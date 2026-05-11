"""
Backfill role_candidates with all job titles that have no role_id assigned.

Skips titles already in role_candidates and known placeholder titles.
Run: PYTHONPATH=. venv/bin/python scripts/backfill_role_candidates.py [--dry-run]
"""
import sys
import os
from datetime import date
from collections import Counter

sys.path.insert(0, os.getcwd())
from app import create_app
from app.models import db, Job, RoleCandidate

PLACEHOLDER_KEYWORDS = [
    "don't see what you're looking for",
    "future opportunities",
    "general interest",
    "talent pool",
    "candidate pool",
    "expression of interest",
    "join our talent network",
]

DRY_RUN = '--dry-run' in sys.argv


def is_placeholder(title: str) -> bool:
    t = title.lower().replace('’', "'").replace('‘', "'")
    return any(kw in t for kw in PLACEHOLDER_KEYWORDS)


def main():
    app = create_app()
    with app.app_context():
        # Get all unique titles with no role_id
        rows = db.session.execute(db.text('''
            SELECT title, COUNT(*) as job_count,
                   COUNT(DISTINCT company_id) as company_count,
                   MIN(scraped_at::date) as first_seen,
                   MAX(scraped_at::date) as last_seen
            FROM jobs
            WHERE role_id IS NULL AND title IS NOT NULL AND title != ''
            GROUP BY title
            ORDER BY job_count DESC
        ''')).all()

        # Get existing role_candidate titles
        existing = {
            rc.raw_title for rc in RoleCandidate.query.with_entities(RoleCandidate.raw_title).all()
        }

        stats = Counter()
        today = date.today()

        for row in rows:
            title = row.title.strip()

            if is_placeholder(title):
                stats['placeholder'] += 1
                continue

            if title in existing:
                stats['already_exists'] += 1
                continue

            stats['to_insert'] += 1
            if DRY_RUN:
                print(f'  [{row.job_count:3d} jobs]  {title}')
                continue

            db.session.execute(db.text('''
                INSERT INTO role_candidates (raw_title, job_count, company_count, first_seen, last_seen, status)
                VALUES (:title, :job_count, :company_count, :first_seen, :last_seen, 'pending')
                ON CONFLICT (raw_title) DO NOTHING
            '''), {
                'title': title,
                'job_count': row.job_count,
                'company_count': row.company_count,
                'first_seen': row.first_seen,
                'last_seen': row.last_seen,
            })

        if not DRY_RUN:
            db.session.commit()

        print(f'\nResults:')
        print(f'  Already in role_candidates: {stats["already_exists"]}')
        print(f'  Placeholders skipped:       {stats["placeholder"]}')
        print(f'  {"Would insert" if DRY_RUN else "Inserted"}:                  {stats["to_insert"]}')
        total = db.session.execute(db.text('SELECT COUNT(*) FROM role_candidates WHERE status = \'pending\'')).scalar()
        print(f'  Total pending candidates:   {total}')


if __name__ == '__main__':
    main()
