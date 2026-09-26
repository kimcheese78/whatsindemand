"""Print the live counts behind the site's hardcoded marketing metrics.

Read-only. Run against prod:

    cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/current_metrics.py

Used to sanity-check the "3,300+ companies / 100,000+ postings / 5,700+ skills"
claims in frontend/src/App.js and backend/app/routes/public.py.
"""
from sqlalchemy import func

from app import create_app
from app.models import db, Company, Job, Skill, Role

# Keep in sync with public.py's MIN_JOBS_FOR_PAGE (the /r/ index gate).
MIN_JOBS_FOR_PAGE = 3


def _floor_hundreds(n):
    return (n // 100) * 100


def _floor_thousands(n):
    return (n // 1000) * 1000


def main():
    app = create_app()
    with app.app_context():
        def count(col, *filters):
            q = db.session.query(func.count(col))
            for f in filters:
                q = q.filter(f)
            return q.scalar()

        companies_total = count(Company.id)
        companies_active = count(Company.id, Company.is_active.is_(True))
        companies_scrape = count(Company.id, Company.scrape_enabled.is_(True))

        jobs_total = count(Job.id)
        jobs_active = count(Job.id, Job.is_active.is_(True))

        skills_verified = count(Skill.id, Skill.is_verified.is_(True))

        roles_pages = count(Role.id, Role.total_active_jobs >= MIN_JOBS_FOR_PAGE)

    print("=== Companies ===")
    print(f"  total          : {companies_total:,}")
    print(f"  is_active       : {companies_active:,}")
    print(f"  scrape_enabled  : {companies_scrape:,}")
    print()
    print("=== Jobs ===")
    print(f"  total          : {jobs_total:,}")
    print(f"  is_active       : {jobs_active:,}")
    print()
    print("=== Skills ===")
    print(f"  is_verified     : {skills_verified:,}")
    print()
    print("=== Role pages (/r/) ===")
    print(f"  total_active_jobs >= {MIN_JOBS_FOR_PAGE}: {roles_pages:,}")
    print()
    print("=== Suggested marketing copy (rounded DOWN so claims stay true) ===")
    print(f"  companies  : {_floor_hundreds(companies_scrape):,}+  (currently reads 3,300+)")
    print(f"  postings   : {_floor_thousands(jobs_active):,}+  (currently reads 100,000+)")
    print(f"  skills     : {_floor_hundreds(skills_verified):,}+  (currently reads 5,700+)")


if __name__ == '__main__':
    main()
