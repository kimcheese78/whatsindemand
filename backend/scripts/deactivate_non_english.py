"""Deactivate jobs whose description is non-English.

Detection heuristic: non-ASCII byte ratio of description_text.
  > 5%  → always non-English (CJK, clearly European foreign language)
  2-5%  → non-English if location_country is outside English-speaking countries
            (catches Hungarian, Brazilian Portuguese, Swedish, French, etc.
             without false-positiving on English jobs that have emojis or HTML)

Dry-run by default. Pass --apply to commit.

Usage:
    cd backend
    DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/deactivate_non_english.py
    DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/deactivate_non_english.py --apply
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db

APPLY = '--apply' in sys.argv

ENGLISH_COUNTRIES = {
    'United States', 'US', 'USA', 'U.S.', 'U.S.A.',
    'United Kingdom', 'UK', 'England', 'Scotland', 'Wales',
    'Canada',
    'Australia',
    'New Zealand',
    'Ireland',
    'Remote',
    'remote',
}


def run():
    app = create_app()
    with app.app_context():
        # Tier 1: clearly non-English (>5% non-ASCII bytes) — all countries
        tier1 = db.session.execute(db.text('''
            SELECT id, title, location_country,
                   round((octet_length(description_text) - length(description_text)) * 100.0
                         / octet_length(description_text), 1) AS pct
            FROM jobs
            WHERE is_active = TRUE
              AND description_text IS NOT NULL
              AND length(description_text) > 100
              AND (octet_length(description_text) - length(description_text)) * 100.0
                  / octet_length(description_text) > 5
            ORDER BY pct DESC
        ''')).fetchall()

        # Tier 2: borderline (2-5%) from non-English-speaking countries
        # Build the NOT IN list as literals to avoid psycopg3 tuple binding issue
        ec_list = ', '.join(f"'{c}'" for c in ENGLISH_COUNTRIES)
        tier2 = db.session.execute(db.text(f'''
            SELECT id, title, location_country,
                   round((octet_length(description_text) - length(description_text)) * 100.0
                         / octet_length(description_text), 1) AS pct
            FROM jobs
            WHERE is_active = TRUE
              AND description_text IS NOT NULL
              AND length(description_text) > 100
              AND (octet_length(description_text) - length(description_text)) * 100.0
                  / octet_length(description_text) BETWEEN 2 AND 5
              AND location_country IS NOT NULL
              AND location_country NOT IN ({ec_list})
            ORDER BY pct DESC
        ''')).fetchall()

        all_jobs = list(tier1) + list(tier2)
        ids = [r.id for r in all_jobs]

        print(f'Mode: {"APPLY" if APPLY else "DRY RUN"}')
        print(f'Tier 1 (>5% non-ASCII, any country): {len(tier1):,}')
        print(f'Tier 2 (2-5%, non-English country):  {len(tier2):,}')
        print(f'Total to deactivate:                 {len(all_jobs):,}')

        print(f'\nSample (first 30):')
        for r in all_jobs[:30]:
            print(f'  {r.pct:5.1f}%  {(r.location_country or ""):15s}  {r.title[:60]}')

        if not ids:
            print('Nothing to deactivate.')
            return

        if APPLY:
            db.session.execute(
                db.text('UPDATE jobs SET is_active = FALSE WHERE id = ANY(:ids)'),
                {'ids': ids}
            )
            db.session.commit()
            print(f'\nDeactivated {len(ids):,} jobs.')
        else:
            print(f'\nRe-run with --apply to deactivate {len(ids):,} jobs.')


if __name__ == '__main__':
    run()
