"""AI-assisted role mapping for unmatched job titles.

Uses Claude to classify each pending unmatched_title by looking at:
  - The raw job title
  - The job's department (if available)
  - A snippet of the job's requirements_text or description_text

Strategy:
  1. Load all canonical roles from the DB at runtime (no hardcoded IDs)
  2. For pending unmatched_titles with job_count >= MIN_JOBS:
     a. Fetch one representative job with its JD text
     b. Batch 25 titles per Claude call
     c. Claude maps to existing role, flags as new_role, or rejects
  3. Checkpoint progress → backend/data/ai_role_decisions.json
  4. --apply to commit decisions to the database

Usage:
    cd backend
    DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/ai_map_roles.py
    DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/ai_map_roles.py --apply
    DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/ai_map_roles.py --min-jobs 10 --limit 200
"""
import json, os, sys, re, time
from collections import defaultdict

# Pass DATABASE_URL as an env var — see CLAUDE.md for the prod DSN.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Job, Role, RoleTitleVariation, UnmatchedTitle
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
APPLY = '--apply' in sys.argv
MIN_JOBS = int(next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == '--min-jobs'), 5))
LIMIT = int(next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == '--limit'), 9999))
BATCH_SIZE = 25   # titles per Claude API call
JD_CHARS = 800    # chars of JD text to include per title
COMMIT_EVERY = 100  # DB commit cadence when applying

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CHECKPOINT_FILE = os.path.join(DATA_DIR, 'ai_role_decisions.json')

MODEL = 'claude-sonnet-4-6'

# ── Reject filters (skip these before sending to Claude) ──────────────────────
_INTERN_PATTERNS = re.compile(
    r'\bintern\b|\binternship\b|\bvolunteer\b|\bapprentice\b|\bwerkstudent\b|\bpraktikum\b',
    re.IGNORECASE
)
_NON_ASCII_THRESHOLD = 0.25   # >25% non-ASCII chars → likely non-English


def _is_english(title: str) -> bool:
    non_ascii = sum(1 for c in title if ord(c) >= 128)
    return non_ascii / max(len(title), 1) < _NON_ASCII_THRESHOLD


def _quick_reject(title: str) -> str | None:
    if not _is_english(title):
        return 'non-english'
    if _INTERN_PATTERNS.search(title):
        return 'intern/volunteer'
    if len(title.strip()) < 4:
        return 'too-short'
    return None


# ── DB helpers ────────────────────────────────────────────────────────────────

def load_canonical_roles() -> list[dict]:
    """Load all roles from DB, sorted by category then title."""
    roles = db.session.execute(db.text(
        'SELECT id, normalized_title, category, job_family '
        'FROM roles ORDER BY category, normalized_title'
    )).fetchall()
    return [
        {'id': r.id, 'title': r.normalized_title,
         'category': r.category or 'Uncategorized',
         'job_family': r.job_family or ''}
        for r in roles
    ]


def load_pending_titles(min_jobs: int) -> list[dict]:
    """Pending unmatched_titles above job_count threshold, highest count first."""
    rows = db.session.execute(db.text(
        "SELECT id, raw_title, job_count "
        "FROM unmatched_titles "
        "WHERE status = 'pending' AND job_count >= :min "
        "ORDER BY job_count DESC"
    ), {'min': min_jobs}).fetchall()
    return [{'id': r.id, 'title': r.raw_title, 'jobs': r.job_count} for r in rows]


def fetch_jd_snippets(titles: list[str]) -> dict[str, dict]:
    """For each raw title, fetch one representative job's dept + JD text."""
    if not titles:
        return {}
    rows = db.session.execute(db.text(
        """
        SELECT DISTINCT ON (j.title)
               j.title,
               j.department,
               COALESCE(j.requirements_text, j.description_text, '') AS jd_text
        FROM jobs j
        WHERE j.title = ANY(:titles)
          AND j.is_active = TRUE
        ORDER BY j.title, (j.requirements_text IS NOT NULL) DESC, j.scraped_at DESC
        """
    ), {'titles': titles}).fetchall()
    result = {}
    for r in rows:
        jd = (r.jd_text or '').strip()[:JD_CHARS]
        result[r.title] = {'department': r.department or '', 'jd': jd}
    return result


def title_to_role_id(title: str, role_map: dict[str, int]) -> int | None:
    return role_map.get(title.lower().strip())


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {'decisions': []}


def save_checkpoint(decisions: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({'decisions': decisions}, f, indent=2)


# ── Canonical roles prompt block ──────────────────────────────────────────────

def build_roles_block(roles: list[dict]) -> str:
    by_cat: dict[str, list[str]] = defaultdict(list)
    for r in roles:
        by_cat[r['category']].append(r['title'])
    lines = []
    for cat in sorted(by_cat):
        lines.append(f'## {cat}')
        for t in sorted(by_cat[cat]):
            lines.append(f'  - {t}')
    return '\n'.join(lines)


SYSTEM_PROMPT = """\
You are a job taxonomy expert for a job market intelligence platform.
Your task: map raw job titles to canonical roles.

Rules:
- Match the role's PRIMARY FUNCTION, not the industry or employer.
- Seniority (Senior, Lead, Principal, Jr, Associate…) is irrelevant when picking the role — always pick the base role.
- Salary info, location, or schedule modifiers in the title do not affect the role classification.
- Use the provided JD snippet to disambiguate ambiguous titles (e.g. "Executive" alone is unclear; the JD will show the function).
- action=map    → best match exists in the canonical list. Provide the exact canonical role title.
- action=reject → non-job (posting is noise, test, event, non-English, or an intern/volunteer with no real function).
- action=new_role → the job function is GENUINELY absent from the canonical list (not a variant, not a seniority variation). Provide a clean normalized title and category.
- action=skip   → cannot determine from title + JD. Use sparingly.

Respond ONLY with a JSON array — no prose, no markdown fences.\
"""


def build_user_prompt(batch: list[dict], roles_block: str) -> str:
    items = []
    for i, item in enumerate(batch):
        jd = item['jd'][:JD_CHARS] if item['jd'] else ''
        dept = item['department']
        context = f'Dept: {dept}  |  JD: {jd}' if (dept or jd) else '(no JD available)'
        items.append(
            f'{i+1}. Title: "{item["title"]}"\n'
            f'   Context: {context}'
        )

    return (
        f'# Canonical Roles\n{roles_block}\n\n'
        f'# Job Titles to Classify\n' + '\n\n'.join(items) +
        '\n\n# Response format (JSON array, one entry per title above)\n'
        '[\n'
        '  {"idx": 1, "action": "map", "role": "<exact canonical title>"},\n'
        '  {"idx": 2, "action": "reject", "reason": "<brief reason>"},\n'
        '  {"idx": 3, "action": "new_role", "suggested_title": "<clean title>", '
        '"category": "<category>", "job_family": "<job family>"},\n'
        '  {"idx": 4, "action": "skip", "reason": "<why unclear>"}\n'
        ']'
    )


# ── Claude API call ───────────────────────────────────────────────────────────

def call_claude(client: anthropic.Anthropic, user_prompt: str) -> list[dict]:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_prompt}],
    )
    raw = resp.content[0].text.strip()
    # Strip markdown fences if model adds them despite instructions
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    return json.loads(raw)


# ── Apply decisions ───────────────────────────────────────────────────────────

def apply_decisions(decisions: list, role_map: dict[str, int]):
    stats = defaultdict(int)
    affected_role_ids: set[int] = set()

    for i, dec in enumerate(decisions):
        raw_title = dec['raw_title']
        action = dec['action']

        if action == 'map':
            rid = title_to_role_id(dec.get('role', ''), role_map)
            if not rid:
                print(f'  ⚠ role not found: {dec.get("role")!r}  (for {raw_title!r})')
                stats['missing_role'] += 1
                continue

            updated = (db.session.query(Job)
                       .filter(Job.title == raw_title, Job.role_id.is_(None))
                       .update({'role_id': rid}, synchronize_session=False))
            stats['jobs_updated'] += updated
            affected_role_ids.add(rid)

            existing = RoleTitleVariation.query.filter_by(original_title=raw_title).first()
            if existing:
                existing.role_id = rid
                existing.frequency = max(existing.frequency, dec.get('jobs', 1))
                stats['variations_updated'] += 1
            else:
                db.session.add(RoleTitleVariation(
                    role_id=rid, original_title=raw_title,
                    frequency=max(1, dec.get('jobs', 1))))
                stats['variations_created'] += 1

            ut = UnmatchedTitle.query.filter_by(raw_title=raw_title).first()
            if ut:
                ut.status = 'approved'
                ut.mapped_role_id = rid
                stats['approved'] += 1

        elif action == 'reject':
            ut = UnmatchedTitle.query.filter_by(raw_title=raw_title).first()
            if ut:
                ut.status = 'rejected'
                ut.rejected_reason = dec.get('reason', 'ai-rejected')[:255]
                stats['rejected'] += 1

        elif action == 'new_role':
            suggested = dec.get('suggested_title', '').strip()
            if not suggested:
                stats['bad_new_role'] += 1
                continue
            existing_role = Role.query.filter(
                db.func.lower(Role.normalized_title) == suggested.lower()
            ).first()
            if existing_role:
                rid = existing_role.id
                print(f'  → new_role already exists: "{suggested}" (id={rid})')
            else:
                role = Role(
                    normalized_title=suggested,
                    category=dec.get('category'),
                    job_family=dec.get('job_family'),
                    total_active_jobs=0,
                )
                db.session.add(role)
                db.session.flush()
                rid = role.id
                print(f'  + Created role: "{suggested}" (id={rid})')
                stats['roles_created'] += 1

            updated = (db.session.query(Job)
                       .filter(Job.title == raw_title, Job.role_id.is_(None))
                       .update({'role_id': rid}, synchronize_session=False))
            stats['jobs_updated'] += updated
            affected_role_ids.add(rid)

            existing = RoleTitleVariation.query.filter_by(original_title=raw_title).first()
            if existing:
                existing.role_id = rid
                stats['variations_updated'] += 1
            else:
                db.session.add(RoleTitleVariation(
                    role_id=rid, original_title=raw_title,
                    frequency=max(1, dec.get('jobs', 1))))
                stats['variations_created'] += 1

            ut = UnmatchedTitle.query.filter_by(raw_title=raw_title).first()
            if ut:
                ut.status = 'approved'
                ut.mapped_role_id = rid
                stats['approved'] += 1

        if (i + 1) % COMMIT_EVERY == 0:
            db.session.commit()
            print(f'  … committed {i+1}/{len(decisions)}')

    db.session.commit()

    # Refresh total_active_jobs for all touched roles
    roles = Role.query.filter(Role.id.in_(affected_role_ids)).all()
    for role in roles:
        role.total_active_jobs = (
            Job.query.filter_by(role_id=role.id, is_active=True).count()
        )
    db.session.commit()
    print(f'  Refreshed counts for {len(roles)} roles')

    # Write new aliases to aliases.yaml so the normalizer classifies these
    # titles automatically at scrape time — prevents re-queueing next run.
    _update_aliases_yaml(decisions)

    return stats


def _update_aliases_yaml(decisions: list) -> None:
    """Append newly mapped titles to aliases.yaml as de-leveled aliases."""
    import yaml as _yaml
    from app.utils.role_normalizer_v2 import _delevel, _load_taxonomy

    canonical_yaml, existing_aliases = _load_taxonomy()
    # Reverse map: role name (lowercase) → canonical_id
    reverse_map = {v['name'].lower(): k for k, v in canonical_yaml.items()}

    aliases_path = os.path.join(DATA_DIR, '..', 'data', 'aliases.yaml')
    aliases_path = os.path.normpath(aliases_path)

    new_entries = []
    for dec in decisions:
        if dec['action'] not in ('map', 'new_role'):
            continue
        raw = dec['raw_title']
        role_name = dec.get('role') or dec.get('suggested_title', '')
        canonical_id = reverse_map.get(role_name.lower())
        if not canonical_id:
            continue
        deleveled = _delevel(raw)
        if not deleveled or deleveled in existing_aliases:
            continue
        new_entries.append((deleveled, canonical_id))

    if not new_entries:
        return

    with open(aliases_path, 'a') as f:
        f.write(f'\n# Auto-added by ai_map_roles --apply\n')
        for title, cid in sorted(new_entries):
            f.write(f'"{title}": {cid}\n')

    print(f'  aliases.yaml: added {len(new_entries)} new entries')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = create_app()
    client = anthropic.Anthropic()

    with app.app_context():
        # ── Load roles ──────────────────────────────────────────────────────
        canonical = load_canonical_roles()
        role_map = {r['title'].lower(): r['id'] for r in canonical}
        roles_block = build_roles_block(canonical)
        print(f'Loaded {len(canonical)} canonical roles from DB')

        # ── Apply mode ──────────────────────────────────────────────────────
        if APPLY:
            checkpoint = load_checkpoint()
            decisions = checkpoint.get('decisions', [])
            if not decisions:
                print('No decisions to apply. Run without --apply first.')
                return

            map_d  = [d for d in decisions if d['action'] == 'map']
            new_d  = [d for d in decisions if d['action'] == 'new_role']
            rej_d  = [d for d in decisions if d['action'] == 'reject']
            skip_d = [d for d in decisions if d['action'] == 'skip']
            print(f'Applying {len(decisions)} decisions: '
                  f'{len(map_d)} map, {len(new_d)} new_role, '
                  f'{len(rej_d)} reject, {len(skip_d)} skip')

            stats = apply_decisions(decisions, role_map)

            print(f'\nResults:')
            print(f'  Jobs updated:          {stats["jobs_updated"]:,}')
            print(f'  Variations created:    {stats["variations_created"]:,}')
            print(f'  Variations updated:    {stats["variations_updated"]:,}')
            print(f'  Candidates approved:   {stats["approved"]:,}')
            print(f'  Candidates rejected:   {stats["rejected"]:,}')
            print(f'  Roles created:         {stats["roles_created"]:,}')
            if stats['missing_role']:
                print(f'  Missing roles:         {stats["missing_role"]:,}')
            return

        # ── Generate decisions ───────────────────────────────────────────────
        # Load checkpoint to skip already-processed titles
        checkpoint = load_checkpoint()
        processed_titles = {d['raw_title'] for d in checkpoint.get('decisions', [])}
        all_decisions = list(checkpoint.get('decisions', []))

        pending = load_pending_titles(MIN_JOBS)
        print(f'Found {len(pending):,} pending titles with job_count >= {MIN_JOBS}')

        # Filter out already processed
        todo = [t for t in pending if t['title'] not in processed_titles]
        todo = todo[:LIMIT]
        print(f'To process: {len(todo):,}  (already done: {len(processed_titles):,})')

        if not todo:
            print('Nothing to do.')
            return

        # Quick-reject obvious noise before sending to Claude
        quick_rejects = []
        to_classify = []
        for t in todo:
            reason = _quick_reject(t['title'])
            if reason:
                quick_rejects.append({**t, 'action': 'reject', 'reason': reason, 'raw_title': t['title']})
            else:
                to_classify.append(t)

        print(f'Quick-rejected: {len(quick_rejects):,}  To Claude: {len(to_classify):,}')

        # Add quick rejects to decisions
        all_decisions.extend(quick_rejects)
        save_checkpoint(all_decisions)

        # ── Fetch JD snippets in bulk ────────────────────────────────────────
        print('Fetching JD snippets …')
        all_classify_titles = [t['title'] for t in to_classify]
        jd_map = fetch_jd_snippets(all_classify_titles)
        print(f'  JD available for {len(jd_map):,} / {len(all_classify_titles):,} titles')

        # Attach JD data to classify items
        for t in to_classify:
            jd_info = jd_map.get(t['title'], {})
            t['department'] = jd_info.get('department', '')
            t['jd'] = jd_info.get('jd', '')

        # ── Batch → Claude ───────────────────────────────────────────────────
        total_batches = (len(to_classify) + BATCH_SIZE - 1) // BATCH_SIZE
        errors = 0

        for batch_num, batch_start in enumerate(range(0, len(to_classify), BATCH_SIZE)):
            batch = to_classify[batch_start:batch_start + BATCH_SIZE]
            print(f'\nBatch {batch_num+1}/{total_batches}  '
                  f'({batch_start+1}-{batch_start+len(batch)} of {len(to_classify):,})')
            for b in batch:
                print(f'  {b["jobs"]:4d} jobs  {b["title"]}')

            user_prompt = build_user_prompt(batch, roles_block)

            try:
                results = call_claude(client, user_prompt)
            except Exception as e:
                print(f'  ❌ Claude error: {e}')
                errors += 1
                if errors >= 3:
                    print('Too many errors, stopping.')
                    break
                time.sleep(5)
                continue

            # Map idx back to title
            idx_to_item = {i+1: b for i, b in enumerate(batch)}
            batch_decisions = []
            for r in results:
                idx = r.get('idx')
                item = idx_to_item.get(idx)
                if not item:
                    print(f'  ⚠ idx {idx} not found in batch')
                    continue

                dec = {
                    'raw_title': item['title'],
                    'jobs': item['jobs'],
                    'action': r.get('action', 'skip'),
                }
                if dec['action'] == 'map':
                    dec['role'] = r.get('role', '')
                    # Validate the role exists
                    if not title_to_role_id(dec['role'], role_map):
                        print(f'  ⚠ Claude returned unknown role: {dec["role"]!r} '
                              f'for {item["title"]!r} — setting skip')
                        dec['action'] = 'skip'
                        dec['reason'] = f'unknown role: {dec["role"]}'
                    else:
                        print(f'  ✓ {item["title"]!r}  →  {dec["role"]!r}')
                elif dec['action'] == 'reject':
                    dec['reason'] = r.get('reason', '')
                    print(f'  ✗ reject  {item["title"]!r}  ({dec["reason"]})')
                elif dec['action'] == 'new_role':
                    dec['suggested_title'] = r.get('suggested_title', '')
                    dec['category'] = r.get('category', '')
                    dec['job_family'] = r.get('job_family', '')
                    print(f'  + new_role  {item["title"]!r}  →  "{dec["suggested_title"]}"')
                else:
                    dec['reason'] = r.get('reason', '')
                    print(f'  ? skip  {item["title"]!r}  ({dec["reason"]})')

                batch_decisions.append(dec)

            all_decisions.extend(batch_decisions)
            save_checkpoint(all_decisions)
            print(f'  Checkpoint saved ({len(all_decisions):,} total decisions)')

            # Small delay to be polite to the API
            if batch_num < total_batches - 1:
                time.sleep(1)

        # ── Summary ──────────────────────────────────────────────────────────
        final = all_decisions
        by_action = defaultdict(int)
        for d in final:
            by_action[d['action']] += 1

        print(f'\n{"="*55}')
        print(f'Done. {len(final):,} total decisions written to {CHECKPOINT_FILE}')
        print(f'  map:      {by_action["map"]:,}')
        print(f'  new_role: {by_action["new_role"]:,}')
        print(f'  reject:   {by_action["reject"]:,}')
        print(f'  skip:     {by_action["skip"]:,}')
        print()
        print('Review the decisions, then run with --apply to commit.')
        print()

        # Show new_role candidates for review
        new_roles = [d for d in final if d['action'] == 'new_role']
        if new_roles:
            by_suggested = defaultdict(list)
            for d in new_roles:
                by_suggested[d['suggested_title']].append(d)
            print('New role candidates:')
            for title, items in sorted(by_suggested.items(),
                                       key=lambda x: -sum(i['jobs'] for i in x[1])):
                total = sum(i['jobs'] for i in items)
                cat = items[0].get('category', '?')
                print(f'  {total:5d} jobs  "{title}"  [{cat}]  ({len(items)} titles)')

        # Show sample mappings
        maps = [d for d in final if d['action'] == 'map']
        if maps:
            print('\nSample mappings (top 25 by job count):')
            for d in sorted(maps, key=lambda x: -x['jobs'])[:25]:
                print(f'  {d["jobs"]:4d}  {d["raw_title"]!r}  →  {d["role"]!r}')


if __name__ == '__main__':
    main()
