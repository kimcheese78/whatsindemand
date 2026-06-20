"""Apply alias review decisions from alias_review.json.

Removes flagged aliases from skill records. Dry-run by default.

Usage:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/apply_alias_review.py
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/apply_alias_review.py --apply
    ... --min-jobs 1000   # only apply to high-traffic skills first
"""
import argparse
import json
import os
import sys
from datetime import datetime

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Skill

app = create_app()
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    p.add_argument('--min-jobs', type=int, default=0, help='Only touch skills with >= N jobs')
    p.add_argument('--flag', choices=['too_broad', 'duplicate_skill', 'misleading'],
                   help='Only remove aliases with this specific flag')
    args = p.parse_args()

    review_path = os.path.join(DATA_DIR, 'alias_review.json')
    if not os.path.exists(review_path):
        print(f'Not found: {review_path}')
        print('Run scripts/review_aliases.py first.')
        sys.exit(1)

    with open(review_path) as f:
        data = json.load(f)

    flagged = data.get('flagged', [])
    if args.min_jobs:
        flagged = [r for r in flagged if r['job_count'] >= args.min_jobs]
    if args.flag:
        flagged = [
            {**r, 'alias_verdicts': [v for v in r['alias_verdicts'] if v['flag'] == args.flag]}
            for r in flagged
        ]
        flagged = [r for r in flagged if r['alias_verdicts']]

    print(f'Alias removals to apply: {sum(len(r["alias_verdicts"]) for r in flagged)} '
          f'across {len(flagged)} skills')
    if args.min_jobs:
        print(f'  (filtered to skills with >= {args.min_jobs} jobs)')
    if args.flag:
        print(f'  (filtered to flag: {args.flag})')
    print()

    with app.app_context():
        now = datetime.utcnow()
        total_removed = 0

        for r in sorted(flagged, key=lambda x: -x['job_count']):
            skill = Skill.query.get(r['skill_id'])
            if not skill:
                print(f'  MISSING id={r["skill_id"]}')
                continue

            current = list(skill.aliases or [])
            to_remove = {v['alias'].lower() for v in r['alias_verdicts']}
            new_aliases = [a for a in current if a.lower() not in to_remove]
            removed = [a for a in current if a.lower() in to_remove]

            if not removed:
                continue

            print(f'  [{r["skill_id"]:5d}] {skill.name} (jobs={r["job_count"]:,})')
            for v in r['alias_verdicts']:
                print(f'    - remove "{v["alias"]}"  [{v["flag"]}]  {v["reason"]}')

            if args.apply:
                skill.aliases = new_aliases
                skill.updated_at = now
                total_removed += len(removed)

        if args.apply:
            db.session.commit()
            print(f'\n✓ Committed. Removed {total_removed} aliases.')
        else:
            total = sum(len(r['alias_verdicts']) for r in flagged)
            print(f'\nDry-run. {total} aliases would be removed. Pass --apply to execute.')


if __name__ == '__main__':
    main()
