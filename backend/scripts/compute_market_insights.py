"""Precompute validity-gated market insights -> market_insight_snapshots.

Boards produced (cohort-locked throughout):
  - Rising / declining ROLES, overall + per sector (job_family). Every row must pass:
    data-substance qualification (data_quality) + flow/stock agreement + family churn
    guard + a minimum absolute delta.
  - Rising / falling established SKILLS, overall. Growth is measured on PREVALENCE
    (share of cohort postings mentioning the skill) so it nets out market drift;
    cohort-locked to companies tracked the whole window; domain/industry skills excluded.
  - Emerging SKILLS (from SkillCandidate: recent first_seen, broad company_count).
  - Market summary (global-cohort postings trend).

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
from app.models import db, Job, Role, Skill, JobSkill, SkillCandidate, MarketInsightSnapshot
from app.routes.roles import calculate_growth_pct
from app.services.data_quality import role_qualifies, qualified_roles
from scripts.leaderboard_diagnostics import (
    month_bounds, stock_count, flow_count, full_series, direction, role_series,
    _get_cohort_company_ids, _period_end, JOB_DATE, FAMILIES,
)
from app.routes.roles import _trend_window_start, COHORT_BUFFER_DAYS, STALE_LISTING_DAYS

TOP_N = 10
MIN_ABS_DELTA = 30          # ignore moves smaller than this many postings
MIN_SECTOR_SURVIVORS = 3    # a sector board needs at least this many qualified movers
EMERGING_MIN_COMPANIES = 3
EMERGING_MAX_AGE_DAYS = 75

# Rising/declining established-SKILL board. Growth is measured on prevalence (share
# of cohort postings mentioning the skill), which nets out overall market drift.
SKILL_MIN_TOTAL_JOBS = 50      # only trend skills with a real market footprint
SKILL_MIN_PREV_JOBS = 20       # baseline volume floor inside the cohort (share stability)
SKILL_MIN_SHARE_DELTA = 0.3    # ignore share moves smaller than this many points
# Breadth guards: a market trend must span many employers, not one company flooding
# postings (or a single-company mis-extraction). Checked in BOTH the base and latest
# full month, so a skill can't rise/fall just because one big employer entered/left.
SKILL_MIN_COMPANIES = 8        # distinct cohort employers posting the skill
SKILL_MAX_CONCENTRATION = 0.5  # drop if any single employer is >50% of the skill's postings


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


def global_cohort_ids():
    """Companies we've tracked the whole trend window — the market-wide cohort shared
    by the market-summary and skill-trend boards."""
    cutoff = _trend_window_start(4) - timedelta(days=COHORT_BUFFER_DAYS)
    return [cid for (cid,) in db.session.query(Job.company_id)
            .filter(Job.company_id.isnot(None)).group_by(Job.company_id)
            .having(func.min(Job.scraped_at) <= cutoff).all()]


def _skill_stock_counts(company_ids, start, end, is_partial, skill_ids):
    """{skill_id: # active cohort postings mentioning that skill} for one month —
    same active-during-month window as stock_count, in a single grouped query."""
    pend = _period_end(end, is_partial)
    stale_floor = pend - timedelta(days=STALE_LISTING_DAYS)
    rows = (db.session.query(JobSkill.skill_id, func.count(func.distinct(Job.id)))
            .join(Job, JobSkill.job_id == Job.id)
            .filter(
                Job.company_id.in_(company_ids),
                JobSkill.skill_id.in_(skill_ids),
                JOB_DATE < pend,
                db.or_(Job.closed_at.is_(None), Job.closed_at >= start),
                db.or_(Job.closed_at.isnot(None), Job.last_seen_at >= stale_floor),
            ).group_by(JobSkill.skill_id).all())
    return dict(rows)


def _skill_concentration(company_ids, start, end, is_partial, skill_ids):
    """{skill_id: (n_companies, top_employer_share)} for one month — how broadly a
    skill's postings are spread across the cohort. One grouped query."""
    if not skill_ids:
        return {}
    pend = _period_end(end, is_partial)
    stale_floor = pend - timedelta(days=STALE_LISTING_DAYS)
    rows = (db.session.query(JobSkill.skill_id, Job.company_id, func.count(func.distinct(Job.id)))
            .join(Job, JobSkill.job_id == Job.id)
            .filter(
                Job.company_id.in_(company_ids),
                JobSkill.skill_id.in_(skill_ids),
                JOB_DATE < pend,
                db.or_(Job.closed_at.is_(None), Job.closed_at >= start),
                db.or_(Job.closed_at.isnot(None), Job.last_seen_at >= stale_floor),
            ).group_by(JobSkill.skill_id, Job.company_id).all())
    by_skill = {}
    for sid, _cid, n in rows:
        by_skill.setdefault(sid, []).append(n)
    return {sid: (len(cs), (max(cs) / sum(cs)) if sum(cs) else 1.0) for sid, cs in by_skill.items()}


def compute_skill_movers(global_cohort):
    """Market-scope rising/declining SKILLS, cohort-locked to companies tracked the
    whole window. Growth is measured on PREVALENCE (share of cohort postings mentioning
    the skill), so it nets out overall market drift — a skill going 8%->11% of postings
    is a real +37% move regardless of how the market moved. Domain skills (industries)
    are excluded; they're context, not learnable skills."""
    cand = (Skill.query
            .filter(Skill.is_verified.is_(True),
                    Skill.category.in_(['technical', 'soft']),
                    Skill.total_job_count >= SKILL_MIN_TOTAL_JOBS)
            .all())
    id_to_name = {s.id: s.name for s in cand}
    skill_ids = list(id_to_name)
    if not skill_ids:
        return []

    bounds = month_bounds()
    month_totals = [(s.isoformat()[:7], stock_count(global_cohort, s, e, p), p) for (s, e, p) in bounds]
    per_skill = {sid: [] for sid in skill_ids}
    for (s, e, p) in bounds:
        counts = _skill_stock_counts(global_cohort, s, e, p, skill_ids)
        month = s.isoformat()[:7]
        for sid in skill_ids:
            per_skill[sid].append((month, counts.get(sid, 0), p))

    full_totals = full_series(month_totals)
    if len(full_totals) < 2 or full_totals[0][1] == 0 or full_totals[-1][1] == 0:
        return []
    base_total, latest_total = full_totals[0][1], full_totals[-1][1]

    survivors = []
    for sid in skill_ids:
        full_counts = full_series(per_skill[sid])
        base_count, latest_count = full_counts[0][1], full_counts[-1][1]
        if base_count < SKILL_MIN_PREV_JOBS:
            continue
        base_share = base_count / base_total * 100
        latest_share = latest_count / latest_total * 100
        if abs(latest_share - base_share) < SKILL_MIN_SHARE_DELTA:
            continue
        growth = calculate_growth_pct(latest_share, base_share)
        if growth is None:
            continue
        trend = [round(c / t * 100, 2) for (_, c), (_, t) in zip(full_counts, full_totals)]
        survivors.append({
            'sid': sid, 'label': id_to_name[sid], 'growth': growth,
            'from_share': round(base_share, 2), 'to_share': round(latest_share, 2),
            'from': base_count, 'to': latest_count,
            'cohort': len(global_cohort), 'trend': trend,
        })

    # Breadth gate: keep only moves spread across many employers in BOTH the base and
    # latest full month — drops one-company floods / mis-extractions (e.g. a single firm
    # tagged on 500 postings) that would otherwise headline the board.
    base_bound, latest_bound = bounds[0], bounds[-2]
    surviving_ids = [s['sid'] for s in survivors]
    conc_base = _skill_concentration(global_cohort, *base_bound, surviving_ids)
    conc_latest = _skill_concentration(global_cohort, *latest_bound, surviving_ids)

    def _broad(s):
        cb, cl = conc_base.get(s['sid']), conc_latest.get(s['sid'])
        if not cb or not cl:
            return False
        return (cb[0] >= SKILL_MIN_COMPANIES and cl[0] >= SKILL_MIN_COMPANIES
                and cb[1] <= SKILL_MAX_CONCENTRATION and cl[1] <= SKILL_MAX_CONCENTRATION)

    kept = []
    for s in survivors:
        if _broad(s):
            s['companies'] = conc_latest[s['sid']][0]
            s.pop('sid')
            kept.append(s)
    return kept


def _skill_rows(survivors, week):
    """Rank survivors into rising/declining skill snapshot rows."""
    rows = []
    rising = [x for x in sorted(survivors, key=lambda x: x['growth'], reverse=True) if x['growth'] > 0][:TOP_N]
    declining = [x for x in sorted(survivors, key=lambda x: x['growth']) if x['growth'] < 0][:TOP_N]
    for kind, items in (('rising_skill', rising), ('falling_skill', declining)):
        for i, x in enumerate(items):
            rows.append(MarketInsightSnapshot(
                week_start=week, kind=kind, scope='overall', rank=i,
                payload=json.dumps({
                    'label': x['label'], 'growth': x['growth'],
                    'from': x['from'], 'to': x['to'],
                    'from_share': x['from_share'], 'to_share': x['to_share'],
                    'cohort': x['cohort'], 'companies': x.get('companies'), 'trend': x['trend'],
                })))
    return rows


def compute_market_summary(week, global_cohort):
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
        global_cohort = global_cohort_ids()
        summary_rows, market_growth = compute_market_summary(week, global_cohort)
        survivors = compute_role_movers(market_growth=market_growth)
        skill_survivors = compute_skill_movers(global_cohort)
        print(f"Role movers surviving all gates: {len(survivors)}  (market drift {market_growth}%)")
        print(f"Skill movers surviving all gates: {len(skill_survivors)}")

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
        rows += _skill_rows(skill_survivors, week)
        rows += compute_emerging_skills(week)
        rows += summary_rows

        # summary print
        print(f"\nWeek {week}  |  {len(rows)} snapshot rows")
        for kind in ('rising_role', 'declining_role', 'rising_skill', 'falling_skill',
                     'emerging_skill', 'market_summary'):
            overall = [r for r in rows if r.kind == kind and r.scope == 'overall']
            if overall:
                print(f"\n[{kind} · overall]")
                for r in overall:
                    p = json.loads(r.payload)
                    if 'from_share' in p:      # skill row: prevalence + breadth
                        print(f"  {p['growth']:+7.1f}%  {p['from_share']:.2f}%→{p['to_share']:.2f}% "
                              f"share ({p.get('from','?')}→{p.get('to','?')} jobs, "
                              f"{p.get('companies','?')} cos)  {p['label']}")
                    elif 'growth' in p and p['growth'] is not None:
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
