"""Promote approved entries from skill_shortlist.json to the skills table.

Reads backend/data/skill_shortlist.json, skips any name already in the taxonomy
(exact or fuzzy), inserts new Skill rows, backfills job_skills from
skill_candidate_jobs, and marks skill_candidates approved.

Run (dry-run first, then --apply):
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/promote_shortlist.py
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/promote_shortlist.py --apply
"""
import json
import os
import sys
from datetime import datetime

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)

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
APPLY = '--apply' in sys.argv

# Canonical name overrides for messy candidate strings
NAME_OVERRIDES = {
    'tools like Burp Suite':                    'Burp Suite',
    'both Product-Led Growth':                  'Product-Led Growth',
    'R/R Shiny advantageous':                   'R Shiny',
    'accordance with IPC-A-620 standards':       'IPC-A-620',
    'using EMR systems':                         'Electronic Medical Records',
    'MITRE':                                     'MITRE ATT&CK',
    'COMSEC requirements':                       'COMSEC',
    'MES/ERP software':                          'MES',
    'Core HCM':                                  'HCM',
    'AML/CFT risks':                             'AML/CFT',
    'SAP/S4 Hana':                               'SAP S/4HANA',
    'optimizing complex queries for performance': 'Query Optimization',
    'BDD/TDD testing approaches':                'BDD/TDD',
    'structured cabling standards':              'Structured Cabling',
}


def main():
    shortlist_path = os.path.join(
        os.path.dirname(scripts_dir), 'data', 'skill_shortlist.json'
    )
    data = json.load(open(shortlist_path))
    all_entries = []
    for cat_entries in data['skills_by_category'].values():
        all_entries.extend(cat_entries)

    with app.app_context():
        taxonomy_set = _build_taxonomy_set(Skill.query.all())
        print(f'Taxonomy: {len(taxonomy_set)} names+aliases\n')

        inserted = 0
        skipped_dup = 0
        new_ids = []
        now = datetime.utcnow()

        for entry in all_entries:
            raw_name = entry['name']
            canonical = NAME_OVERRIDES.get(raw_name, raw_name)
            cat = entry['category'].lower()
            sub = entry.get('subcategory', '')
            aliases = entry.get('aliases', [])
            cid = entry['candidate_id']

            if _is_in_taxonomy(canonical.lower(), taxonomy_set):
                print(f'  SKIP (fuzzy): {canonical!r}')
                if APPLY:
                    db.session.execute(db.text(
                        "UPDATE skill_candidates SET status='rejected', rejected_reason='already_in_taxonomy'"
                        " WHERE id=:cid"
                    ), {'cid': cid})
                skipped_dup += 1
                continue

            # Exact-name guard (catches different casing not caught by fuzzy)
            existing = Skill.query.filter(
                db.func.lower(Skill.name) == canonical.lower()
            ).first()
            if existing:
                print(f'  SKIP (exact): {canonical!r} [id={existing.id}]')
                if APPLY:
                    # Still backfill subcategory if missing
                    if sub and not existing.subcategory:
                        existing.subcategory = sub
                    db.session.execute(db.text(
                        "UPDATE skill_candidates SET status='rejected', rejected_reason='already_in_taxonomy'"
                        " WHERE id=:cid"
                    ), {'cid': cid})
                skipped_dup += 1
                continue

            print(f'  INSERT: {canonical!r}  ({cat} / {sub})  aliases={aliases}')

            if APPLY:
                skill = Skill(
                    name=canonical,
                    category=cat,
                    subcategory=sub if sub else None,
                    aliases=aliases or [],
                    is_verified=True,
                    total_job_count=entry.get('job_count', 0),
                    trending_score=0.0,
                    created_at=now,
                    updated_at=now,
                )
                db.session.add(skill)
                db.session.flush()
                new_ids.append(skill.id)

                # Backfill job_skills from skill_candidate_jobs
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
                for a in aliases:
                    taxonomy_set.add(a.lower())

            inserted += 1

        if APPLY:
            db.session.commit()
            print(f'\n✓ Committed. Inserted {inserted}, skipped {skipped_dup} duplicates.')
            if new_ids:
                print(f'New skill IDs: {new_ids}')
                print(f'First new ID (for backfill): {new_ids[0]}')
                print(f'\nBackfill command:')
                print(f'  DATABASE_URL=\'...\' PYTHONPATH=. venv/bin/python scripts/backfill_skills.py --min-id {new_ids[0]}')
        else:
            print(f'\nDry-run. {inserted} to insert, {skipped_dup} already in taxonomy.')
            print('Pass --apply to execute.')


if __name__ == '__main__':
    main()
