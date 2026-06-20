"""Review all skill aliases for over-matching and taxonomy conflicts.

Flags three problems per alias:
  - too_broad: generic word/phrase that matches jobs it shouldn't
  - duplicate_skill: alias is (or closely matches) another skill's canonical name
  - misleading: alias implies a different skill than the canonical

Writes backend/data/alias_review.json — then run apply_alias_review.py to execute.

Usage:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/review_aliases.py
    ... --batch-size 20 --limit 50   # smoke test
"""
import argparse
import json
import os
import sys
import time

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Skill

app = create_app()
MODEL = 'claude-haiku-4-5-20251001'
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def _review_batch(client, batch, all_names_lower: set) -> list:
    """
    batch: list of {id, name, category, aliases, job_count}
    Returns list of {skill_id, name, alias_verdicts: [{alias, keep, reason, flag}]}
    """
    lines = []
    for i, s in enumerate(batch, 1):
        aliases_str = ', '.join(f'"{a}"' for a in s['aliases'])
        lines.append(f'{i}. [{s["category"]}] {s["name"]} (jobs={s["job_count"]})\n   aliases: {aliases_str}')

    prompt = (
        'You are auditing the aliases of a job-market skills taxonomy. '
        'Each alias is used for regex matching: if the alias appears anywhere in a job\'s requirements section, '
        'the job gets tagged with that skill.\n\n'
        'For each alias, decide: KEEP or REMOVE.\n\n'
        'REMOVE if any of these apply:\n'
        '  - too_broad: the word/phrase appears in almost every job description regardless of whether '
        'the skill is required (e.g. "scheduling" for Time Management, "presentations" for PowerPoint)\n'
        '  - duplicate_skill: the alias is (or is nearly identical to) a different canonical skill name '
        'in the taxonomy — this causes every mention of that skill to double-tag the current one\n'
        '  - misleading: the alias implies a meaningfully different concept than the canonical skill name\n\n'
        'KEEP if the alias is a genuine variant spelling, abbreviation, or close synonym that a job posting '
        'would use specifically when requiring this skill.\n\n'
        f'Skills to review:\n' + '\n'.join(lines) + '\n\n'
        'Reply ONLY as a JSON array, one object per skill in order:\n'
        '[{"n":1,"aliases":[{"alias":"foo","keep":true},{"alias":"bar","keep":false,"flag":"too_broad","reason":"..."}]}, ...]\n'
        'No prose, no markdown.'
    )

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = resp.content[0].text.strip().strip('`')
        if text.lower().startswith('json'):
            text = text[4:]
        parsed = json.loads(text)
    except Exception as e:
        print(f'    parse error: {e}')
        return []

    results = []
    by_n = {obj['n']: obj for obj in parsed if isinstance(obj, dict) and 'n' in obj}
    for i, skill in enumerate(batch, 1):
        obj = by_n.get(i)
        if not obj:
            continue
        verdicts = []
        for av in (obj.get('aliases') or []):
            alias = av.get('alias', '')
            # Also auto-flag if alias exactly matches another skill's canonical name
            auto_dup = alias.lower() in all_names_lower and alias.lower() != skill['name'].lower()
            flag = av.get('flag', '')
            if auto_dup and av.get('keep', True):
                flag = 'duplicate_skill'
            verdicts.append({
                'alias': alias,
                'keep': av.get('keep', True) and not auto_dup,
                'flag': flag,
                'reason': av.get('reason', 'duplicate of another skill name' if auto_dup else ''),
            })
        results.append({
            'skill_id': skill['id'],
            'name': skill['name'],
            'category': skill['category'],
            'job_count': skill['job_count'],
            'alias_verdicts': verdicts,
        })
    return results


def run(batch_size: int, limit: int | None):
    import anthropic
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print('ANTHROPIC_API_KEY not set')
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    with app.app_context():
        rows = Skill.query.filter(
            Skill.is_verified == True,
            Skill.aliases != None,
        ).order_by(Skill.total_job_count.desc()).all()

        skills = [
            {
                'id': s.id,
                'name': s.name,
                'category': s.category or 'unknown',
                'aliases': [a for a in (s.aliases or []) if a.strip()],
                'job_count': s.total_job_count or 0,
            }
            for s in rows
            if s.aliases and len([a for a in s.aliases if a.strip()]) > 0
        ]

        # Build set of all canonical skill names for auto-dup detection
        all_names_lower = {s.name.lower() for s in Skill.query.filter(Skill.is_verified == True).all()}

    if limit:
        skills = skills[:limit]

    print(f'Reviewing aliases for {len(skills)} skills ({sum(len(s["aliases"]) for s in skills)} total aliases)')

    all_results = []
    flagged = []
    t0 = time.time()

    for i in range(0, len(skills), batch_size):
        batch = skills[i:i + batch_size]
        try:
            results = _review_batch(client, batch, all_names_lower)
            all_results.extend(results)
            for r in results:
                bad = [v for v in r['alias_verdicts'] if not v['keep']]
                if bad:
                    flagged.append({**r, 'alias_verdicts': bad})
        except Exception as e:
            print(f'  batch {i // batch_size} error: {e}')
            continue

        done = min(i + batch_size, len(skills))
        elapsed = time.time() - t0
        total_flagged = sum(
            len([v for v in r['alias_verdicts'] if not v['keep']])
            for r in all_results
        )
        print(f'  {done}/{len(skills)} skills reviewed | {total_flagged} aliases flagged | {elapsed:.0f}s')

    # Summary
    total_keep = sum(
        len([v for v in r['alias_verdicts'] if v['keep']])
        for r in all_results
    )
    total_remove = sum(
        len([v for v in r['alias_verdicts'] if not v['keep']])
        for r in all_results
    )
    flag_counts = {}
    for r in all_results:
        for v in r['alias_verdicts']:
            if not v['keep']:
                flag_counts[v['flag']] = flag_counts.get(v['flag'], 0) + 1

    out = {
        'meta': {
            'skills_reviewed': len(all_results),
            'aliases_reviewed': total_keep + total_remove,
            'keep': total_keep,
            'remove': total_remove,
            'flag_breakdown': flag_counts,
        },
        'flagged': sorted(flagged, key=lambda x: -x['job_count']),
        'all_results': sorted(all_results, key=lambda x: -x['job_count']),
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, 'alias_review.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)

    print(f'\nWrote {out_path}')
    print(f'  keep={total_keep}  remove={total_remove}')
    for flag, cnt in sorted(flag_counts.items(), key=lambda x: -x[1]):
        print(f'    {flag}: {cnt}')
    print(f'\nNext: review data/alias_review.json then run scripts/apply_alias_review.py')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--batch-size', type=int, default=20)
    p.add_argument('--limit', type=int, default=None)
    args = p.parse_args()
    run(args.batch_size, args.limit)


if __name__ == '__main__':
    main()
