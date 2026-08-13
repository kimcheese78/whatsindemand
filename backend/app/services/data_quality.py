# backend/app/services/data_quality.py
"""Reusable data-substance qualifier: is a role / sector substantial enough to show?

Separate concern from the trend VALIDITY gates (family aggregation, flow/stock) that
live in the leaderboard precompute. This answers "does this entity have enough data to
be trustworthy at all" — volume + company breadth + concentration — and is reused by
the market precompute, the market endpoint, the qualified-roles list (search box), and
the per-role insights guard.

The decision math (`evaluate_qualification`) is a pure function so it can be unit-tested
without a database; the DB-touching helpers gather its inputs.
"""
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func

from app.models import db, Job, Role

# Tunable thresholds (calibrate against prod coverage).
MIN_ROLE_ACTIVE = 50        # active-postings floor
MIN_COHORT = 10             # distinct trend-depth companies posting the role
MAX_CONCENTRATION = 0.30    # top company's max share of the role's postings


def evaluate_qualification(active, cohort_size, top_share):
    """Pure decision: given the three inputs, return (qualified, reasons, confidence).

    - qualified: clears all three floors.
    - reasons: human-readable failure reasons (empty when qualified).
    - confidence: 0-1 blend of volume, breadth, and (lack of) concentration.
    """
    reasons = []
    if active < MIN_ROLE_ACTIVE:
        reasons.append(f'volume {active} < {MIN_ROLE_ACTIVE}')
    if cohort_size < MIN_COHORT:
        reasons.append(f'breadth {cohort_size} < {MIN_COHORT} companies')
    if top_share > MAX_CONCENTRATION:
        reasons.append(f'concentrated (top company {top_share:.0%} > {MAX_CONCENTRATION:.0%})')

    conc_term = 1 - (top_share / MAX_CONCENTRATION) if MAX_CONCENTRATION else 0
    confidence = (min(1.0, active / 200.0) * 0.4
                  + min(1.0, cohort_size / 30.0) * 0.4
                  + max(0.0, min(1.0, conc_term)) * 0.2)
    return (not reasons), reasons, round(max(0.0, min(1.0, confidence)), 2)


def _cohort(role_id):
    """Trend-depth companies that have posted this role (lazy import breaks a cycle)."""
    from app.routes.roles import (_get_cohort_company_ids, _trend_window_start,
                                  COHORT_BUFFER_DAYS)
    cutoff = _trend_window_start(4) - timedelta(days=COHORT_BUFFER_DAYS)
    return _get_cohort_company_ids(role_id, cutoff)


def _top_company_share(role_id, company_ids):
    """Largest single company's share of the role's active postings within the cohort."""
    if not company_ids:
        return 1.0
    rows = (db.session.query(Job.company_id, func.count(Job.id))
            .filter(Job.role_id == role_id, Job.is_active == True,
                    Job.company_id.in_(company_ids))
            .group_by(Job.company_id).all())
    counts = [c for _, c in rows]
    total = sum(counts)
    return (max(counts) / total) if total else 1.0


def role_qualifies(role_id, role=None):
    """Return (qualified: bool, info: dict) for a role. info: active, cohort, top_share,
    confidence, reasons."""
    role = role or Role.query.get(role_id)
    active = (role.total_active_jobs or 0) if role else 0
    cohort = _cohort(role_id)
    top_share = _top_company_share(role_id, cohort)
    qualified, reasons, confidence = evaluate_qualification(active, len(cohort), top_share)
    return qualified, {
        'active': active, 'cohort': len(cohort), 'top_share': round(top_share, 3),
        'confidence': confidence, 'reasons': reasons,
    }


def qualified_roles(min_active=MIN_ROLE_ACTIVE):
    """Cheap prefilter for surfaces like the search box: roles with real volume, newest
    first. Callers needing full trust apply role_qualifies() (breadth/concentration too)."""
    return (Role.query.filter(Role.total_active_jobs >= min_active)
            .order_by(Role.total_active_jobs.desc()).all())


def sector_rollup(roles=None):
    """Aggregate roles into `job_family` sectors: {family: {active, roles, qualified_roles}}.
    Thin roles still feed their sector so 'areas with substantial data' surface even when
    no single role clears the bar."""
    roles = roles if roles is not None else Role.query.all()
    agg = defaultdict(lambda: {'active': 0, 'roles': 0, 'qualified_roles': 0})
    for r in roles:
        a = agg[r.job_family or 'Other']
        a['active'] += (r.total_active_jobs or 0)
        a['roles'] += 1
        if (r.total_active_jobs or 0) >= MIN_ROLE_ACTIVE:
            a['qualified_roles'] += 1
    return dict(agg)
