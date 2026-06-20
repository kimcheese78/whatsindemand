"""
Re-map title variations (and their jobs) out of Software Engineer:
  - Mobile-tagged titles  → Mobile Engineer
  - Salesforce-tagged titles → Salesforce Administrator

Dry-run by default; pass --apply to commit.
"""
import os, sys

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

from app import create_app
from app.models import Role, RoleTitleVariation, Job, db
from sqlalchemy import func

APPLY = '--apply' in sys.argv

SE_ID   = 3328
MOB_ID  = 68
SF_ID   = 4347

MOBILE_KEYWORDS = [
    'android', 'ios', 'mobile', 'flutter', 'react native',
    'swift ', 'kotlin', 'iphone', 'ipad',
]
MOBILE_EXCLUSIONS = [
    'mobile building', 'mobile home', 'mobile unit', 'mobile crane',
    'mobile clinic', 'mobile notary', 'mobile lab',
]
SALESFORCE_KEYWORDS = [
    'salesforce', 'sfdc', 'apex developer', 'apex engineer',
]

def matches(title, keywords, exclusions=None):
    t = title.lower()
    if exclusions and any(e in t for e in exclusions):
        return False
    return any(k in t for k in keywords)

app = create_app()
with app.app_context():
    se_vars = db.session.query(RoleTitleVariation).filter_by(role_id=SE_ID).all()

    mobile_vars    = [v for v in se_vars if matches(v.original_title, MOBILE_KEYWORDS, MOBILE_EXCLUSIONS)]
    salesforce_vars = [v for v in se_vars if matches(v.original_title, SALESFORCE_KEYWORDS)]

    print(f'Mobile variations to move to Mobile Engineer ({MOB_ID}): {len(mobile_vars)}')
    for v in sorted(mobile_vars, key=lambda x: -x.frequency):
        print(f'  {v.frequency:4d}  {v.original_title}')

    print()
    print(f'Salesforce variations to move to Salesforce Administrator ({SF_ID}): {len(salesforce_vars)}')
    for v in sorted(salesforce_vars, key=lambda x: -x.frequency):
        print(f'  {v.frequency:4d}  {v.original_title}')

    # Count affected jobs
    mobile_titles    = [v.original_title for v in mobile_vars]
    salesforce_titles = [v.original_title for v in salesforce_vars]

    mob_jobs = db.session.query(func.count(Job.id)).filter(
        Job.role_id == SE_ID, Job.title.in_(mobile_titles)
    ).scalar()
    sf_jobs = db.session.query(func.count(Job.id)).filter(
        Job.role_id == SE_ID, Job.title.in_(salesforce_titles)
    ).scalar()

    print()
    print(f'Jobs that will move → Mobile Engineer:          {mob_jobs:,}')
    print(f'Jobs that will move → Salesforce Administrator: {sf_jobs:,}')

    if not APPLY:
        print('\nDry run. Pass --apply to commit.')
        sys.exit(0)

    print('\nApplying...')

    # Re-map variations
    for v in mobile_vars:
        v.role_id = MOB_ID
    for v in salesforce_vars:
        v.role_id = SF_ID
    db.session.flush()

    # Re-map jobs
    if mobile_titles:
        db.session.query(Job).filter(
            Job.role_id == SE_ID, Job.title.in_(mobile_titles)
        ).update({'role_id': MOB_ID}, synchronize_session=False)

    if salesforce_titles:
        db.session.query(Job).filter(
            Job.role_id == SE_ID, Job.title.in_(salesforce_titles)
        ).update({'role_id': SF_ID}, synchronize_session=False)

    db.session.flush()

    # Recompute total_active_jobs for the three affected roles
    for role_id in [SE_ID, MOB_ID, SF_ID]:
        active_count = db.session.query(func.count(Job.id)).filter(
            Job.role_id == role_id, Job.is_active == True
        ).scalar()
        db.session.query(Role).filter_by(id=role_id).update(
            {'total_active_jobs': active_count}
        )
        role = db.session.query(Role).get(role_id)
        print(f'  {role.normalized_title}: {active_count:,} active jobs')

    db.session.commit()
    print('Done.')
