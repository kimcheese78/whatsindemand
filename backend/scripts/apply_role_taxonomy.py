"""
Apply full role taxonomy cleanup:
  - Merges: move variations + jobs from source → target, delete source
  - Category moves
  - Pure removes (0-job roles)

Dry-run by default; pass --apply to commit.
"""
import os, sys

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)

from app import create_app
from app.models import Role, RoleTitleVariation, Job, db
from sqlalchemy import func

APPLY = '--apply' in sys.argv

# (source_title, target_title)
MERGES = [
    # Security Engineering
    ('Application Security Engineer',   'Security Engineer'),
    ('Product Security Engineer',        'Security Engineer'),
    ('Information Security Engineer',    'Security Engineer'),
    ('Enterprise Security Engineer',     'Security Engineer'),
    ('Threat Specialist',                'Security Engineer'),
    ('Security Operations Engineer',     'Security Operations Analyst'),
    # Engineering misc
    ('Applied AI Engineer',              'AI Engineer'),
    ('AI Infrastructure Engineer',       'Platform Engineer'),
    ('Resident Solutions Architect',     'Solutions Architect'),
    ('Partner Solutions Architect',      'Solutions Architect'),
    ('Sales Engineer',                   'Solutions Engineer'),
    ('Deployment Strategist',            'Implementation Consultant'),
    # Sales
    ('Commercial Account Executive',     'Mid-Market Account Executive'),
    ('Major Account Executive',          'Enterprise Account Executive'),
    ('Corporate Account Executive',      'Account Executive'),
    ('Territory Account Executive',      'Account Executive'),
    ('Business Development Representative', 'Sales Development Representative'),
    ('Revenue Strategy & Operations Lead',  'Revenue Operations Manager'),
    ('Deal Operations Analyst',          'Deal Desk Analyst'),
    ('Field Enablement Manager',         'Sales Enablement Manager'),
    ('Enterprise Account Manager',       'Account Manager'),
    # People / HR
    ('People Partner',                   'HR Business Partner'),
    ('People Business Partner',          'HR Business Partner'),
    ('HR Manager',                       'HR Generalist'),
    ('Talent Acquisition Specialist',    'Recruiter'),
    ('Technical Recruiter',              'Recruiter'),
    ('Talent Manager',                   'Recruiter'),
    ('Partner Development Manager',      'Partner Manager'),
    # Customer Success
    ('Mid-Market Customer Success Manager', 'Customer Success Manager'),
    ('Renewals Manager',                 'Customer Success Manager'),
    ('AI Success Manager',               'Technical Success Manager'),
    ('Product Support Engineer',         'Technical Support Engineer'),
    # Legal
    ('Attorney',                         'Legal Counsel'),
    ('Corporate Counsel',                'Legal Counsel'),
    ('Associate General Counsel',        'Legal Counsel'),
    ('Contracts Negotiator',             'Contracts Manager'),
    ('Product Paralegal',                'Paralegal'),
    ('Legal Assistant',                  'Paralegal'),
    # Design
    ('UX Designer',                      'Product Designer'),
    ('Director of Design',               'Design Director'),
    # Finance
    ('Equity Program Manager',           'Stock Plan Administrator'),
    # IT / Operations
    ('Business Systems Engineer',        'Business Systems Analyst'),
    # Remove-with-target (tiny roles)
    ('Forward Deployed Data Scientist',  'Data Scientist'),
    ('Ocean Operations Associate',       'Operations Manager'),
    ('Trade Advisory Lead',              'Supply Chain Analyst'),
]

# (role_title, new_category)
CATEGORY_MOVES = [
    ('Technical Writer',        'Product'),
    ('Scrum Master',            'Product'),
    ('GTM Engineer',            'Sales'),
    ('Leasing Consultant',      'Real Estate'),
    ('Bartender',               'Retail / Hospitality'),
    ('Business Systems Analyst','IT'),
    ('Partner Sales Manager',   'Partnerships'),
]

# Pure removes — must have 0 jobs after merges above
PURE_REMOVES = [
    'Strategic Growth Partner',
    'Stylist',
]


def resolve(name):
    r = db.session.query(Role).filter_by(normalized_title=name).first()
    if r is None:
        print(f'  WARNING: role not found: {name!r}')
    return r


app = create_app()
with app.app_context():
    affected_role_ids = set()
    merge_stats = []   # (src, tgt, var_count, job_count)
    move_stats  = []
    remove_stats = []

    # ── MERGES ──────────────────────────────────────────────────────────────
    for src_name, tgt_name in MERGES:
        src = resolve(src_name)
        tgt = resolve(tgt_name)
        if src is None or tgt is None:
            continue

        src_vars = db.session.query(RoleTitleVariation).filter_by(role_id=src.id).all()
        job_count = db.session.query(func.count(Job.id)).filter_by(role_id=src.id).scalar()

        var_moved = 0
        var_merged = 0
        for v in src_vars:
            existing = db.session.query(RoleTitleVariation).filter_by(
                role_id=tgt.id, original_title=v.original_title
            ).first()
            if existing:
                # absorb frequency into existing, drop duplicate
                if APPLY:
                    existing.frequency = (existing.frequency or 0) + (v.frequency or 0)
                    db.session.delete(v)
                var_merged += 1
            else:
                if APPLY:
                    v.role_id = tgt.id
                var_moved += 1

        if APPLY and job_count:
            db.session.query(Job).filter_by(role_id=src.id).update(
                {'role_id': tgt.id}, synchronize_session=False
            )

        merge_stats.append((src_name, tgt_name, var_moved + var_merged, job_count))
        affected_role_ids.add(src.id)
        affected_role_ids.add(tgt.id)

    # ── CATEGORY MOVES ──────────────────────────────────────────────────────
    for role_name, new_cat in CATEGORY_MOVES:
        r = resolve(role_name)
        if r is None:
            continue
        old_cat = r.category
        if APPLY:
            r.category = new_cat
        move_stats.append((role_name, old_cat, new_cat))

    # ── FLUSH before deletes ─────────────────────────────────────────────────
    if APPLY:
        db.session.flush()

    # ── DELETE merged source roles ────────────────────────────────────────────
    if APPLY:
        for src_name, _, _, _ in merge_stats:
            src = db.session.query(Role).filter_by(normalized_title=src_name).first()
            if src is None:
                continue
            remaining_jobs = db.session.query(func.count(Job.id)).filter_by(role_id=src.id).scalar()
            remaining_vars = db.session.query(func.count(RoleTitleVariation.id)).filter_by(role_id=src.id).scalar()
            if remaining_jobs == 0 and remaining_vars == 0:
                # Clear any unmatched_titles references before delete
                db.session.execute(
                    db.text('UPDATE unmatched_titles SET mapped_role_id = NULL WHERE mapped_role_id = :rid'),
                    {'rid': src.id}
                )
                db.session.delete(src)
            else:
                print(f'  SKIP DELETE {src_name!r}: still has {remaining_jobs} jobs / {remaining_vars} vars')

    # ── PURE REMOVES ─────────────────────────────────────────────────────────
    for role_name in PURE_REMOVES:
        r = resolve(role_name)
        if r is None:
            continue
        job_count = db.session.query(func.count(Job.id)).filter_by(role_id=r.id).scalar()
        var_count = db.session.query(func.count(RoleTitleVariation.id)).filter_by(role_id=r.id).scalar()
        remove_stats.append((role_name, job_count, var_count))
        if APPLY:
            if job_count > 0:
                print(f'  SKIP REMOVE {role_name!r}: still has {job_count} jobs — re-map first')
            else:
                db.session.execute(
                    db.text('UPDATE unmatched_titles SET mapped_role_id = NULL WHERE mapped_role_id = :rid'),
                    {'rid': r.id}
                )
                db.session.query(RoleTitleVariation).filter_by(role_id=r.id).delete()
                db.session.delete(r)

    # ── RECOMPUTE total_active_jobs ──────────────────────────────────────────
    if APPLY:
        db.session.flush()
        for role_id in affected_role_ids:
            role = db.session.query(Role).get(role_id)
            if role is None:
                continue
            active = db.session.query(func.count(Job.id)).filter(
                Job.role_id == role_id, Job.is_active == True
            ).scalar()
            role.total_active_jobs = active

        db.session.commit()

    # ── REPORT ───────────────────────────────────────────────────────────────
    print(f'\n{"=== DRY RUN ===" if not APPLY else "=== APPLIED ==="}\n')

    print(f'MERGES ({len(merge_stats)}):')
    for src, tgt, vars_, jobs in merge_stats:
        print(f'  {src:45s} → {tgt}  ({vars_} vars, {jobs} jobs)')

    print(f'\nCATEGORY MOVES ({len(move_stats)}):')
    for name, old, new in move_stats:
        print(f'  [{old}] → [{new}]  {name}')

    print(f'\nPURE REMOVES ({len(remove_stats)}):')
    for name, jobs, vars_ in remove_stats:
        print(f'  {name}  ({jobs} jobs, {vars_} vars)')

    if not APPLY:
        print('\nDry run. Pass --apply to commit.')
