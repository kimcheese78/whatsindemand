"""Precompute validity-gated market insights -> market_insight_snapshots.

Boards produced (cohort-locked throughout):
  - Rising / declining ROLES, overall + per sector (job_family). Every row must pass:
    data-substance qualification (data_quality) + flow/stock agreement + family churn
    guard + a minimum absolute delta.
  - Emerging SKILLS (from SkillCandidate: recent first_seen, broad company_count).
  - Market summary (global-cohort postings trend).
  (Rising/falling established-skill board is a planned follow-up — see TODO.)

Idempotent per ISO week: with --apply it deletes this week's rows and rewrites them.

Run:
  cd backend && DATABASE_URL='<prod-public-dsn>' PYTHONPATH=. \\
      venv/bin/python scripts/compute_market_insights.py [--apply]
"""
import json
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app import create_app
from app.models import db, Role, SkillCandidate, MarketInsightSnapshot
from app.routes.roles import calculate_growth_pct
from app.services.data_quality import role_qualifies, qualified_roles
from scripts.leaderboard_diagnostics import (
    month_bounds, stock_count, flow_count, full_series, direction, role_series,
    _get_cohort_company_ids, FAMILIES,
)
from app.routes.roles import _trend_window_start, COHORT_BUFFER_DAYS

TOP_N = 10
MIN_ABS_DELTA = 30          # ignore moves smaller than this many postings
MIN_SECTOR_SURVIVORS = 3    # a sector board needs at least this many qualified movers
EMERGING_MIN_COMPANIES = 3
EMERGING_MAX_AGE_DAYS = 75


def iso_week_start(d=None):
    d = d or datetime.utcnow().date()
    return d - timedelta(days=d.weekday())


def _combined_series(series_list):
    """Element-wise sum of several [(month, count, partial)] series."""
    series_list = [s for s in series_list if s]
    if not series_list:
        return None
    base = list(series_list[0])
    for s in series_list[1:]:
        base = [(a[0], a[1] + b[1], a[2]) for a, b in zip(base, s)]
    return base


def _cohort_ids(role_id):
    cutoff = _trend_window_start(4) - timedelta(days=COHORT_BUFFER_DAYS)
    return _get_cohort_company_ids(role_id, cutoff)


def _series_pair(role_id):
    stock = role_series(role_id, stock_count)
    if not stock:                 # cohort < 5 -> no trustworthy trend
        return None
    return stock, role_series(role_id, flow_count)


def _mover(label, sector, stock, flow, cohort, confidence, is_family, market_growth):
    """Apply the movement gates (flow/stock agreement + absolute delta) and build a row,
    or return None. Qualification/breadth is checked by the caller."""
    ds, gs = direction(stock)
    df, _ = direction(flow)
    if gs is None or ds is None or ds != df:      # flow/stock must agree on direction
        return None
    full = full_series(stock)
    baseline, latest = full[0][1], full[-1][1]
    if abs(latest - baseline) < MIN_ABS_DELTA:    # ignore tiny moves
        return None
    return {
        'role': label, 'sector': sector, 'from': baseline, 'to': latest, 'growth': gs,
        'vs_market': round(gs - market_growth, 1) if market_growth is not None else None,
        'cohort': cohort, 'confidence': confidence, 'trend': [pt[1] for pt in full],
        'is_family': is_family,
    }


def _family_map():
    """name(lower) -> family, and family -> [Role rows]."""
    name_to_family, members_by_family = {}, {}
    for fam, members in FAMILIES.items():
        rows = Role.query.filter(
            func.lower(Role.normalized_title).in_([m.lower() for m in members])).all()
        members_by_family[fam] = rows
        for mr in rows:
            name_to_family[mr.normalized_title.lower()] = fam
    return name_to_family, members_by_family


def compute_role_movers(market_growth=None):
    """Individual (non-family) roles surface on their own; roles in a known synonym
    family NEVER surface individually — they are aggregated to a single family-level row
    (so relabeling within the family can't masquerade as a real move). Every survivor
    passes qualification + flow/stock agreement + absolute-delta floor."""
    name_to_family, members_by_family = _family_map()
    survivors = []

    # Non-family roles, individually.
    for r in qualified_roles():
        if r.normalized_title.lower() in name_to_family:
            continue
        pair = _series_pair(r.id)
        if not pair:
            continue
        ok, info = role_qualifies(r.id, r)
        if not ok:
            continue
        m = _mover(r.normalized_title, r.job_family or 'Other', pair[0], pair[1],
                   info['cohort'], info['confidence'], False, market_growth)
        if m:
            survivors.append(m)

    # Families, aggregated. The family must itself clear breadth + the movement gates,
    # so a flat family with a swinging split (relabeling) is dropped.
    for fam, rows in members_by_family.items():
        stocks, flows, cohort = [], [], set()
        sector_vol = {}
        for mr in rows:
            pair = _series_pair(mr.id)
            if not pair:
                continue
            stocks.append(pair[0])
            flows.append(pair[1])
            cohort |= set(_cohort_ids(mr.id))
            k = mr.job_family or 'Other'
            sector_vol[k] = sector_vol.get(k, 0) + (mr.total_active_jobs or 0)
        cs, cf = _combined_series(stocks), _combined_series(flows)
        if not cs or len(cohort) < 10:            # family breadth floor
            continue
        sector = max(sector_vol, key=sector_vol.get) if sector_vol else 'Other'
        confidence = round(min(1.0, len(cohort) / 30.0), 2)
        m = _mover(f"{fam} (family)", sector, cs, cf, len(cohort), confidence, True, market_growth)
        if m:
            survivors.append(m)
    return survivors


def _rows_from_survivors(survivors, scope, week):
    """Turn a survivor list into ranked rising/declining snapshot rows for a scope."""
    rows = []
    rising = sorted(survivors, key=lambda x: x['growth'], reverse=True)[:TOP_N]
    declining = sorted(survivors, key=lambda x: x['growth'])[:TOP_N]
    for kind, items in (('rising_role', rising), ('declining_role', declining)):
        for i, x in enumerate(items):
            if kind == 'rising_role' and x['growth'] <= 0:
                continue
            if kind == 'declining_role' and x['growth'] >= 0:
                continue
            rows.append(MarketInsightSnapshot(
                week_start=week, kind=kind, scope=scope, rank=i,
                payload=json.dumps({
                    'label': x['role'], 'sector': x['sector'],
                    'from': x['from'], 'to': x['to'], 'growth': x['growth'],
                    'cohort': x['cohort'], 'confidence': x['confidence'], 'trend': x['trend'],
                })))
    return rows


def compute_in_demand_roles(week, top=TOP_N):
    """Broad 'what companies are hiring for now' board — top qualified roles by current
    active volume (always populated, unlike the depth-gated trend boards)."""
    rows, rank = [], 0
    for r in qualified_roles()[:80]:            # already sorted desc by active volume
        ok, info = role_qualifies(r.id, r)
        if not ok:
            continue
        rows.append(MarketInsightSnapshot(
            week_start=week, kind='in_demand_role', scope='overall', rank=rank,
            payload=json.dumps({
                'label': r.normalized_title, 'sector': r.job_family or 'Other',
                'active': info['active'], 'cohort': info['cohort'],
                'confidence': info['confidence'],
            })))
        rank += 1
        if rank >= top:
            break
    return rows


def compute_emerging_skills(week):
    cutoff = datetime.utcnow().date() - timedelta(days=EMERGING_MAX_AGE_DAYS)
    cands = (SkillCandidate.query
             .filter(SkillCandidate.first_seen >= cutoff,
                     SkillCandidate.company_count >= EMERGING_MIN_COMPANIES)
             .order_by(SkillCandidate.company_count.desc(),
                       SkillCandidate.job_count.desc())
             .limit(TOP_N).all())
    rows = []
    for i, c in enumerate(cands):
        rows.append(MarketInsightSnapshot(
            week_start=week, kind='emerging_skill', scope='overall', rank=i,
            payload=json.dumps({
                'label': c.name, 'job_count': c.job_count, 'company_count': c.company_count,
                'first_seen': c.first_seen.isoformat() if c.first_seen else None,
            })))
    return rows


def compute_market_summary(week):
    cutoff = _trend_window_start(4) - timedelta(days=COHORT_BUFFER_DAYS)
    from app.models import Job
    global_cohort = [cid for (cid,) in db.session.query(Job.company_id)
                     .filter(Job.company_id.isnot(None)).group_by(Job.company_id)
                     .having(func.min(Job.scraped_at) <= cutoff).all()]
    series = [(s.isoformat()[:7], stock_count(global_cohort, s, e, p), p) for (s, e, p) in month_bounds()]
    full = full_series(series)
    growth = calculate_growth_pct(full[-1][1], full[0][1]) if len(full) >= 2 else None
    rows = [MarketInsightSnapshot(
        week_start=week, kind='market_summary', scope='overall', rank=0,
        payload=json.dumps({
            'label': 'Overall postings', 'cohort_companies': len(global_cohort),
            'from': full[0][1] if full else None, 'to': full[-1][1] if full else None,
            'growth': growth, 'trend': [pt[1] for pt in full],
        }))]
    return rows, growth


def main(apply=False):
    app = create_app()
    with app.app_context():
        week = iso_week_start()
        summary_rows, market_growth = compute_market_summary(week)
        survivors = compute_role_movers(market_growth=market_growth)
        print(f"Role movers surviving all gates: {len(survivors)}  (market drift {market_growth}%)")

        rows = []
        rows += _rows_from_survivors(survivors, 'overall', week)
        # per sector
        by_sector = {}
        for s in survivors:
            by_sector.setdefault(s['sector'], []).append(s)
        for sector, items in by_sector.items():
            if len(items) >= MIN_SECTOR_SURVIVORS:
                rows += _rows_from_survivors(items, f'sector:{sector}', week)
        rows += compute_in_demand_roles(week)
        rows += compute_emerging_skills(week)
        rows += summary_rows

        # summary print
        print(f"\nWeek {week}  |  {len(rows)} snapshot rows")
        for kind in ('rising_role', 'declining_role', 'emerging_skill', 'market_summary'):
            overall = [r for r in rows if r.kind == kind and r.scope == 'overall']
            if overall:
                print(f"\n[{kind} · overall]")
                for r in overall:
                    p = json.loads(r.payload)
                    if 'growth' in p and p['growth'] is not None:
                        vm = p.get('vs_market')
                        vm_s = f"  (vs mkt {vm:+.1f})" if vm is not None else ""
                        print(f"  {p['growth']:+7.1f}%  {p.get('from','?')}→{p.get('to','?')}  {p['label']}{vm_s}")
                    else:
                        print(f"  {p['label']}  {p.get('company_count','')}")
        print(f"\nSectors with a board: "
              f"{sorted({r.scope for r in rows if r.scope.startswith('sector:')})}")

        if apply:
            MarketInsightSnapshot.query.filter_by(week_start=week).delete()
            db.session.add_all(rows)
            db.session.commit()
            print(f"\nAPPLIED: wrote {len(rows)} rows for week {week}.")
        else:
            print("\nDRY RUN (pass --apply to persist).")


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
