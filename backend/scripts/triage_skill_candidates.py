"""Phase 1 — LLM triage of pending skill candidates into a reviewable shortlist.

Pulls pending `skill_candidates` with company_count >= MIN_COMPANIES, drops any
already covered by the taxonomy (alias/fuzzy match), then runs a Claude haiku
pass that, per candidate, decides keep/skip and proposes category + subcategory
+ aliases. Writes backend/data/skill_shortlist.json grouped by category for the
user to bulk-approve before promotion (see scripts/promote_shortlist.py).

This is READ-ONLY w.r.t. the DB — it only reads candidates + taxonomy and writes
a JSON artifact. Promotion happens separately after human review.

Run (against prod):
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/triage_skill_candidates.py
    ... scripts/triage_skill_candidates.py --min-companies 3 --limit 100   # smaller pass
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

# Default to prod (overridable via DATABASE_URL env). MUST precede app import.
if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Skill
from discover_new_skills import _build_taxonomy_set, _is_in_taxonomy

app = create_app()

# ---------------------------------------------------------------------------
# Subcategory taxonomy (v1) — the LLM must pick subcategory from the list that
# matches the category it assigns.
# ---------------------------------------------------------------------------
SUBCATEGORIES = {
    'technical': [
        'Programming Languages', 'Frontend & Web', 'Backend & APIs', 'Mobile',
        'Databases & Data Engineering', 'Data Science & Analytics',
        'AI & Machine Learning', 'Cloud & Infrastructure', 'DevOps & CI/CD',
        'Security & Compliance', 'Hardware & Embedded', 'QA & Testing',
        'Networking & Systems', 'Enterprise Tools & Platforms',
    ],
    'domain': [
        'Industries', 'Business & Operations', 'Marketing & Growth',
        'Sales & Customer Success', 'Finance & Accounting', 'People & HR',
        'Legal & Compliance', 'Product & Design', 'Methodologies',
    ],
    'soft': [
        'Communication', 'Leadership & Management', 'Collaboration & Teamwork',
        'Problem Solving & Critical Thinking', 'Personal Effectiveness',
    ],
}

MODEL = 'claude-haiku-4-5-20251001'
BATCH_SIZE = 20


def log(msg):
    print(msg, flush=True)


def _subcat_block() -> str:
    lines = []
    for cat, subs in SUBCATEGORIES.items():
        lines.append(f'  {cat}: {", ".join(subs)}')
    return '\n'.join(lines)


def _classify_batch(client, batch):
    """batch: list of dicts {name, contexts}. Returns list aligned by index of
    dicts {keep, category, subcategory, aliases} (or None on parse failure)."""
    items = []
    for i, c in enumerate(batch, 1):
        ctx = f"  (seen as: {'; '.join(c['contexts'][:2])})" if c['contexts'] else ''
        items.append(f'{i}. {c["name"]}{ctx}')
    item_block = '\n'.join(items)

    prompt = (
        'You are curating a job-market SKILLS taxonomy. Each item below is a phrase '
        'extracted from job-description requirements. For each, decide whether it is a '
        'real, discrete, learnable skill, tool, technology, certification, framework, or '
        'methodology worth tracking — versus generic filler, a sentence fragment, a benefit, '
        'a job title, or an EEO/boilerplate phrase (those should be dropped).\n\n'
        'If you KEEP it, assign a category and a subcategory chosen ONLY from this list, '
        'and up to 3 common aliases/spelling variants (acronyms, alternate casing). Use the '
        'cleanest canonical name (you may lightly normalize casing).\n\n'
        f'Allowed subcategories per category:\n{_subcat_block()}\n\n'
        f'Items:\n{item_block}\n\n'
        'Reply with ONLY a JSON array, one object per item in the same order:\n'
        '[{"n":1,"keep":true,"name":"Debezium","category":"technical",'
        '"subcategory":"Databases & Data Engineering","aliases":["CDC"]}, '
        '{"n":2,"keep":false}]\n'
        'No prose, no markdown fences.'
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = resp.content[0].text.strip()
    # strip accidental code fences
    if text.startswith('```'):
        text = text.strip('`')
        if text.lstrip().lower().startswith('json'):
            text = text.lstrip()[4:]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # try to salvage the array slice
        start, end = text.find('['), text.rfind(']')
        if start != -1 and end != -1:
            try:
                parsed = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return [None] * len(batch)
        else:
            return [None] * len(batch)

    by_n = {}
    for obj in parsed:
        if isinstance(obj, dict) and 'n' in obj:
            by_n[obj['n']] = obj
    out = []
    for i in range(1, len(batch) + 1):
        out.append(by_n.get(i))
    return out


def run(min_companies: int, limit: int | None):
    import anthropic
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        log('ANTHROPIC_API_KEY not set — aborting.')
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    with app.app_context():
        taxonomy_set = _build_taxonomy_set(Skill.query.all())
        log(f'Taxonomy: {len(taxonomy_set)} names+aliases')

        rows = db.session.execute(db.text(
            """
            SELECT id, name, job_count, company_count, example_contexts
            FROM skill_candidates
            WHERE status = 'pending' AND company_count >= :minc
            ORDER BY company_count DESC, job_count DESC
            """
        ), {'minc': min_companies}).fetchall()
        log(f'{len(rows)} pending candidates with company_count >= {min_companies}')

        # Drop ones already in taxonomy
        candidates = []
        already = 0
        for r in rows:
            cid, name, jc, cc, ctxs = r
            if _is_in_taxonomy(name.lower(), taxonomy_set):
                already += 1
                continue
            candidates.append({
                'id': cid, 'name': name, 'job_count': jc,
                'company_count': cc, 'contexts': list(ctxs or []),
            })
        log(f'  {already} already covered by taxonomy (skipped), {len(candidates)} to classify')

        if limit:
            candidates = candidates[:limit]
            log(f'  --limit applied: classifying first {len(candidates)}')

    # LLM pass (no DB needed)
    kept = []
    dropped = 0
    failed = 0
    t0 = time.time()
    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i:i + BATCH_SIZE]
        try:
            verdicts = _classify_batch(client, batch)
        except Exception as e:
            log(f'  batch {i // BATCH_SIZE} error: {e} — leaving pending')
            failed += len(batch)
            continue
        for cand, v in zip(batch, verdicts):
            if v is None:
                failed += 1
                continue
            if not v.get('keep'):
                dropped += 1
                continue
            cat = (v.get('category') or '').lower()
            if cat not in SUBCATEGORIES:
                cat = 'domain'
            sub = v.get('subcategory') or ''
            if sub not in SUBCATEGORIES[cat]:
                sub = ''  # flag for manual fill
            kept.append({
                'candidate_id': cand['id'],
                'name': v.get('name') or cand['name'],
                'category': cat,
                'subcategory': sub,
                'aliases': [a for a in (v.get('aliases') or []) if a][:3],
                'company_count': cand['company_count'],
                'job_count': cand['job_count'],
                'example_contexts': cand['contexts'][:3],
            })
        done = min(i + BATCH_SIZE, len(candidates))
        rate = done / max(time.time() - t0, 1e-6)
        log(f'  {done}/{len(candidates)} classified  (kept {len(kept)}, dropped {dropped}, failed {failed}, {rate:.0f}/s)')

    # group by category for the artifact
    grouped = defaultdict(list)
    for k in sorted(kept, key=lambda x: (-x['company_count'], -x['job_count'])):
        grouped[k['category']].append(k)

    out_path = os.path.join(os.path.dirname(scripts_dir), 'data', 'skill_shortlist.json')
    payload = {
        'meta': {
            'min_companies': min_companies,
            'total_candidates_considered': len(candidates),
            'kept': len(kept), 'dropped': dropped, 'failed': failed,
        },
        'skills_by_category': grouped,
    }
    with open(out_path, 'w') as f:
        json.dump(payload, f, indent=2)
    log(f'\nWrote {len(kept)} shortlisted skills to {out_path}')
    log(f'  kept={len(kept)}  dropped(noise)={dropped}  failed(parse)={failed}')
    for cat in SUBCATEGORIES:
        log(f'    {cat}: {len(grouped[cat])}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--min-companies', type=int, default=2)
    p.add_argument('--limit', type=int, default=None, help='Classify only first N (smoke test)')
    args = p.parse_args()
    run(args.min_companies, args.limit)


if __name__ == '__main__':
    main()
