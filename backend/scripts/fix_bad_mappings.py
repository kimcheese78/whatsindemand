"""
Fix bad title-to-role mappings in Operations Manager, Solutions Consultant, Legal Counsel.

Strategy:
  - Solutions Consultant / Legal Counsel: targeted re-map by pattern
  - Operations Manager: blacklist approach — explicitly wrong categories get
    re-mapped or nulled; everything else stays

Dry-run by default; pass --apply to commit.
"""
import os, sys

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)

from app import create_app
from app.models import Role, RoleTitleVariation, Job, db
from sqlalchemy import func

APPLY = '--apply' in sys.argv


def role_id(name):
    r = db.session.query(Role).filter_by(normalized_title=name).first()
    if r is None:
        raise ValueError(f'Role not found: {name!r}')
    return r.id


def matches(title, patterns):
    t = title.lower()
    return any(p in t for p in patterns)


# ── SOLUTIONS CONSULTANT ─────────────────────────────────────────────────────
# (patterns, target_role_name_or_None)
SC_RULES = [
    (['leasing consultant', 'leasing associate', 'senior leasing'],
     'Leasing Consultant'),
    (['physical therapist', 'occupational therapist', 'physical / occupational',
      'physical/occupational', 'pt consultant', 'ot consultant',
      'physical & occupational', 'physical and occupational'],
     None),   # split PT/OT — null for now, they'll surface as unmatched
    (['wealth advisor', 'wealth management advisor', 'associate wealth advisor'],
     'Financial Analyst'),
    (['new home sales', 'automotive sales consultant', 'outside sales consultant',
      'sales and design consultant', 'aesthetic sales', 'hospice care consultant'],
     None),
]

# ── LEGAL COUNSEL ─────────────────────────────────────────────────────────────
LC_RULES = [
    (['1099 process server', 'process server'],
     None),
    (['licensed professional counselor', 'licensed mental health counselor',
      'licensed clinical professional counselor', 'substance abuse counselor',
      'peer counselor', 'residential counselor', 'mental health counselor',
      'marriage and family therapist', 'lmhc', 'lpcc', 'lcpc'],
     'Mental Health Therapist'),
    (['compliance manager', 'compliance engineer', 'compliance coordinator',
      'grc manager', 'governance risk and compliance',
      'governance, risk', 'governance risk &'],
     'Compliance Specialist'),
]

# ── OPERATIONS MANAGER — blacklist rules ─────────────────────────────────────
OM_RULES = [
    # Design
    (['art director', 'senior art director', 'associate creative director',
      'group creative director', 'vp creative'],
     'Creative Director'),
    # Healthcare
    (['medical director', 'chief medical', 'director of medicine',
      'director, medical', 'director of clinical'],
     'Medical Director'),
    (['health information specialist', 'health information manager',
      'health info specialist', 'health information technician'],
     None),
    # Security / Physical Security
    (['security specialist', 'security guard', 'unarmed security officer',
      'loss prevention officer', 'loss prevention manager',
      'security supervisor', 'security coordinator'],
     'Security Officer'),
    # Finance
    (['mortgage loan officer', 'loan officer', 'mortgage officer',
      'mortgage banker', 'lending officer'],
     'Loan Officer'),
    (['portfolio manager', 'portfolio management manager'],
     'Portfolio Manager'),
    (['accounts receivable specialist', 'accounting specialist',
      'accounting associate', 'accounting coordinator'],
     'Accountant'),
    (['tax supervisor', 'tax specialist', 'tax coordinator'],
     'Tax Manager'),
    # Legal
    (['associate attorney', 'staff attorney'],
     'Legal Counsel'),
    # Sales / BD
    (['business development associate', 'business development director',
      'business development manager'],
     'Business Development Manager'),
    # Marketing
    (['paid media manager', 'paid media specialist', 'manager, paid search',
      'manager, programmatic', 'programmatic manager', 'media buyer',
      'media manager', 'director of media buying'],
     'Paid Media Specialist'),
    # Retail (null — too floor-level)
    (['floor lead (retail)', 'floor lead', 'lead store associate',
      'store associate', 'grocery associate', 'retail assistant manager',
      'retail general manager', 'lead sales associate', 'key holder'],
     None),
    # Real Estate (null — no matching role)
    (['property manager', 'assistant property manager',
      'property management manager', 'assistant community manager',
      'feasibility manager', 'senior feasibility associate'],
     None),
    # Facilities / Maintenance
    (['maintenance manager', 'maintenance supervisor',
      'maintenance director', 'facilities supervisor'],
     'Maintenance Technician'),
    # Manufacturing
    (['production lead', 'production supervisor'],
     'Manufacturing Technician'),
    # Customer Support
    (['client service associate', 'client service specialist',
      'client services associate', 'client services specialist'],
     'Support Specialist'),
    # Logistics
    (['warehouse associate', 'warehouse supervisor', 'warehouse coordinator',
      'warehouse manager'],
     None),
    # Environmental
    (['environmental specialist', 'environmental manager',
      'environmental coordinator', 'environmental associate'],
     None),
    # Implementation
    (['implementation specialist', 'implementation associate'],
     'Implementation Consultant'),
    # Cannabis / niche
    (['cultivation associate', 'cannabis associate', 'dispensary associate',
      'budtender associate'],
     None),
    # Too-generic titles (null)
    (['^manager$', ' manager$'],   # standalone "Manager" or trailing " Manager" with no qualifier
     None),
    (['team lead', '^team lead$'],
     None),
]


def apply_rules(vars_, rules, role_ids_lookup, label):
    """
    For each variation in vars_, check rules in order.
    Returns list of (variation, target_role_id_or_None, matched_pattern).
    """
    actions = []
    for v in vars_:
        for patterns, target_name in rules:
            if matches(v.original_title, patterns):
                tgt_id = role_ids_lookup.get(target_name) if target_name else None
                actions.append((v, tgt_id, target_name or 'NULL', patterns[0]))
                break
    return actions


app = create_app()
with app.app_context():

    # Pre-load role IDs we'll need
    needed_roles = [
        'Leasing Consultant', 'Financial Analyst', 'Mental Health Therapist',
        'Compliance Specialist', 'Creative Director', 'Medical Director',
        'Security Officer', 'Loan Officer', 'Portfolio Manager', 'Accountant',
        'Tax Manager', 'Legal Counsel', 'Business Development Manager',
        'Paid Media Specialist', 'Maintenance Technician', 'Manufacturing Technician',
        'Support Specialist', 'Implementation Consultant',
    ]
    role_ids_lookup = {}
    for name in needed_roles:
        r = db.session.query(Role).filter_by(normalized_title=name).first()
        if r:
            role_ids_lookup[name] = r.id
        else:
            print(f'WARNING: role not found: {name!r}')

    sc_id  = role_id('Solutions Consultant')
    lc_id  = role_id('Legal Counsel')
    om_id  = role_id('Operations Manager')

    sc_vars = db.session.query(RoleTitleVariation).filter_by(role_id=sc_id).all()
    lc_vars = db.session.query(RoleTitleVariation).filter_by(role_id=lc_id).all()
    om_vars = db.session.query(RoleTitleVariation).filter_by(role_id=om_id).all()

    sc_actions = apply_rules(sc_vars, SC_RULES, role_ids_lookup, 'Solutions Consultant')
    lc_actions = apply_rules(lc_vars, LC_RULES, role_ids_lookup, 'Legal Counsel')
    om_actions = apply_rules(om_vars, OM_RULES, role_ids_lookup, 'Operations Manager')

    all_actions = [('SC', sc_actions), ('LC', lc_actions), ('OM', om_actions)]

    # ── REPORT ───────────────────────────────────────────────────────────────
    affected_role_ids = {sc_id, lc_id, om_id}

    for label, actions in all_actions:
        total_freq = sum(v.frequency for v, _, _, _ in actions)
        total_jobs = sum(
            db.session.query(func.count(Job.id)).filter(
                Job.role_id == v.role_id, Job.title == v.original_title
            ).scalar()
            for v, _, _, _ in actions
        )
        print(f'\n{label}: {len(actions)} variations affected  |  ~{total_freq} freq  |  ~{total_jobs} jobs')

        # Group by destination
        by_dest = {}
        for v, tgt_id, tgt_name, pat in actions:
            by_dest.setdefault(tgt_name, []).append((v, tgt_id, pat))

        for dest, items in sorted(by_dest.items(), key=lambda x: -sum(v.frequency for v, _, _ in x[1])):
            freq = sum(v.frequency for v, _, _ in items)
            print(f'  → {dest} ({len(items)} vars, {freq} freq):')
            for v, _, pat in sorted(items, key=lambda x: -x[0].frequency)[:5]:
                print(f'      {v.frequency:4d}  {v.original_title}')
            if len(items) > 5:
                print(f'      ... +{len(items)-5} more')
            if tgt_id := items[0][1]:
                affected_role_ids.add(tgt_id)

    if not APPLY:
        print('\nDry run. Pass --apply to commit.')
        sys.exit(0)

    print('\nApplying...')

    for label, actions in all_actions:
        for v, tgt_id, tgt_name, pat in actions:
            # Move jobs
            if tgt_id is not None:
                db.session.query(Job).filter(
                    Job.role_id == v.role_id, Job.title == v.original_title
                ).update({'role_id': tgt_id}, synchronize_session=False)
                # Re-point or delete variation
                existing = db.session.query(RoleTitleVariation).filter_by(
                    role_id=tgt_id, original_title=v.original_title
                ).first()
                if existing:
                    existing.frequency = (existing.frequency or 0) + (v.frequency or 0)
                    db.session.delete(v)
                else:
                    v.role_id = tgt_id
            else:
                # Null out jobs, delete variation
                db.session.query(Job).filter(
                    Job.role_id == v.role_id, Job.title == v.original_title
                ).update({'role_id': None}, synchronize_session=False)
                db.session.delete(v)

    db.session.flush()

    # Recompute total_active_jobs for all affected roles
    for rid in affected_role_ids:
        role = db.session.query(Role).filter_by(id=rid).first()
        if role is None:
            continue
        active = db.session.query(func.count(Job.id)).filter(
            Job.role_id == rid, Job.is_active == True
        ).scalar()
        role.total_active_jobs = active
        print(f'  {role.normalized_title}: {active:,} active jobs')

    db.session.commit()
    print('Done.')
