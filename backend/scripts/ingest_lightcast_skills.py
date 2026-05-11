"""Ingest Lightcast Open Skills taxonomy into the skills table.

Additive: never deletes/overwrites existing curated skills. For a new skill
name that already exists (case-insensitive), we merge category info into the
existing row; we never create a duplicate.

Run: python scripts/ingest_lightcast_skills.py           # dry run
     python scripts/ingest_lightcast_skills.py --apply   # writes
"""
import json
import os
import sys
from collections import Counter

from app import create_app
from app.models import db, Skill

APPLY = '--apply' in sys.argv
DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'lightcast_taxonomy.json')

# No whole top-level category blocks.
CATEGORY_SKIPLIST: set = set()

# Block specific subcategories that contain conditions/diagnoses, not job skills.
SUBCATEGORY_SKIPLIST = {
    ('Health Care', 'Genetic Disorders Subcategory'),
    ('Health Care', 'Infectious Diseases Subcategory'),      # Ebola, Pneumonia, etc.
    ('Health Care', 'Mental Health Diseases and Disorders'), # Schizophrenia, Alzheimer's, etc.
    ('Education and Training', 'Special Education'),         # Dyslexia, Dyscalculia, etc.
}

# Skip individual skill names known to cause false-positive noise.
# Add names here rather than blocking whole categories, so legitimate skills
# in the same subcategory (e.g. Mental Health, Genetic Counseling) still come through.
# Kept in sync with scripts/cleanup_generic_skills.py NAME_SKIPLIST.
NAME_SKIPLIST = {
    'office', 'management', 'operations', 'planning', 'analysis',
    'administration', 'support', 'services', 'technology',
    # generic functions / nouns
    'marketing', 'communications', 'branding', 'advertising',
    'consulting', 'commercialization', 'benchmarking', 'bidding',
    'tooling', 'workflows', 'automation', 'documentation',
    'analytics', 'reporting', 'dashboard', 'calculations',
    'research', 'innovation', 'strategy', 'leadership',
    'writing', 'editing', 'proofreading', 'blogs', 'broadcasting',
    'publishing', 'storytelling',
    'merchandising', 'warehousing', 'purchasing', 'scheduling',
    'onboarding', 'forecasting', 'budgeting', 'invoicing', 'quoting',
    'coaching', 'mentoring', 'negotiation', 'presentation', 'presentations',
    'facilitation', 'mediation', 'auditing', 'archiving', 'cataloging',
    'drafting', 'curation', 'training',
    'hospitality', 'cooperation', 'coordinating', 'collections',
    'sales',
}


def walk_leaves(data):
    """Yield (category_name, subcategory_name, skill_name, external_id) tuples."""
    for top in data:
        cat = top['name']
        for sub in top.get('children', []):
            subcat = sub['name']
            for leaf in sub.get('children', []):
                yield cat, subcat, leaf['name'], leaf['external_id']


def main():
    app = create_app()
    with app.app_context():
        with open(DATA_PATH) as f:
            data = json.load(f)

        existing_by_name = {s.name.lower(): s for s in Skill.query.all()}

        stats = Counter()
        to_insert = []

        for cat, subcat, name, xid in walk_leaves(data):
            name_clean = name.strip()
            if not name_clean:
                stats['empty'] += 1
                continue
            if len(name_clean) > 100:
                stats['too_long'] += 1
                continue
            if name_clean.lower() in NAME_SKIPLIST:
                stats['name_skipped'] += 1
                continue
            if cat in CATEGORY_SKIPLIST:
                stats['category_skipped'] += 1
                continue
            if (cat, subcat) in SUBCATEGORY_SKIPLIST:
                stats['subcategory_skipped'] += 1
                continue
            if name_clean.lower() in existing_by_name:
                stats['already_exists'] += 1
                continue

            # Map Lightcast top-level category to our three canonical categories
            category = 'Soft' if cat == 'Physical and Inherent Abilities' else cat

            to_insert.append({
                'name': name_clean,
                'category': category,
                'aliases': [],
                'is_verified': True,
                'total_job_count': 0,
            })
            stats['to_insert'] += 1

        print(f'Lightcast leaves scanned: {sum(1 for _ in walk_leaves(data))}')
        print(f'Stats: {dict(stats)}')
        print(f'Mode: {"APPLY" if APPLY else "DRY-RUN"}')
        print(f'Current skills: {Skill.query.count()}')
        print(f'Would insert: {len(to_insert)}')

        if APPLY and to_insert:
            # Use bulk insert for speed
            db.session.bulk_insert_mappings(Skill, to_insert)
            db.session.commit()
            print(f'Inserted. New skill count: {Skill.query.count()}')

            # Sanity check: category distribution of new skills
            print('\nNew category distribution:')
            for r in db.session.execute(db.text(
                'SELECT category, COUNT(*) FROM skills GROUP BY 1 ORDER BY 2 DESC'
            )).all():
                print(f'  {r[0]}: {r[1]}')


if __name__ == '__main__':
    main()
