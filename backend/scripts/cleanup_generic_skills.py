"""Unverify generic Lightcast skills that cause false positives in extraction.

Reversible: sets is_verified=False instead of deleting. Re-run with --restore to
revert (sets is_verified=True for rows it previously touched, scoped by the
same name/category filters).

Run: python scripts/cleanup_generic_skills.py           # dry run
     python scripts/cleanup_generic_skills.py --apply
     python scripts/cleanup_generic_skills.py --restore
"""
import sys

from app import create_app
from app.models import db, Skill

APPLY = '--apply' in sys.argv
RESTORE = '--restore' in sys.argv

# Whole categories whose members are inherent traits, not JD skills.
CATEGORY_SKIPLIST = {
    'Physical and Inherent Abilities',
}

# Individual generic names to unverify (case-insensitive).
NAME_SKIPLIST = {
    # overly generic functions / nouns
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
    # soft/interpersonal
    'hospitality', 'cooperation', 'coordinating', 'collections',
    # already in Lightcast-generic set
    'sales',
}


def main():
    app = create_app()
    with app.app_context():
        q = Skill.query.filter(
            db.or_(
                Skill.category.in_(CATEGORY_SKIPLIST),
                db.func.lower(Skill.name).in_(NAME_SKIPLIST),
            )
        )

        if RESTORE:
            targets = q.filter(Skill.is_verified == False).all()
            print(f'RESTORE: {len(targets)} rows would be re-verified')
            for s in targets[:20]:
                print(f'  {s.name!r:35s} [{s.category}]')
            if APPLY:
                for s in targets:
                    s.is_verified = True
                db.session.commit()
                print(f'Restored {len(targets)} skills.')
            return

        targets = q.filter(Skill.is_verified == True).all()
        by_cat = {}
        for s in targets:
            by_cat.setdefault(s.category, []).append(s.name)

        print(f'Total verified skills: {Skill.query.filter_by(is_verified=True).count()}')
        print(f'Rows to unverify: {len(targets)}')
        for cat, names in sorted(by_cat.items(), key=lambda x: -len(x[1])):
            print(f'  [{cat}] ({len(names)})')
            for n in sorted(names):
                print(f'     {n}')

        if APPLY:
            for s in targets:
                s.is_verified = False
            db.session.commit()
            print(f'\nUnverified {len(targets)} skills.')
            print(f'New verified count: {Skill.query.filter_by(is_verified=True).count()}')
        else:
            print('\nDry run. Re-run with --apply to persist.')


if __name__ == '__main__':
    main()
