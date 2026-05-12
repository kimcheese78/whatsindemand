"""
Add 4 new canonical roles to the roles table.

Run: PYTHONPATH=. venv/bin/python scripts/add_new_roles.py
"""
import sys, os
sys.path.insert(0, os.getcwd())

NEW_ROLES = [
    {
        'normalized_title': 'Developer Relations Engineer',
        'category': 'Engineering',
        'job_family': 'Developer Relations',
        'seniority_level': None,
    },
    {
        'normalized_title': 'Learning & Development Manager',
        'category': 'People',
        'job_family': 'Learning & Development',
        'seniority_level': None,
    },
    {
        'normalized_title': 'Game Designer',
        'category': 'Design',
        'job_family': 'Game Design',
        'seniority_level': None,
    },
    {
        'normalized_title': 'Trader',
        'category': 'Finance',
        'job_family': 'Trading',
        'seniority_level': None,
    },
]


def main():
    from app import create_app
    from app.models import db, Role

    app = create_app()
    with app.app_context():
        for r in NEW_ROLES:
            existing = Role.query.filter_by(normalized_title=r['normalized_title']).first()
            if existing:
                print(f"  ⚠️  Already exists: {r['normalized_title']}")
                continue
            role = Role(
                normalized_title=r['normalized_title'],
                category=r['category'],
                job_family=r['job_family'],
                seniority_level=r['seniority_level'],
                total_active_jobs=0,
            )
            db.session.add(role)
            print(f"  ✅ Created: {r['normalized_title']}  ({r['category']} / {r['job_family']})")

        db.session.commit()
        print(f"\nDone. Total roles now: {Role.query.count()}")


if __name__ == '__main__':
    main()
