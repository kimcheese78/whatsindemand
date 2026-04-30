"""Collapse the 31 Lightcast top-level categories + legacy lowercase labels
down to the three big buckets: Technical / Soft / Domain.

Run: PYTHONPATH=. python3 scripts/recategorize_skills.py           # dry run
     PYTHONPATH=. python3 scripts/recategorize_skills.py --apply
     PYTHONPATH=. python3 scripts/recategorize_skills.py --restore  # undo (if backup exists)
"""
import json
import os
import sys
from collections import Counter

from app import create_app
from app.models import db, Skill

APPLY = '--apply' in sys.argv
RESTORE = '--restore' in sys.argv
BACKUP_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'skill_category_backup.json')

CATEGORY_MAP = {
    # Legacy lowercase -> canonical case
    'technical': 'Technical',
    'soft': 'Soft',
    'domain': 'Domain',

    # Technical
    'Information Technology Category': 'Technical',
    'Engineering': 'Technical',
    'Analysis': 'Technical',
    'Science and Research': 'Technical',
    'Design': 'Technical',
    'Manufacturing and Production': 'Technical',
    'Architecture and Construction': 'Technical',
    'Maintenance, Repair, and Facility Services': 'Technical',
    'Energy and Utilities': 'Technical',
    'Agriculture, Horticulture, and Landscaping': 'Technical',

    # Soft
    'Language': 'Soft',
    'Customer and Client Support': 'Soft',
    'Performing Arts': 'Soft',

    # Domain
    'Health Care': 'Domain',
    'Finance Subcategory': 'Domain',
    'Business': 'Domain',
    'Marketing and Public Relations': 'Domain',
    'Media and Writing': 'Domain',
    'Human Resources': 'Domain',
    'Sales Category': 'Domain',
    'Law, Regulation, and Compliance': 'Domain',
    'Education and Training': 'Domain',
    'Economics, Policy, and Social Studies': 'Domain',
    'Environment': 'Domain',
    'Hospitality and Food Services': 'Domain',
    'Property and Real Estate': 'Domain',
    'Public Safety and National Security': 'Domain',
    'Social and Human Services': 'Domain',
    'Transportation, Supply Chain, and Logistics': 'Domain',
    'Administration': 'Domain',

    # Skiplisted — leave unverified, don't relabel
    # 'Physical and Inherent Abilities': keep as-is
}


def main():
    app = create_app()
    with app.app_context():
        if RESTORE:
            if not os.path.exists(BACKUP_PATH):
                print(f'No backup at {BACKUP_PATH}')
                return
            with open(BACKUP_PATH) as f:
                backup = json.load(f)
            restored = 0
            for row in backup:
                s = Skill.query.get(row['id'])
                if s and s.category != row['category']:
                    s.category = row['category']
                    restored += 1
            db.session.commit()
            print(f'Restored {restored} rows from backup.')
            return

        skills = Skill.query.all()
        migrations = Counter()      # (old -> new) -> n
        unmapped = Counter()        # categories we don't have a mapping for
        backup = []
        changes = []                # list[(id, new_cat)]

        for s in skills:
            old = s.category
            if old in CATEGORY_MAP:
                new = CATEGORY_MAP[old]
                if new != old:
                    migrations[(old, new)] += 1
                    backup.append({'id': s.id, 'category': old})
                    changes.append((s.id, new))
            elif old:
                unmapped[old] += 1

        print(f'Skills scanned: {len(skills)}')
        print(f'Changing: {len(changes)}')
        print(f'Unmapped categories (left as-is): {sum(unmapped.values())} across {len(unmapped)} categories')

        print('\n=== Top migrations (old -> new) ===')
        for (o, n), cnt in migrations.most_common(40):
            print(f'  {o:<50} -> {n:<12} {cnt:>6}')

        if unmapped:
            print('\n=== Unmapped (no change) ===')
            for cat, cnt in unmapped.most_common():
                print(f'  {cat:<50} {cnt:>6}')

        if APPLY:
            os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
            with open(BACKUP_PATH, 'w') as f:
                json.dump(backup, f)
            print(f'\nBackup written: {BACKUP_PATH} ({len(backup)} rows)')

            print('Applying...')
            CHUNK = 1000
            for i in range(0, len(changes), CHUNK):
                batch = changes[i:i + CHUNK]
                values = ','.join(f'({jid},:c{k})' for k, (jid, _) in enumerate(batch))
                params = {f'c{k}': new for k, (_, new) in enumerate(batch)}
                sql = f"""
                    UPDATE skills SET category = v.c
                    FROM (VALUES {values}) AS v(id, c)
                    WHERE skills.id = v.id
                """
                db.session.execute(db.text(sql), params)
                db.session.commit()
                print(f'  committed {min(i + CHUNK, len(changes))}/{len(changes)}')

            print(f'Done. Updated {len(changes)} rows.')
        else:
            print('\n(Dry run. Use --apply to write, or --restore to undo after a previous apply.)')


if __name__ == '__main__':
    main()
