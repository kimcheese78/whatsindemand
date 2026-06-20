"""Phase 3 — Full taxonomy review: subcategory assignment + quality pass.

Runs a Claude Haiku pass over ALL verified skills to:
  1. Assign a subcategory from the canonical list
  2. Flag mis-categorized skills (wrong technical/domain/soft)
  3. Flag skills to deactivate (junk, pure adjectives, duplicate fragments)
  4. Surface fuzzy-duplicate clusters for manual merge review

Writes two output files:
  - backend/data/taxonomy_review.json — full results (subcategory assignments)
  - backend/data/taxonomy_review_flagged.json — only recategorize/deactivate/dup clusters

Then a separate apply script (apply_taxonomy_review.py) executes the approved changes.

READ-ONLY against the DB — no writes here.

Usage:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/review_taxonomy.py
    ... --category technical    # Only review technical skills (good for incremental runs)
    ... --limit 100             # Smoke test: first N skills
    ... --skip-llm              # Only run fuzzy dedup, no LLM (useful without API key)
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from difflib import SequenceMatcher

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Skill

app = create_app()

MODEL = 'claude-haiku-4-5-20251001'
BATCH_SIZE = 40

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


def _subcat_block() -> str:
    return '\n'.join(
        f'  {cat}: {", ".join(subs)}'
        for cat, subs in SUBCATEGORIES.items()
    )


def _classify_batch_llm(client, batch):
    """batch: list of {id, name, category, job_count}. Returns dict id->result."""
    items = '\n'.join(
        f'{i+1}. [{s["category"]}] {s["name"]} (jobs={s["job_count"]})'
        for i, s in enumerate(batch)
    )
    prompt = (
        'You are auditing a job-market skills taxonomy. Each item shows [current_category] name.\n\n'
        'For EACH item, return a JSON object with:\n'
        '  "n": item number\n'
        '  "subcategory": string from the allowed list below (REQUIRED)\n'
        '  "action": one of "keep" | "recategorize" | "deactivate"\n'
        '  If action="recategorize": add "new_category": one of technical|domain|soft\n'
        '  If action="deactivate": add "reason": why (e.g. "too generic", "junk", "not a skill")\n\n'
        f'Allowed subcategories per category:\n{_subcat_block()}\n\n'
        'Deactivate only clear non-skills: company-specific jargon with no cross-company meaning, '
        'EEO/boilerplate phrases, pure adjectives, or exact duplicates of other items in this batch.\n\n'
        f'Items:\n{items}\n\n'
        'Return ONLY a JSON array, no prose:\n'
        '[{"n":1,"subcategory":"AI & Machine Learning","action":"keep"}, ...]\n'
        'No markdown fences.'
    )
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2500,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = resp.content[0].text.strip().strip('`')
        if text.lower().startswith('json'):
            text = text[4:]
        parsed = json.loads(text)
    except Exception:
        # Fallback: try to extract array
        try:
            start, end = text.find('['), text.rfind(']')
            parsed = json.loads(text[start:end + 1])
        except Exception:
            return {}

    out = {}
    for obj in parsed:
        if isinstance(obj, dict) and 'n' in obj:
            idx = obj['n'] - 1
            if 0 <= idx < len(batch):
                out[batch[idx]['id']] = {
                    'subcategory': obj.get('subcategory', ''),
                    'action': obj.get('action', 'keep'),
                    'new_category': obj.get('new_category', ''),
                    'reason': obj.get('reason', ''),
                }
    return out


def _fuzzy_dedup_clusters(skills, threshold=0.88):
    """Return list of {a, b, similarity} for near-duplicate pairs."""
    names = [(s['id'], s['name'].lower()) for s in skills]
    clusters = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            id_a, n_a = names[i]
            id_b, n_b = names[j]
            if abs(len(n_a) - len(n_b)) > 20:
                continue
            sim = SequenceMatcher(None, n_a, n_b).ratio()
            if sim >= threshold:
                clusters.append({
                    'a_id': id_a, 'a_name': skills[i]['name'],
                    'b_id': id_b, 'b_name': skills[j]['name'],
                    'similarity': round(sim, 3),
                })
    clusters.sort(key=lambda x: -x['similarity'])
    return clusters


def run(category_filter, limit, skip_llm):
    if not skip_llm:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print('ANTHROPIC_API_KEY not set. Use --skip-llm to run dedup only.')
            sys.exit(1)
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None

    with app.app_context():
        q = Skill.query.filter(Skill.is_verified == True)
        if category_filter:
            q = q.filter(Skill.category == category_filter)
        skills_rows = q.order_by(Skill.category, Skill.total_job_count.desc()).all()

    skills = [
        {'id': s.id, 'name': s.name, 'category': s.category or 'technical',
         'subcategory': s.subcategory, 'job_count': s.total_job_count or 0}
        for s in skills_rows
    ]
    if limit:
        skills = skills[:limit]
    print(f'{len(skills)} verified skills to review')

    results = {}  # id -> {subcategory, action, new_category, reason}

    if not skip_llm:
        t0 = time.time()
        for i in range(0, len(skills), BATCH_SIZE):
            batch = skills[i:i + BATCH_SIZE]
            try:
                batch_results = _classify_batch_llm(client, batch)
                results.update(batch_results)
            except Exception as e:
                print(f'  batch {i // BATCH_SIZE} error: {e} — skipping')
            done = min(i + BATCH_SIZE, len(skills))
            elapsed = time.time() - t0
            print(f'  {done}/{len(skills)} ({done/elapsed:.0f}/s)', flush=True)

    # Fuzzy dedup (all skills in scope, category-filtered if set)
    print('Running fuzzy dedup...')
    dup_clusters = _fuzzy_dedup_clusters(skills)
    print(f'  {len(dup_clusters)} near-duplicate pairs found')

    # Merge LLM results into skill records
    all_results = []
    for s in skills:
        r = results.get(s['id'], {})
        sub = r.get('subcategory') or s.get('subcategory') or ''
        # Validate subcategory against allowed list
        cat = r.get('new_category') or s['category']
        if sub not in SUBCATEGORIES.get(cat, []):
            sub = ''
        all_results.append({
            'id': s['id'],
            'name': s['name'],
            'current_category': s['category'],
            'current_subcategory': s.get('subcategory'),
            'proposed_subcategory': sub,
            'action': r.get('action', 'keep'),
            'new_category': r.get('new_category', ''),
            'deactivate_reason': r.get('reason', ''),
        })

    # Group by category/subcategory
    grouped = defaultdict(lambda: defaultdict(list))
    for item in all_results:
        cat = item['new_category'] or item['current_category'] or 'unknown'
        sub = item['proposed_subcategory'] or '(unassigned)'
        grouped[cat][sub].append(item)

    # Flagged: recategorize + deactivate + dups
    flagged = {
        'recategorize': [x for x in all_results if x['action'] == 'recategorize'],
        'deactivate': [x for x in all_results if x['action'] == 'deactivate'],
        'dup_clusters': dup_clusters,
    }

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)

    full_path = os.path.join(data_dir, 'taxonomy_review.json')
    with open(full_path, 'w') as f:
        json.dump({'meta': {'total': len(all_results), 'dup_pairs': len(dup_clusters)},
                   'skills_by_category': {k: dict(v) for k, v in grouped.items()}}, f, indent=2)

    flagged_path = os.path.join(data_dir, 'taxonomy_review_flagged.json')
    with open(flagged_path, 'w') as f:
        json.dump(flagged, f, indent=2)

    print(f'\nWrote {len(all_results)} skills to {full_path}')
    print(f'Flagged: {len(flagged["recategorize"])} recategorize, '
          f'{len(flagged["deactivate"])} deactivate, {len(dup_clusters)} dup pairs')
    print(f'Review {flagged_path} for items needing action.')
    print(f'\nNext: run scripts/apply_taxonomy_review.py after reviewing the flagged file.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--category', choices=['technical', 'domain', 'soft'], default=None)
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--skip-llm', action='store_true', help='Run fuzzy dedup only (no API calls)')
    args = p.parse_args()
    run(args.category, args.limit, args.skip_llm)


if __name__ == '__main__':
    main()
