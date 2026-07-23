"""AI triage for pending skill candidates.

Sends pending skill_candidates (company_count >= 2) to Claude in batches,
gets keep/drop decisions with category/subcategory/aliases, then promotes
keeps to the skills table and rejects drops. Replaces the claude.ai cloud
review routine — runs inside the weekly Railway cron (agent_run.py).

Usage (standalone):
    DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/ai_triage_skills.py          # dry-run
    DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/ai_triage_skills.py --apply
"""
import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import db, Skill
import anthropic

MODEL = 'claude-sonnet-5'
BATCH_SIZE = 100
MAX_CANDIDATES = 300

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

SYSTEM_PROMPT = """\
You curate the skill taxonomy of a job market intelligence platform. The goal
is concrete, learnable skills — things a recruiter could list in a job
requirement and a candidate could claim on a resume.

For each candidate, decide keep or drop from its name and example contexts.

DROP if ANY apply:
- Generic filler or adjective phrase ("best practices", "fast-paced environment")
- EEO / benefits boilerplate
- Verb phrase or sentence fragment ("building scalable systems")
- Job title or seniority level
- Company name used generically (unless clearly a product/platform)
- Already covered by the existing taxonomy (exact or near-duplicate)
- Too vague to mean anything specific

KEEP: assign a clean canonical name (no "using"/"experience with" prefixes,
no "or similar" suffixes, no version numbers), category, subcategory, and 0-2
GENUINE aliases. Aliases are matched case-insensitively against every job
description — never use common words or ambiguous acronyms as aliases.

Subcategory must belong to the chosen category exactly as listed in the user
message.

Self-verify before answering: subcategory matches category; no near-duplicate
pairs among your keeps; aliases are real alternates.

Respond ONLY with a JSON array — no prose, no markdown fences:
[{"candidate_id": 123, "action": "keep", "name": "Temporal",
  "category": "technical", "subcategory": "Backend & APIs", "aliases": []},
 {"candidate_id": 124, "action": "drop"}]
Every candidate must appear exactly once.\
"""


def load_pending(limit=MAX_CANDIDATES):
    rows = db.session.execute(db.text("""
        SELECT id, name, job_count, company_count, example_contexts
        FROM skill_candidates
        WHERE status = 'pending' AND company_count >= 2
        ORDER BY company_count DESC, job_count DESC LIMIT :lim
    """), {'lim': limit}).fetchall()
    return [{'id': r[0], 'name': r[1], 'job_count': r[2],
             'company_count': r[3], 'contexts': list(r[4] or [])[:3]} for r in rows]


def load_taxonomy_names():
    skills = db.session.execute(db.text(
        "SELECT name, aliases FROM skills WHERE is_verified=true"
    )).fetchall()
    return [s[0] for s in skills] + [a for s in skills for a in (s[1] or [])]


def build_system_blocks(taxonomy_names):
    """Static prompt prefix, cached across batches within a run.
    Cache reads cost ~0.1x, so only the first batch pays for the ~25k-token
    taxonomy; sorted() keeps the bytes deterministic for prefix matching."""
    subcats = json.dumps(SUBCATEGORIES, indent=1)
    return [
        {'type': 'text', 'text': SYSTEM_PROMPT},
        {
            'type': 'text',
            'text': (
                f'# Valid subcategories per category\n{subcats}\n\n'
                f'# Existing taxonomy (names + aliases) — drop near-duplicates of these\n'
                f'{", ".join(sorted(taxonomy_names))}'
            ),
            'cache_control': {'type': 'ephemeral'},
        },
    ]


def build_user_prompt(batch):
    cands = '\n'.join(
        f'- id={c["id"]} name={c["name"]!r} companies={c["company_count"]} '
        f'jobs={c["job_count"]} contexts={c["contexts"]!r}'
        for c in batch
    )
    return f'# Candidates to classify ({len(batch)})\n{cands}'


def classify(candidates, taxonomy_names):
    """Batch candidates to Claude; returns list of decision dicts."""
    client = anthropic.Anthropic()
    system_blocks = build_system_blocks(taxonomy_names)
    decisions = []
    for start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[start:start + BATCH_SIZE]
        print(f'  Claude batch {start // BATCH_SIZE + 1}: {len(batch)} candidates', flush=True)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=system_blocks,
            messages=[{'role': 'user', 'content': build_user_prompt(batch)}],
        )
        u = resp.usage
        print(f'    tokens: in={u.input_tokens} cache_write={u.cache_creation_input_tokens} '
              f'cache_read={u.cache_read_input_tokens} out={u.output_tokens}', flush=True)
        text_block = next((b for b in resp.content if getattr(b, 'type', None) == 'text'), None)
        if text_block is None:
            raise ValueError(f'no text block in response (got: {[getattr(b, "type", None) for b in resp.content]})')
        raw = text_block.text.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        decisions.extend(json.loads(raw))
        if start + BATCH_SIZE < len(candidates):
            time.sleep(1)
    return decisions


def apply_decisions(decisions, apply=True):
    """Promote keeps / reject drops. Returns stats dict incl. new_skill_ids."""
    from scripts.discover_new_skills import _build_taxonomy_set, _is_in_taxonomy

    valid_ids = set()
    keeps, drop_ids = [], []
    for d in decisions:
        cid = d.get('candidate_id')
        if cid is None or cid in valid_ids:
            continue
        valid_ids.add(cid)
        if d.get('action') == 'keep' and d.get('name') and d.get('category'):
            cat = d['category'].lower()
            sub = d.get('subcategory') or ''
            if cat not in SUBCATEGORIES or (sub and sub not in SUBCATEGORIES[cat]):
                print(f'  ⚠ invalid category/subcategory for {d["name"]!r} — dropping')
                drop_ids.append(cid)
                continue
            keeps.append(d)
        else:
            drop_ids.append(cid)

    taxonomy_set = _build_taxonomy_set(Skill.query.all())
    inserted = skipped_dup = 0
    new_ids = []
    now = datetime.utcnow()

    for d in keeps:
        canonical = d['name'].strip()
        cid = d['candidate_id']
        exact = Skill.query.filter(db.func.lower(Skill.name) == canonical.lower()).first()
        if exact or _is_in_taxonomy(canonical.lower(), taxonomy_set):
            print(f'  SKIP (dup): {canonical!r}')
            if apply:
                db.session.execute(db.text(
                    "UPDATE skill_candidates SET status='rejected',"
                    " rejected_reason='already_in_taxonomy' WHERE id=:cid"
                ), {'cid': cid})
            skipped_dup += 1
            continue

        print(f'  INSERT: {canonical!r}  ({d["category"].lower()} / {d.get("subcategory")})'
              f'  aliases={d.get("aliases") or []}')
        if apply:
            skill = Skill(
                name=canonical,
                category=d['category'].lower(),
                subcategory=d.get('subcategory') or None,
                aliases=d.get('aliases') or [],
                is_verified=True,
                total_job_count=0,
                trending_score=0.0,
                created_at=now,
                updated_at=now,
            )
            db.session.add(skill)
            db.session.flush()
            new_ids.append(skill.id)
            db.session.execute(db.text("""
                INSERT INTO job_skills (job_id, skill_id, is_required, created_at)
                SELECT scj.job_id, :sid, true, NOW()
                FROM skill_candidate_jobs scj
                WHERE scj.candidate_id = :cid
                AND NOT EXISTS (
                    SELECT 1 FROM job_skills js
                    WHERE js.job_id = scj.job_id AND js.skill_id = :sid
                )
            """), {'sid': skill.id, 'cid': cid})
            db.session.execute(db.text("""
                UPDATE skill_candidates
                SET status='approved', promoted_skill_id=:sid, promoted_at=NOW()
                WHERE id=:cid
            """), {'sid': skill.id, 'cid': cid})
        taxonomy_set.add(canonical.lower())
        inserted += 1

    if apply and drop_ids:
        db.session.execute(db.text(
            "UPDATE skill_candidates SET status='rejected',"
            " rejected_reason='ai_triage_dropped' WHERE id = ANY(:ids) AND status='pending'"
        ), {'ids': drop_ids})

    if apply:
        db.session.commit()

    return {
        'reviewed': len(valid_ids),
        'kept': inserted,
        'dropped': len(drop_ids),
        'skipped_duplicates': skipped_dup,
        'new_skill_ids': new_ids,
    }


def run(apply=True):
    """Full triage: load → classify → apply. Returns stats dict.
    Must be called inside an app context."""
    candidates = load_pending()
    if not candidates:
        print('No pending skill candidates.')
        return {'reviewed': 0, 'kept': 0, 'dropped': 0,
                'skipped_duplicates': 0, 'new_skill_ids': []}
    print(f'Triaging {len(candidates)} pending candidates via {MODEL} …')
    taxonomy_names = load_taxonomy_names()
    decisions = classify(candidates, taxonomy_names)
    return apply_decisions(decisions, apply=apply)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    from app import create_app
    APPLY = '--apply' in sys.argv
    app = create_app()
    with app.app_context():
        stats = run(apply=APPLY)
        print(f'\n{"Applied" if APPLY else "Dry-run"}: {stats}')
        if not APPLY:
            print('Pass --apply to commit.')
