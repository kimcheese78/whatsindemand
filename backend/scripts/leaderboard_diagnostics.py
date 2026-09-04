"""Diagnostics: is the role-growth signal real, or taxonomy churn?

Cohort-locked, May-Jul 2026. Three checks:
  1. Global total conservation — active postings/month across one global cohort.
     A stable total with wild per-role swings = redistribution (relabeling).
  2. Family offsets — do near-synonym roles net ~flat while their split swings?
  3. Flow vs stock — recompute demand as NEW reqs opened/month (flow) and check
     whether it agrees on direction with the current active-during-month (stock).

Run:
  cd backend && DATABASE_URL='<prod-public-dsn>' PYTHONPATH=. \\
      venv/bin/python scripts/leaderboard_diagnostics.py
"""
from datetime import date, timedelta, datetime

from sqlalchemy import func

from app import create_app
from app.models import db, Job, Role
from app.routes.roles import (
    _get_cohort_company_ids, _trend_window_start, calculate_growth_pct,
    COHORT_BUFFER_DAYS, STALE_LISTING_DAYS,
)

MONTHS = 4
JOB_DATE = func.coalesce(Job.posted_at, Job.scraped_at)

# Suspected synonym families (by case-insensitive title match) + a few standalone
# movers to test with flow/stock. Edit freely.
FAMILIES = {
    'Sales/Solutions Eng': ['Sales Engineer', 'Solutions Engineer', 'Partner Solutions Architect'],
    'HRBP / People Partner': ['HR Business Partner', 'People Partner'],
    'Sales Dev (SDR/BDR)': ['Sales Development Representative', 'Business Development Representative'],
    'Account Executive': ['Commercial Account Executive', 'Mid-Market Account Executive'],
}
STANDALONES = ['Applied AI Engineer', 'Technical Program Manager', 'Mobile Engineer',
               'Payroll Specialist', 'Talent Sourcer', 'Business Systems Analyst']


def month_bounds():
    today = datetime.utcnow().date()
    out = []
    for months_ago in range(MONTHS - 1, -1, -1):
        m, y = today.month - months_ago, today.year
        while m <= 0:
            m += 12
            y -= 1
        start = date(y, m, 1)
        end = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
        out.append((start, end, months_ago == 0))
    return out


def _period_end(end, is_partial):
    return datetime.utcnow().date() + timedelta(days=1) if is_partial else end


def stock_count(company_ids, start, end, is_partial, role_id=None):
    """Postings ACTIVE during the month (same window logic as get_trend_data)."""
    pend = _period_end(end, is_partial)
    stale_floor = pend - timedelta(days=STALE_LISTING_DAYS)
    q = Job.query.filter(
        Job.company_id.in_(company_ids),
        JOB_DATE < pend,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= start),
        db.or_(Job.closed_at.isnot(None), Job.last_seen_at >= stale_floor),
    )
    if role_id is not None:
        q = q.filter(Job.role_id == role_id)
    return q.count()


def flow_count(company_ids, start, end, is_partial, role_id=None):
    """NEW postings opened in the month (coalesce(posted_at, scraped_at) in [start,end))."""
    pend = _period_end(end, is_partial)
    q = Job.query.filter(
        Job.company_id.in_(company_ids),
        JOB_DATE >= start, JOB_DATE < pend,
    )
    if role_id is not None:
        q = q.filter(Job.role_id == role_id)
    return q.count()


def full_series(counts):
    """Drop the partial (current) month; return [(YYYY-MM, count), ...]."""
    return [(m, c) for (m, c, p) in counts if not p]


def direction(counts):
    fc = full_series(counts)
    if len(fc) < 2 or fc[0][1] == 0:
        return None, None
    g = calculate_growth_pct(fc[-1][1], fc[0][1])
    return (1 if g and g > 0 else -1 if g and g < 0 else 0), g


def role_series(role_id, counter):
    cutoff = _trend_window_start(MONTHS) - timedelta(days=COHORT_BUFFER_DAYS)
    cohort = _get_cohort_company_ids(role_id, cutoff)
    if len(cohort) < 5:
        return None
    return [(s.isoformat()[:7], counter(cohort, s, e, p, role_id), p) for (s, e, p) in month_bounds()]


def resolve(name):
    return Role.query.filter(func.lower(Role.normalized_title) == name.lower()).first()


def fmt(counts):
    return "  ".join(f"{m[5:]}:{c}{'*' if p else ''}" for (m, c, p) in counts)


def main():
    app = create_app()
    with app.app_context():
        bounds = month_bounds()
        window = f"{bounds[0][0].isoformat()[:7]} -> {bounds[-2][0].isoformat()[:7]} (full) + {bounds[-1][0].isoformat()[:7]}* partial"
        print(f"\nWindow: {window}\n")

        # 1. Global total conservation (one global cohort)
        cutoff = _trend_window_start(MONTHS) - timedelta(days=COHORT_BUFFER_DAYS)
        global_cohort = [cid for (cid,) in db.session.query(Job.company_id).filter(
            Job.company_id.isnot(None)
        ).group_by(Job.company_id).having(func.min(Job.scraped_at) <= cutoff).all()]
        gtotals = [(s.isoformat()[:7], stock_count(global_cohort, s, e, p), p) for (s, e, p) in bounds]
        print(f"[1] GLOBAL active postings (cohort of {len(global_cohort)} cos):")
        print(f"    {fmt(gtotals)}")
        gfull = full_series(gtotals)
        print(f"    full-month change: {calculate_growth_pct(gfull[-1][1], gfull[0][1])}%  "
              f"(stable total + big per-role swings => redistribution)\n")

        # 2. Family offsets
        print("[2] FAMILY OFFSETS (does the split swing while the family stays ~flat?):")
        for fam, members in FAMILIES.items():
            print(f"  {fam}:")
            combined = None
            for name in members:
                r = resolve(name)
                if not r:
                    print(f"    - {name}: NOT FOUND")
                    continue
                s = role_series(r.id, stock_count)
                if not s:
                    print(f"    - {name}: cohort<5, skipped")
                    continue
                _, g = direction(s)
                print(f"    - {name:<34} {fmt(s)}   ({g:+}%)" if g is not None else f"    - {name}: n/a")
                combined = [c for c in s] if combined is None else [
                    (a[0], a[1] + b[1], a[2]) for a, b in zip(combined, s)]
            if combined:
                _, gc = direction(combined)
                print(f"    = FAMILY TOTAL{'':<21} {fmt(combined)}   ({gc:+}% <= the real signal)\n")

        # 3. Flow vs stock agreement
        print("[3] FLOW vs STOCK (keep only roles where both agree on direction):")
        check = STANDALONES + [m for ms in FAMILIES.values() for m in ms]
        agree = disagree = 0
        for name in check:
            r = resolve(name)
            if not r:
                continue
            s = role_series(r.id, stock_count)
            f = role_series(r.id, flow_count)
            if not s or not f:
                continue
            ds, gs = direction(s)
            df, gf = direction(f)
            ok = (ds == df)
            agree += ok
            disagree += (not ok)
            print(f"  {'OK ' if ok else 'XX '} {name:<34} stock {gs:+}%  |  flow {gf:+}%")
        print(f"\n  agree: {agree}   disagree: {disagree}  (disagree => drop; likely artifact)\n")


if __name__ == '__main__':
    main()
