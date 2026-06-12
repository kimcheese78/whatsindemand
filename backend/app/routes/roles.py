# backend/app/routes/roles.py

from flask import Blueprint, request, jsonify
from app.models import db, Job, JobSkill, Skill, Role, Company, RoleTitleVariation
from sqlalchemy import func
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date

from app.utils.location_normalizer import (
    normalize_location_to_country,
    COUNTRY_TO_REGION,
    COUNTRY_ALIASES,
    US_STATE_ABBREVS,
    US_STATE_NAMES,
    CITY_TO_COUNTRY,
    CANADIAN_PROVINCE_ABBREVS,
    CANADIAN_PROVINCE_NAMES,
)

roles_bp = Blueprint('roles', __name__, url_prefix='/api/roles')


# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_growth_pct(current_count: float, previous_count: float) -> Optional[float]:
    """Calculate percentage growth between two periods."""
    if previous_count == 0:
        if current_count > 0:
            return 100.0
        return None
    return round(((current_count - previous_count) / previous_count) * 100, 1)


# Cohort-lock keeps every period drawn from the same set of companies, so
# scrape expansion doesn't create phantom growth.
COHORT_BUFFER_DAYS = 14         # absorbs scraper ramp-up irregularities
STALE_LISTING_DAYS = 90         # treat as closed if not re-scraped within this
MIN_COHORT_COMPANIES = 5        # below this, return None / [] (insufficient data)


def _get_cohort_company_ids(role_id: int, cohort_cutoff: date) -> List[int]:
    """Companies tracked for this role since at least `cohort_cutoff`."""
    rows = db.session.query(Job.company_id).filter(
        Job.role_id == role_id,
        Job.company_id.isnot(None),
    ).group_by(Job.company_id).having(
        func.min(Job.scraped_at) <= cohort_cutoff
    ).all()
    return [cid for (cid,) in rows]


def is_all(value):
    """Check if a value represents 'all' (case-insensitive)."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.lower() == 'all'
    if isinstance(value, list):
        return len(value) == 0 or any(
            isinstance(v, str) and v.lower() == 'all' for v in value
        )
    return False


def _find_role(role_name: str):
    """Look up a role by normalized title, then alias, then partial match."""
    role = Role.query.filter(
        func.lower(Role.normalized_title) == func.lower(role_name)
    ).first()
    if role:
        return role

    variation = RoleTitleVariation.query.filter(
        func.lower(RoleTitleVariation.original_title) == func.lower(role_name)
    ).first()
    if variation:
        return Role.query.get(variation.role_id)

    return Role.query.filter(
        Role.normalized_title.ilike(f'%{role_name}%')
    ).first()


# ============================================
# TREND & GROWTH CALCULATION FUNCTIONS
# ============================================

def get_trend_data(
    role_id: int,
    months: int = 4,
    seniority: str = None,
    locations: List[str] = None,
    company_ids: List[int] = None
) -> List[Dict]:
    """
    Cohort-locked monthly trend. Each bar counts distinct postings whose
    [posted_at_or_scraped_at, closed_at_or_now] window intersects the month,
    restricted to companies tracked for the entire window so scrape expansion
    can't create phantom growth.
    """
    today = datetime.utcnow().date()
    job_date = func.coalesce(Job.posted_at, Job.scraped_at)

    # Window starts at first day of (today − months + 1) month
    first_month = today.month - (months - 1)
    first_year = today.year
    while first_month <= 0:
        first_month += 12
        first_year -= 1
    window_start = date(first_year, first_month, 1)
    cohort_cutoff = window_start - timedelta(days=COHORT_BUFFER_DAYS)

    cohort_company_ids = _get_cohort_company_ids(role_id, cohort_cutoff)
    if len(cohort_company_ids) < MIN_COHORT_COMPANIES:
        return []

    # If user filtered by company, intersect with the cohort
    effective_company_ids = cohort_company_ids
    if company_ids:
        effective_company_ids = list(set(company_ids) & set(cohort_company_ids))
        if not effective_company_ids:
            # Selected companies are all outside the cohort → all bars are 0
            effective_company_ids = []

    trend_data = []

    for months_ago in range(months - 1, -1, -1):
        month = today.month - months_ago
        year = today.year
        while month <= 0:
            month += 12
            year -= 1

        period_start = date(year, month, 1)
        if month == 12:
            month_end_exclusive = date(year + 1, 1, 1)
        else:
            month_end_exclusive = date(year, month + 1, 1)

        is_partial = (months_ago == 0)
        period_end = today + timedelta(days=1) if is_partial else month_end_exclusive

        if not effective_company_ids:
            trend_data.append({
                'date': period_start.isoformat(),
                'count': 0,
                **({'is_partial': True} if is_partial else {}),
            })
            continue

        stale_floor = period_end - timedelta(days=STALE_LISTING_DAYS)

        query = Job.query.filter(
            Job.role_id == role_id,
            Job.company_id.in_(effective_company_ids),
            job_date < period_end,
            db.or_(Job.closed_at.is_(None), Job.closed_at >= period_start),
            db.or_(
                Job.closed_at.isnot(None),
                Job.last_seen_at >= stale_floor,
            ),
        )

        # Seniority filter
        if seniority and seniority.lower() != 'all':
            seniority_map = {
                'entry': ['entry', 'junior', 'associate', 'i', 'I', '1', 'intern'],
                'mid': ['mid', 'middle', 'ii', 'II', '2', 'intermediate'],
                'senior': ['senior', 'sr', 'iii', 'III', '3'],
                'lead': ['lead', 'principal', 'staff', 'director', 'head', 'iv', 'IV', '4', '5']
            }
            seniority_values = seniority_map.get(seniority, [seniority])
            seniority_conditions = [
                func.lower(Job.seniority_level) == val.lower()
                for val in seniority_values
            ]
            query = query.filter(db.or_(*seniority_conditions))

        # Location filter
        if locations and not any(loc.lower() == 'all' for loc in locations):
            location_conditions = []
            for loc in locations:
                location_conditions.append(func.lower(Job.location_country) == loc.lower())
                location_conditions.append(Job.location_raw.ilike(f'%{loc}%'))
                if loc == 'United States':
                    for abbrev in US_STATE_ABBREVS:
                        location_conditions.append(func.upper(Job.location_country) == abbrev)
                    location_conditions.append(Job.location_state.in_(list(US_STATE_ABBREVS)))
                elif loc == 'Canada':
                    for abbrev in CANADIAN_PROVINCE_ABBREVS:
                        location_conditions.append(func.upper(Job.location_country) == abbrev)
                    location_conditions.append(Job.location_state.in_(list(CANADIAN_PROVINCE_ABBREVS)))
            query = query.filter(db.or_(*location_conditions))

        count = query.count()

        entry = {'date': period_start.isoformat(), 'count': count}
        if is_partial:
            entry['is_partial'] = True
        trend_data.append(entry)

    return trend_data


def get_market_trend(
    role_id: int,
    seniority: str = None,
    locations: List[str] = None,
    company_ids: List[int] = None,
    trend_data: Optional[List[Dict]] = None,
) -> Dict:
    """
    Latest month-over-month growth, derived from the same cohort-locked
    monthly data the trend chart shows. Compares the last full month to the
    month before it, so the headline number can never disagree with the
    bars on the chart.

    `trend_data` may be passed in to avoid recomputing; otherwise we fetch
    a fresh 4-month window.
    """
    if trend_data is None:
        trend_data = get_trend_data(
            role_id,
            months=4,
            seniority=seniority,
            locations=locations,
            company_ids=company_ids,
        )

    full_months = [b for b in trend_data if not b.get('is_partial')]
    if len(full_months) < 2:
        return {
            'postings_growth_pct': None,
            'current_period_count': None,
            'previous_period_count': None,
        }

    current = full_months[-1]
    previous = full_months[-2]

    return {
        'postings_growth_pct': calculate_growth_pct(current['count'], previous['count']),
        'current_period_count': current['count'],
        'previous_period_count': previous['count'],
        'current_period_start': current['date'],
        'previous_period_start': previous['date'],
    }


# ============================================
# BULK GROWTH CALCULATION FUNCTIONS (OPTIMIZED)
# ============================================

def get_all_skill_growth_bulk(role_id: int, skill_ids: List[int], window_days: int = 30) -> Dict[int, Optional[float]]:
    """
    Calculate growth % for ALL skills in one bulk query.
    Returns dict mapping skill_id -> growth_pct
    """
    if not skill_ids:
        return {}
    
    today = datetime.utcnow().date()
    current_end = today
    current_start = today - timedelta(days=window_days)
    previous_end = current_start
    previous_start = previous_end - timedelta(days=window_days)
    
    job_date = func.coalesce(Job.posted_at, Job.scraped_at)
    
    # Get job IDs for current period
    current_jobs = Job.query.filter(
        Job.role_id == role_id,
        job_date < current_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= current_start)
    ).with_entities(Job.id).all()
    current_job_ids = [j.id for j in current_jobs]
    
    # Get job IDs for previous period
    previous_jobs = Job.query.filter(
        Job.role_id == role_id,
        job_date < previous_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= previous_start)
    ).with_entities(Job.id).all()
    previous_job_ids = [j.id for j in previous_jobs]
    
    if not current_job_ids or not previous_job_ids:
        return {sid: None for sid in skill_ids}
    
    current_total = len(current_job_ids)
    previous_total = len(previous_job_ids)
    
    # Bulk query: count jobs per skill in current period
    current_counts = db.session.query(
        JobSkill.skill_id,
        func.count(JobSkill.id).label('count')
    ).filter(
        JobSkill.job_id.in_(current_job_ids),
        JobSkill.skill_id.in_(skill_ids)
    ).group_by(JobSkill.skill_id).all()
    
    current_map = {skill_id: count for skill_id, count in current_counts}
    
    # Bulk query: count jobs per skill in previous period
    previous_counts = db.session.query(
        JobSkill.skill_id,
        func.count(JobSkill.id).label('count')
    ).filter(
        JobSkill.job_id.in_(previous_job_ids),
        JobSkill.skill_id.in_(skill_ids)
    ).group_by(JobSkill.skill_id).all()
    
    previous_map = {skill_id: count for skill_id, count in previous_counts}
    
    MIN_SKILL_PREV_JOBS = 5

    # Calculate growth for each skill
    result = {}
    for skill_id in skill_ids:
        current_count = current_map.get(skill_id, 0)
        previous_count = previous_map.get(skill_id, 0)

        if previous_count < MIN_SKILL_PREV_JOBS:
            result[skill_id] = None
            continue

        current_pct = (current_count / current_total) * 100 if current_total > 0 else 0
        previous_pct = (previous_count / previous_total) * 100 if previous_total > 0 else 0

        result[skill_id] = calculate_growth_pct(current_pct, previous_pct)

    return result


def get_all_company_growth_bulk(role_id: int, company_ids: List[int], window_days: int = 30) -> Dict[int, Optional[float]]:
    """
    Calculate growth % for ALL companies in one bulk query.
    Returns dict mapping company_id -> growth_pct
    """
    if not company_ids:
        return {}
    
    today = datetime.utcnow().date()
    current_end = today
    current_start = today - timedelta(days=window_days)
    previous_end = current_start
    previous_start = previous_end - timedelta(days=window_days)
    
    job_date = func.coalesce(Job.posted_at, Job.scraped_at)
    
    # Bulk query: count jobs per company in current period
    current_counts = db.session.query(
        Job.company_id,
        func.count(Job.id).label('count')
    ).filter(
        Job.role_id == role_id,
        Job.company_id.in_(company_ids),
        job_date < current_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= current_start)
    ).group_by(Job.company_id).all()
    
    current_map = {cid: count for cid, count in current_counts}
    
    # Bulk query: count jobs per company in previous period
    previous_counts = db.session.query(
        Job.company_id,
        func.count(Job.id).label('count')
    ).filter(
        Job.role_id == role_id,
        Job.company_id.in_(company_ids),
        job_date < previous_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= previous_start)
    ).group_by(Job.company_id).all()
    
    previous_map = {cid: count for cid, count in previous_counts}
    
    # Use a proportional floor: require at least 1% of the largest company's previous count,
    # but no less than 3. Prevents newly-scraped companies with sparse history from topping the list.
    max_prev = max(previous_map.values(), default=0)
    min_company_prev_jobs = max(3, int(max_prev * 0.01))

    # Calculate growth for each company
    result = {}
    for company_id in company_ids:
        current_count = current_map.get(company_id, 0)
        previous_count = previous_map.get(company_id, 0)
        if previous_count < min_company_prev_jobs:
            result[company_id] = None
            continue
        result[company_id] = calculate_growth_pct(current_count, previous_count)

    return result


def _get_all_role_growth_bulk(role_ids: List[int], **_kwargs) -> Dict[int, Optional[float]]:
    """
    Calculate posting growth % for multiple roles in bulk using the same
    full calendar-month windows as get_market_trend(), so numbers stay
    consistent with the overview tab headline.
    """
    if not role_ids:
        return {}

    today = datetime.utcnow().date()
    # Last full calendar month
    curr_month = today.month - 1 or 12
    curr_year = today.year if today.month > 1 else today.year - 1
    curr_start = date(curr_year, curr_month, 1)
    curr_end = date(today.year, today.month, 1)  # first of current month

    prev_month = curr_month - 1 or 12
    prev_year = curr_year if curr_month > 1 else curr_year - 1
    prev_start = date(prev_year, prev_month, 1)
    prev_end = curr_start

    job_date = func.coalesce(Job.posted_at, Job.scraped_at)

    current_counts = db.session.query(
        Job.role_id,
        func.count(Job.id).label('count')
    ).filter(
        Job.role_id.in_(role_ids),
        job_date < curr_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= curr_start)
    ).group_by(Job.role_id).all()

    previous_counts = db.session.query(
        Job.role_id,
        func.count(Job.id).label('count')
    ).filter(
        Job.role_id.in_(role_ids),
        job_date < prev_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= prev_start)
    ).group_by(Job.role_id).all()

    current_map = {role_id: count for role_id, count in current_counts}
    previous_map = {role_id: count for role_id, count in previous_counts}

    result = {}
    for role_id in role_ids:
        result[role_id] = calculate_growth_pct(
            current_map.get(role_id, 0), previous_map.get(role_id, 0)
        )

    return result


def _get_all_role_salaries_bulk(role_ids: List[int]) -> Dict[int, Dict]:
    """Get USD salary data for multiple roles in a single query."""
    if not role_ids:
        return {}
    
    salary_data = db.session.query(
        Job.role_id,
        func.avg(Job.salary_min_usd).label('avg_min'),
        func.avg(Job.salary_max_usd).label('avg_max'),
        func.count(Job.salary_min_usd).label('salary_count')
    ).filter(
        Job.role_id.in_(role_ids),
        Job.is_active == True,
        Job.salary_min_usd.isnot(None),
        Job.salary_min_usd > 0
    ).group_by(Job.role_id).all()
    
    return {
        role_id: {
            'avg_min': int(avg_min) if avg_min else None,
            'avg_max': int(avg_max) if avg_max else None,
            'jobs_with_salary': salary_count
        }
        for role_id, avg_min, avg_max, salary_count in salary_data
    }


# ============================================
# MAIN INSIGHTS ENDPOINT
# ============================================

@roles_bp.route('/insights', methods=['POST'])
def get_role_insights():
    """
    Main endpoint for role intelligence dashboard.
    Returns skills, companies, trends, and growth data for a role.
    """
    data = request.get_json() or {}
    
    role_name = data.get('role')
    seniority = data.get('seniority')
    location = data.get('location')
    industries = data.get('industry')
    company_ids = data.get('company_id')
    user_skill_ids_raw = data.get('user_skills') or []
    user_skill_ids = set(int(s) for s in user_skill_ids_raw) if user_skill_ids_raw else None
    
    if not role_name:
        return jsonify({'success': False, 'error': 'role is required'}), 400
    
    role = _find_role(role_name)
    if not role:
        return jsonify({
            'success': False,
            'error': f'Role "{role_name}" not found',
            'suggestions': _suggest_similar_roles(role_name)
        }), 404

    # Build job query with filters
    jobs_query = Job.query.filter(
        Job.role_id == role.id,
        Job.is_active == True
    )

    filters_applied = {
        'seniority': None,
        'location': None,
        'industries': None,
        'company_ids': None
    }

    # Apply seniority filter
    if not is_all(seniority):
        seniority_map = {
            'entry': ['entry', 'junior', 'associate', 'i', 'I', '1', 'intern'],
            'mid': ['mid', 'middle', 'ii', 'II', '2', 'intermediate'],
            'senior': ['senior', 'sr', 'iii', 'III', '3'],
            'lead': ['lead', 'principal', 'staff', 'director', 'head', 'iv', 'IV', '4', '5']
        }
        seniority_values = seniority_map.get(seniority, [seniority])
        seniority_conditions = [
            func.lower(Job.seniority_level) == val.lower() 
            for val in seniority_values
        ]
        
        jobs_query = jobs_query.filter(db.or_(*seniority_conditions))
        filters_applied['seniority'] = seniority

    # Apply location filter
    if not is_all(location):
        if isinstance(location, str):
            locations_list = [location]
        else:
            locations_list = list(location)
        
        locations_list = [loc for loc in locations_list if loc.lower() != 'all']
        
        if locations_list:
            all_location_conditions = []
            
            for loc in locations_list:
                location_conditions = []
                loc_lower = loc.lower()
                
                matching_aliases = [alias for alias, country in COUNTRY_ALIASES.items() if country == loc]
                matching_aliases.append(loc)
                
                for alias in matching_aliases:
                    location_conditions.append(func.lower(Job.location_country) == alias.lower())
                    location_conditions.append(Job.location_country.ilike(f'%{alias}%'))
                
                location_conditions.append(Job.location_raw.ilike(f'%{loc}%'))
                
                # Special handling for United States
                if loc == 'United States':
                    for abbrev in US_STATE_ABBREVS:
                        location_conditions.append(func.upper(Job.location_country) == abbrev)
                        location_conditions.append(Job.location_country.ilike(f'{abbrev} %'))
                        location_conditions.append(Job.location_country.ilike(f'% {abbrev}'))
                        location_conditions.append(Job.location_country.ilike(f'{abbrev};%'))
                        location_conditions.append(Job.location_country.ilike(f'{abbrev}|%'))
                        location_conditions.append(Job.location_country.ilike(f'{abbrev}-%'))
                    
                    for state_name in US_STATE_NAMES:
                        location_conditions.append(func.lower(Job.location_country) == state_name.lower())
                    
                    location_conditions.append(Job.location_state.in_(list(US_STATE_ABBREVS)))
                    
                    us_cities = [city for city, country in CITY_TO_COUNTRY.items() if country == 'United States']
                    for city in us_cities[:20]:
                        location_conditions.append(Job.location_raw.ilike(f'%{city}%'))
                
                # Special handling for Canada
                elif loc == 'Canada':
                    for abbrev in CANADIAN_PROVINCE_ABBREVS:
                        location_conditions.append(func.upper(Job.location_country) == abbrev)
                        location_conditions.append(Job.location_country.ilike(f'{abbrev};%'))
                        location_conditions.append(Job.location_country.ilike(f'{abbrev} %'))
                    
                    for prov_name in CANADIAN_PROVINCE_NAMES:
                        location_conditions.append(func.lower(Job.location_country) == prov_name.lower())
                    
                    location_conditions.append(Job.location_state.in_(list(CANADIAN_PROVINCE_ABBREVS)))
                
                # Special handling for UK
                elif loc == 'United Kingdom':
                    uk_terms = ['uk', 'u.k.', 'england', 'scotland', 'wales', 'gbr', 'great britain']
                    for term in uk_terms:
                        location_conditions.append(func.lower(Job.location_country) == term)
                        location_conditions.append(Job.location_country.ilike(f'%{term}%'))
                
                # Special handling for India
                elif loc == 'India':
                    india_terms = ['ind', 'india', 'karnataka', 'telangana', 'maharashtra', 'bengaluru', 'bangalore', 'hyderabad', 'mumbai', 'pune', 'delhi']
                    for term in india_terms:
                        location_conditions.append(func.lower(Job.location_country) == term)
                        location_conditions.append(Job.location_country.ilike(f'{term};%'))
                        location_conditions.append(Job.location_country.ilike(f'{term} %'))
                
                all_location_conditions.append(db.or_(*location_conditions))
            
            jobs_query = jobs_query.filter(db.or_(*all_location_conditions))
            filters_applied['location'] = locations_list

    # Apply industry filter
    if industries:
        if isinstance(industries, str):
            industries = [industries]
        
        matching_companies = db.session.query(Company.id).filter(
            Company.industry.in_(industries),
            Company.is_active == True
        ).all()
        matching_company_ids = [c[0] for c in matching_companies]
        
        if matching_company_ids:
            jobs_query = jobs_query.filter(Job.company_id.in_(matching_company_ids))
        else:
            jobs_query = jobs_query.filter(Job.company_id.in_([-1]))
        filters_applied['industries'] = industries

    # Apply company filter
    if company_ids:
        if isinstance(company_ids, int):
            company_ids = [company_ids]
        elif isinstance(company_ids, str):
            company_ids = [int(company_ids)]
        elif isinstance(company_ids, list):
            company_ids = [int(cid) for cid in company_ids]
        
        jobs_query = jobs_query.filter(Job.company_id.in_(company_ids))
        filters_applied['company_ids'] = company_ids

    # Get jobs
    job_ids = [j for (j,) in jobs_query.with_entities(Job.id).all()]
    total_jobs = len(job_ids)

    # ============================================
    # GET TREND DATA
    # ============================================
    

    # TODO: bump back to months=6 once scrape history reaches ~6.5 months (~2026-06-14).
    trend_data = get_trend_data(
        role.id,
        months=4,
        seniority=filters_applied.get('seniority'),
        locations=filters_applied.get('location'),
        company_ids=filters_applied.get('company_ids')
    )
    
    market_trend = get_market_trend(
        role.id,
        seniority=filters_applied.get('seniority'),
        locations=filters_applied.get('location'),
        company_ids=filters_applied.get('company_ids'),
        trend_data=trend_data,
    )

    # Return empty result if no jobs match filters
    if total_jobs == 0:
        return jsonify({
            'success': True,
            'role': {
                'id': role.id,
                'title': role.normalized_title,
                'category': role.category,
                'job_family': role.job_family
            },
            'total_jobs_analyzed': 0,
            'company_count': 0,
            'top_companies': [],
            'skills': [],
            'alternative_roles': [],
            'salary_info': None,
            'filters_applied': filters_applied,
            'trend_data': trend_data,
            'market_trend': market_trend,
            'remote_count': 0,
            'onsite_count': 0,
            'message': 'No jobs found matching these filters'
        }), 200

    # ============================================
    # GET SKILLS WITH GROWTH DATA (BULK OPTIMIZED)
    # ============================================
    
    skill_counts = db.session.query(
        Skill.id,
        Skill.name,
        Skill.category,
        Skill.subcategory,
        func.count(JobSkill.id).label('job_count'),
        func.sum(func.cast(JobSkill.is_required, db.Integer)).label('required_count'),
        func.sum(func.cast(~JobSkill.is_required, db.Integer)).label('preferred_count')
    ).join(JobSkill).filter(
        JobSkill.job_id.in_(job_ids),
        Skill.is_verified == True
    ).group_by(Skill.id).order_by(
        func.count(JobSkill.id).desc()
    ).limit(150).all()

    # Get all skill IDs for bulk growth calculation
    all_skill_ids = [s[0] for s in skill_counts]

    # Bulk calculate growth for all skills at once
    skill_growth_map = get_all_skill_growth_bulk(role.id, all_skill_ids, window_days=30)

    # Bulk fetch top companies per skill (single query, grouped in Python)
    from collections import defaultdict
    skill_company_rows = db.session.query(
        JobSkill.skill_id,
        Company.name,
        func.count(Job.id).label('job_count')
    ).join(Job, JobSkill.job_id == Job.id
    ).join(Company, Job.company_id == Company.id
    ).filter(
        JobSkill.job_id.in_(job_ids),
        JobSkill.skill_id.in_(all_skill_ids),
        Job.company_id.isnot(None)
    ).group_by(JobSkill.skill_id, Company.id, Company.name
    ).order_by(JobSkill.skill_id, func.count(Job.id).desc()
    ).all()

    skill_companies_map = defaultdict(list)
    for s_id, c_name, c_count in skill_company_rows:
        if len(skill_companies_map[s_id]) < 10:
            skill_companies_map[s_id].append({'name': c_name, 'job_count': c_count})

    skills = []
    for skill_id, skill_name, category, subcategory, job_count, required_count, preferred_count in skill_counts:
        demand = round(job_count / total_jobs * 100, 1)
        required_count = required_count or 0
        preferred_count = preferred_count or 0

        skills.append({
            'skill_id': skill_id,
            'name': skill_name,
            'category': category or 'technical',
            'subcategory': subcategory,
            'job_count': job_count,
            'demand': demand,
            'required_pct': round(required_count / job_count * 100) if job_count else 0,
            'preferred_pct': round(preferred_count / job_count * 100) if job_count else 0,
            'growth_pct': skill_growth_map.get(skill_id),
            'top_companies': skill_companies_map.get(skill_id, [])
        })

    # ============================================
    # GET COMPANY DATA WITH GROWTH (BULK OPTIMIZED)
    # ============================================
    
    company_count = db.session.query(
        func.count(func.distinct(Job.company_id))
    ).filter(Job.id.in_(job_ids)).scalar() or 0
    
    top_companies = db.session.query(
        Company.id,
        Company.name,
        Company.industry,
        Company.logo_url,
        Company.website,
        Company.location,
        Company.founded_year,
        Company.company_type,
        Company.valuation,
        func.count(Job.id).label('job_count')
    ).join(Job).filter(
        Job.id.in_(job_ids)
    ).group_by(Company.id).order_by(
        func.count(Job.id).desc()
    ).limit(100).all()

    all_company_ids = [c[0] for c in top_companies]
    company_growth_map = get_all_company_growth_bulk(role.id, all_company_ids, window_days=30)

    top_companies_list = []
    for cid, cname, industry, logo_url, website, location, founded_year, company_type, valuation, jcount in top_companies:
        top_companies_list.append({
            'id': cid,
            'name': cname,
            'industry': industry,
            'logo_url': logo_url,
            'website': website,
            'location': location,
            'founded_year': founded_year,
            'company_type': company_type,
            'valuation': valuation,
            'job_count': jcount,
            'growth_pct': company_growth_map.get(cid)
        })

    # ============================================
    # GET ALTERNATIVE ROLES
    # ============================================
    

    alternative_roles = _get_alternative_roles(role.id, job_ids, user_skill_ids=user_skill_ids)

    # ============================================
    # GET SALARY INFO (ALL CONVERTED TO USD)
    # ============================================
    
    salary_rows = db.session.query(
        Job.salary_min_usd,
        Job.salary_max_usd
    ).filter(
        Job.id.in_(job_ids),
        Job.salary_min_usd.isnot(None),
        Job.salary_min_usd > 0
    ).all()
    
    salary_info = None
    if len(salary_rows) >= 3:
        mins = sorted([r.salary_min_usd for r in salary_rows])
        maxs = sorted([r.salary_max_usd for r in salary_rows if r.salary_max_usd])
        
        count = len(mins)
        median_idx = count // 2
        
        salary_info = {
            'min': mins[0],
            'max': maxs[-1] if maxs else mins[-1],
            'median': mins[median_idx],
            'jobs_with_salary': count,
            'salary_coverage_pct': round((count / total_jobs) * 100, 1) if total_jobs > 0 else 0
        }

    # ============================================
    # GET REMOTE VS ONSITE COUNTS
    # ============================================
    
    remote_count = Job.query.filter(
        Job.id.in_(job_ids),
        Job.location_is_remote == True
    ).count()
    
    onsite_count = total_jobs - remote_count

    # Last scrape timestamp — max last_scraped_at across all active companies
    last_scraped = db.session.execute(
        db.text("SELECT MAX(last_scraped_at) FROM companies WHERE scrape_enabled = TRUE AND last_scraped_at IS NOT NULL")
    ).scalar()

    return jsonify({
        'success': True,
        'role': {
            'id': role.id,
            'title': role.normalized_title,
            'category': role.category,
            'job_family': role.job_family
        },
        'total_jobs_analyzed': total_jobs,
        'company_count': company_count,
        'top_companies': top_companies_list,
        'skills': skills,
        'alternative_roles': alternative_roles,
        'salary_info': salary_info,
        'filters_applied': filters_applied,
        'trend_data': trend_data,
        'market_trend': market_trend,
        'remote_count': remote_count,
        'onsite_count': onsite_count,
        'data_as_of': last_scraped.isoformat() if last_scraped else None,
    })


# ============================================
# ALTERNATIVES ENDPOINT
# ============================================

@roles_bp.route('/alternatives', methods=['POST'])
def get_role_alternatives():
    """
    Get alternative roles based on skill overlap.
    """
    data = request.get_json() or {}
    role_name = data.get('role')
    
    if not role_name:
        return jsonify({'success': False, 'error': 'role is required'}), 400
    
    role = _find_role(role_name)
    if not role:
        return jsonify({'success': False, 'error': f'Role "{role_name}" not found'}), 404
    
    job_ids = [j.id for j in Job.query.filter(
        Job.role_id == role.id,
        Job.is_active == True
    ).limit(500).all()]
    
    if not job_ids:
        return jsonify({
            'success': True,
            'alternatives': [],
            'message': 'No jobs found for this role'
        })
    
    total_jobs = len(job_ids)
    skill_counts = db.session.query(
        Skill.id,
        Skill.name,
        Skill.category,
        func.count(JobSkill.id).label('job_count')
    ).join(JobSkill).filter(
        JobSkill.job_id.in_(job_ids)
    ).group_by(Skill.id).order_by(
        func.count(JobSkill.id).desc()
    ).limit(20).all()

    skills = [
        {
            'skill_id': skill_id,
            'name': skill_name,
            'category': category,
            'job_count': job_count,
            'demand': round(job_count / total_jobs * 100, 1)
        }
        for skill_id, skill_name, category, job_count in skill_counts
    ]
    
    alternatives = _get_alternative_roles(role.id, job_ids)
    
    return jsonify({
        'success': True,
        'current_role': role.normalized_title,
        'alternatives': alternatives
    })


# ============================================
# ROLE DETAILS ENDPOINT
# ============================================

@roles_bp.route('/<int:role_id>', methods=['GET'])
def get_role_details(role_id):
    """Get details for a specific role."""
    role = Role.query.get(role_id)
    
    if not role:
        return jsonify({'success': False, 'error': 'Role not found'}), 404
    
    job_count = Job.query.filter(
        Job.role_id == role_id,
        Job.is_active == True
    ).count()
    
    return jsonify({
        'success': True,
        'role': {
            'id': role.id,
            'title': role.normalized_title,
            'category': role.category,
            'job_family': role.job_family,
            'job_count': job_count
        }
    })


# ============================================
# PRIVATE HELPER FUNCTIONS
# ============================================

def _suggest_similar_roles(query: str) -> List[Dict]:
    """Suggest similar role titles based on search query."""
    roles = Role.query.filter(
        Role.normalized_title.ilike(f'%{query}%')
    ).limit(5).all()
    
    if not roles:
        roles = db.session.query(Role).join(Job).group_by(Role.id).order_by(
            func.count(Job.id).desc()
        ).limit(5).all()
    
    return [
        {
            'id': r.id, 
            'title': r.normalized_title, 
            'category': r.category
        } 
        for r in roles
    ]


def _get_alternative_roles(
    current_role_id: int,
    job_ids: List[int],
    user_skill_ids: set = None,
) -> List[Dict]:
    """
    Find roles that fit the user's skill profile.

    If user_skill_ids is provided (the skills the user selected on their profile),
    ranks by how much of their skillset each candidate role demands. Otherwise
    falls back to skill overlap with the current role.

    Blends with posting growth so dying roles don't surface as "promising".
    De-duplicates by Role.category (max 2 per category).
    All salary numbers are USD.
    """
    from collections import defaultdict

    MIN_CANDIDATE_JOBS = 30          # demand floor — "in-demand" requires real volume
    MIN_SHARED_SKILLS = 3
    MAX_PER_CATEGORY = 2
    TARGET_COUNT = 5

    if not job_ids:
        return []

    total_current_jobs = len(job_ids)

    # Current role: skill_id -> distinct-job count
    current_counts = db.session.query(
        JobSkill.skill_id,
        func.count(func.distinct(JobSkill.job_id)).label('cnt')
    ).filter(
        JobSkill.job_id.in_(job_ids)
    ).group_by(JobSkill.skill_id).all()

    current_skill_demand = {sid: cnt for sid, cnt in current_counts}
    if user_skill_ids:
        my_skill_ids = user_skill_ids
        min_shared = 1  # user may have few skills; any overlap is signal
    else:
        my_skill_ids = set(current_skill_demand.keys())
        min_shared = MIN_SHARED_SKILLS
    if len(my_skill_ids) < 1:
        return []

    # Candidate roles: must clear the demand floor
    other_roles = db.session.query(
        Role.id,
        Role.normalized_title,
        Role.category,
        func.count(Job.id).label('jc')
    ).join(Job, Job.role_id == Role.id).filter(
        Role.id != current_role_id,
        Job.is_active == True
    ).group_by(Role.id, Role.normalized_title, Role.category).having(
        func.count(Job.id) >= MIN_CANDIDATE_JOBS
    ).all()

    if not other_roles:
        return []

    candidate_role_ids = [r[0] for r in other_roles]
    role_meta = {
        rid: {'title': title, 'category': category, 'job_count': jc}
        for rid, title, category, jc in other_roles
    }

    # Bulk: per-(role, skill) distinct-job counts in a single query.
    # Replaces the prior N+1 loop and the 100-row sample bias.
    role_skill_rows = db.session.query(
        Job.role_id,
        JobSkill.skill_id,
        func.count(func.distinct(Job.id)).label('cnt')
    ).join(JobSkill, JobSkill.job_id == Job.id).filter(
        Job.role_id.in_(candidate_role_ids),
        Job.is_active == True
    ).group_by(Job.role_id, JobSkill.skill_id).all()

    role_skill_demand: Dict[int, Dict[int, int]] = defaultdict(dict)
    for rid, sid, cnt in role_skill_rows:
        role_skill_demand[rid][sid] = cnt

    role_growth_map = _get_all_role_growth_bulk(candidate_role_ids, window_days=30)
    role_salary_map = _get_all_role_salaries_bulk(candidate_role_ids)

    candidates = []
    for rid in candidate_role_ids:
        skills_map = role_skill_demand.get(rid, {})
        their_skill_ids = set(skills_map.keys())
        total_role_jobs = role_meta[rid]['job_count']

        if user_skill_ids:
            # Skip roles with too little skill data — can't score them meaningfully.
            if len(skills_map) < 10:
                continue

            # Core skills: appear in ≥5% of this role's job postings.
            if total_role_jobs > 0:
                core_skill_ids = {sid for sid, cnt in skills_map.items()
                                  if cnt / total_role_jobs >= 0.05}
            else:
                core_skill_ids = set()
            # Fallback: if fewer than 15 qualify, take the top 30 by raw count
            if len(core_skill_ids) < 15:
                core_skill_ids = set(sorted(skills_map, key=lambda s: skills_map[s], reverse=True)[:30])
            if len(core_skill_ids) < 10:
                continue
            if len(core_skill_ids) > 40:
                core_skill_ids = set(sorted(core_skill_ids, key=lambda s: skills_map[s], reverse=True)[:40])

            shared_ids = my_skill_ids & core_skill_ids
            if len(shared_ids) < min_shared:
                continue

            # Demand-weighted score: sum how strongly each of the user's matched
            # skills is demanded by this role, normalised by user skill count.
            # This rewards roles where the user's skills are CORE (demanded at 40%)
            # over roles where they appear as afterthoughts (demanded at 5%).
            matched_demand = sum(
                skills_map.get(sid, 0) / total_role_jobs
                for sid in shared_ids
            ) if total_role_jobs else 0
            demand_score = matched_demand / len(my_skill_ids)

            # Breadth: fraction of the user's skills that transfer (used in ranking).
            breadth = len(shared_ids) / len(my_skill_ids)

            # Demand-weighted role coverage: what fraction of this role's total
            # skill demand does the user already cover?
            # Σ(demand% for matched skills) / Σ(demand% for all core skills)
            total_role_demand = sum(
                skills_map.get(sid, 0) / total_role_jobs
                for sid in core_skill_ids
            ) if total_role_jobs else 0
            demand_weighted_coverage = (
                matched_demand / total_role_demand
                if total_role_demand > 0 else 0
            )

            # Combined ranking score: demand strength drives ordering.
            coverage = 0.7 * demand_score + 0.3 * breadth

            new_ids = core_skill_ids - my_skill_ids
        else:
            shared_ids = my_skill_ids & their_skill_ids
            if len(shared_ids) < min_shared:
                continue
            coverage = len(shared_ids) / len(my_skill_ids)
            new_ids = their_skill_ids - my_skill_ids

        union_ids = my_skill_ids | their_skill_ids
        jaccard = len(shared_ids) / len(union_ids) if union_ids else 0

        # Growth signal — clamp tightly so a hot role can't outrank a strong skill match.
        growth = role_growth_map.get(rid)
        growth_signal = 0.0
        if growth is not None:
            growth_signal = max(-30.0, min(30.0, growth)) / 100.0
        score = coverage + 0.05 * growth_signal

        # Rank shared skills by how central they are to the role
        shared_scored = []
        for sid in shared_ids:
            theirs_pct = skills_map.get(sid, 0) / total_role_jobs if total_role_jobs else 0
            shared_scored.append((sid, theirs_pct))
        shared_scored.sort(key=lambda x: x[1], reverse=True)
        top_shared_ids = [sid for sid, _ in shared_scored[:8]]

        # Gap: core skills the user doesn't have, ranked by demand %.
        # Filter to ≥10% demand so fringe skills don't surface (e.g. "Google Ads"
        # in Operations Manager passes the 5% core threshold but isn't a real gap
        # worth surfacing). Fall back to top-10 by demand % if nothing clears 10%.
        MIN_GAP_DEMAND = 0.10
        new_ids_scored = [
            (sid, skills_map.get(sid, 0) / total_role_jobs)
            for sid in new_ids
            if total_role_jobs
        ]
        new_ids_scored.sort(key=lambda x: x[1], reverse=True)
        filtered = [sid for sid, pct in new_ids_scored if pct >= MIN_GAP_DEMAND]
        top_new_ids = (filtered or [sid for sid, _ in new_ids_scored])[:10]

        # MATCH % shown in the UI.
        # F1 of demand-weighted coverage and breadth — harmonic mean of:
        #   demand_weighted_coverage: what fraction of this role's demand you cover
        #   breadth: what fraction of YOUR skills are relevant here
        # Pure coverage alone rates Neuropsychologist (2 soft skills, small role)
        # above AI Engineer (6 technical skills) because Communication+Collaboration
        # happen to dominate a small denominator. F1 fixes this by also requiring
        # that a meaningful fraction of the user's own skills transfer.
        if user_skill_ids:
            f1 = (2 * demand_weighted_coverage * breadth / (demand_weighted_coverage + breadth)
                  if (demand_weighted_coverage + breadth) > 0 else 0)
            display_pct = round(f1 * 100)
        else:
            display_pct = round(coverage * 100)

        candidates.append({
            'role_id': rid,
            'shared_ids': top_shared_ids,
            'new_ids': top_new_ids,
            'shared_count': len(shared_ids),
            'new_count': len(new_ids),
            'coverage_pct': display_pct,
            'jaccard_pct': round(jaccard * 100),
            'score': score,
            'growth': growth,
        })

    if not candidates:
        return []

    # Hydrate skill names in one query
    referenced_ids = set()
    for c in candidates:
        referenced_ids.update(c['shared_ids'])
        referenced_ids.update(c['new_ids'])
    skill_name_map = {
        s.id: s.name
        for s in Skill.query.filter(Skill.id.in_(referenced_ids)).all()
    }

    candidates.sort(key=lambda c: (c['shared_count'], c['coverage_pct'], role_meta[c['role_id']]['job_count']), reverse=True)

    # Same-category dedupe so role families don't sweep the list
    out = []
    cat_counts: Dict[str, int] = defaultdict(int)
    for c in candidates:
        meta = role_meta[c['role_id']]
        cat_key = meta['category'] or '__uncategorized__'
        if cat_counts[cat_key] >= MAX_PER_CATEGORY:
            continue
        cat_counts[cat_key] += 1

        salary = role_salary_map.get(c['role_id'], {})
        out.append({
            'title': meta['title'],
            'category': meta['category'],
            'job_count': meta['job_count'],
            'skill_overlap': c['coverage_pct'],   # what % of your skills transfer
            'jaccard_pct': c['jaccard_pct'],      # symmetric similarity, for transparency
            'shared_skills': [skill_name_map[s] for s in c['shared_ids'] if s in skill_name_map],
            'new_skills': [skill_name_map[s] for s in c['new_ids'] if s in skill_name_map][:6],
            'shared_count': c['shared_count'],
            'new_count': c['new_count'],
            'posting_growth_pct': c['growth'],
            'salary_min': salary.get('avg_min'),
            'salary_max': salary.get('avg_max'),
            'salary_currency': 'USD',
            'jobs_with_salary': salary.get('jobs_with_salary', 0),
        })
        if len(out) >= TARGET_COUNT:
            break

    return out


# ============================================
# SHAREABLE CARD ENDPOINT
# ============================================

# (skill_name_lower, role_category_lower, callout_template)
# Only fires when the skill is verified in the live top-6; {rank}/{pct} come from real data.
_SURPRISE_SIGNALS = [
    ('sql',           'product',     'SQL ranks #{rank} in {role} postings ({pct}%) — ahead of Figma, Jira, and every roadmapping tool.'),
    ('sql',           'marketing',   'SQL ranks #{rank} in {role} postings ({pct}%) — the role is more quantitative than the title suggests.'),
    ('sql',           'design',      'SQL ranks #{rank} in {role} postings ({pct}%) — employers want data fluency alongside craft skills.'),
    ('sql',           'operations',  'SQL ranks #{rank} in {role} postings ({pct}%) — data querying is now a core operations skill.'),
    ('sql',           'finance',     'SQL ranks #{rank} in {role} postings ({pct}%) — spreadsheet fluency alone is no longer enough.'),
    ('sql',           'sales',       'SQL ranks #{rank} in {role} postings ({pct}%) — analytics fluency is now expected in sales.'),
    ('sql',           'people',       'SQL ranks #{rank} in {role} postings ({pct}%) — people analytics has changed what HR needs.'),
    ('excel',         'data science', 'Excel ranks #{rank} in {role} postings ({pct}%) — spreadsheets still beat modern tools at most companies.'),
    ('communication', 'engineering',  'Communication ranks #{rank} in {role} postings ({pct}%) — the most underrated line on a tech resume.'),
    ('communication', 'data science', 'Communication ranks #{rank} in {role} postings ({pct}%) — technical depth alone isn\'t enough.'),
    ('figma',         'design',      'Figma ranks #{rank} in {role} postings ({pct}%) — it\'s now the industry standard, not a preference.'),
    ('typescript',    'engineering', 'TypeScript ranks #{rank} in {role} postings ({pct}%) — it now outranks plain JavaScript in most markets.'),
    ('kubernetes',    'engineering', 'Kubernetes ranks #{rank} in {role} postings ({pct}%) — container orchestration has overtaken traditional CI/CD tools.'),
    ('python',        'marketing',   'Python ranks #{rank} in {role} postings ({pct}%) — the bar for marketing analytics keeps rising.'),
    ('python',        'finance',     'Python ranks #{rank} in {role} postings ({pct}%) — financial modeling is moving beyond spreadsheets.'),
]


def _get_callout(role_title: str, role_category: str, skills: list) -> Optional[str]:
    """Return a surprise callout only when the signal is verified in the live top-6."""
    category_key = (role_category or '').lower().strip()
    skill_index = {s['name'].lower(): (i + 1, s['percentage']) for i, s in enumerate(skills)}
    for skill_lower, cat, template in _SURPRISE_SIGNALS:
        if cat != category_key:
            continue
        entry = skill_index.get(skill_lower)
        if entry is None:
            continue
        rank, pct = entry
        if rank > 6:
            continue
        return template.format(role=role_title, rank=rank, pct=pct)
    return None


@roles_bp.route('/card/<role_slug>', methods=['GET'])
def get_role_card(role_slug):
    """Public endpoint for shareable role insight cards. No auth required."""
    role_name = role_slug.replace('-', ' ')
    role = _find_role(role_name)
    if not role:
        return jsonify({'success': False, 'error': 'Role not found'}), 404

    seniority = request.args.get('seniority', '').lower().strip()
    location = request.args.get('location', '').strip()

    jobs_query = db.session.query(Job.id).filter(
        Job.role_id == role.id,
        Job.is_active == True,
    )
    if seniority and seniority != 'all':
        jobs_query = jobs_query.filter(func.lower(Job.seniority_level) == seniority)
    if location and location.lower() not in ('', 'all'):
        if location.lower() == 'remote':
            jobs_query = jobs_query.filter(Job.location_is_remote == True)
        else:
            jobs_query = jobs_query.filter(func.lower(Job.location_country) == location.lower())

    job_ids = [j for (j,) in jobs_query.with_entities(Job.id).all()]
    total_jobs = len(job_ids)
    if total_jobs == 0:
        return jsonify({'success': False, 'error': 'No jobs found for this role and filters'}), 404

    skill_counts = db.session.query(
        Skill.name,
        func.count(JobSkill.id).label('job_count'),
    ).join(JobSkill, Skill.id == JobSkill.skill_id).filter(
        JobSkill.job_id.in_(job_ids),
        Skill.is_verified == True,
    ).group_by(Skill.id, Skill.name).order_by(
        func.count(JobSkill.id).desc()
    ).limit(8).all()

    skills = [
        {
            'name': name,
            'job_count': count,
            'percentage': min(round(count / total_jobs * 100), 100),
        }
        for name, count in skill_counts
    ]

    return jsonify({
        'success': True,
        'role': role.normalized_title,
        'category': role.category,
        'total_jobs': total_jobs,
        'seniority': seniority or 'all',
        'location': location or 'all',
        'skills': skills,
        'callout': _get_callout(role.normalized_title, role.category, skills),
    })