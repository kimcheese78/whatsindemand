# backend/app/routes/roles.py

from flask import Blueprint, request, jsonify
from app.models import db, Job, JobSkill, Skill, Role, Company
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


# ============================================
# TREND & GROWTH CALCULATION FUNCTIONS
# ============================================

def get_trend_data(
    role_id: int, 
    months: int = 6, 
    seniority: str = None,
    locations: List[str] = None,
    company_ids: List[int] = None
) -> List[Dict]:
    """
    Get job availability trend data with all filters applied.
    """
    today = datetime.utcnow().date()
    trend_data = []
    
    job_date = func.coalesce(Job.posted_at, Job.scraped_at)
    
    for months_ago in range(months - 1, -1, -1):
        month = today.month - months_ago
        year = today.year
        
        while month <= 0:
            month += 12
            year -= 1
        
        period_start = date(year, month, 1)
        
        if month == 12:
            period_end = date(year + 1, 1, 1)
        else:
            period_end = date(year, month + 1, 1)
        
        # Base query
        query = Job.query.filter(
            Job.role_id == role_id,
            job_date < period_end,
            db.or_(
                Job.closed_at.is_(None),
                Job.closed_at >= period_start
            )
        )
        
        # Apply company filter
        if company_ids:
            query = query.filter(Job.company_id.in_(company_ids))
        
        # Apply seniority filter
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
        
        # Apply location filter
        if locations and not any(loc.lower() == 'all' for loc in locations):
            location_conditions = []
            for loc in locations:
                location_conditions.append(func.lower(Job.location_country) == loc.lower())
                location_conditions.append(Job.location_raw.ilike(f'%{loc}%'))
                
                # Handle US states
                if loc == 'United States':
                    for abbrev in US_STATE_ABBREVS:
                        location_conditions.append(func.upper(Job.location_country) == abbrev)
                    location_conditions.append(Job.location_state.in_(list(US_STATE_ABBREVS)))
                
                # Handle Canada
                elif loc == 'Canada':
                    for abbrev in CANADIAN_PROVINCE_ABBREVS:
                        location_conditions.append(func.upper(Job.location_country) == abbrev)
                    location_conditions.append(Job.location_state.in_(list(CANADIAN_PROVINCE_ABBREVS)))
                    
            query = query.filter(db.or_(*location_conditions))
        
        count = query.count()
        
        trend_data.append({
            'date': period_start.isoformat(),
            'count': count
        })
    
    return trend_data


def get_market_trend(
    role_id: int, 
    window_days: int = 30, 
    seniority: str = None,
    locations: List[str] = None,
    company_ids: List[int] = None
) -> Dict:
    """
    Calculate market trend (growth %) with all filters applied.
    """
    today = datetime.utcnow().date()
    current_end = today
    current_start = today - timedelta(days=window_days)
    previous_end = current_start
    previous_start = previous_end - timedelta(days=window_days)
    
    job_date = func.coalesce(Job.posted_at, Job.scraped_at)
    
    def build_base_query():
        """Build query with all filters except date range."""
        query = Job.query.filter(Job.role_id == role_id)
        
        # Apply company filter
        if company_ids:
            query = query.filter(Job.company_id.in_(company_ids))
        
        # Apply seniority filter
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
        
        # Apply location filter
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
        
        return query
    
    def count_available_jobs(period_start: date, period_end: date) -> int:
        query = build_base_query().filter(
            job_date < period_end,
            db.or_(
                Job.closed_at.is_(None),
                Job.closed_at >= period_start
            )
        )
        return query.count()
    
    current_count = count_available_jobs(current_start, current_end)
    previous_count = count_available_jobs(previous_start, previous_end)
    
    # Count new companies (also needs filters)
    current_companies_query = build_base_query().filter(
        job_date >= current_start,
        job_date < current_end
    )
    current_companies = set(
        c[0] for c in current_companies_query.with_entities(
            func.distinct(Job.company_id)
        ).all()
    )
    
    previous_companies_query = build_base_query().filter(
        job_date >= previous_start,
        job_date < previous_end
    )
    previous_companies = set(
        c[0] for c in previous_companies_query.with_entities(
            func.distinct(Job.company_id)
        ).all()
    )
    
    new_companies_count = len(current_companies - previous_companies)
    
    return {
        'postings_growth_pct': calculate_growth_pct(current_count, previous_count),
        'current_period_count': current_count,
        'previous_period_count': previous_count,
        'window_days': window_days,
        'new_companies_count': new_companies_count
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
    
    # Calculate growth for each skill
    result = {}
    for skill_id in skill_ids:
        current_count = current_map.get(skill_id, 0)
        previous_count = previous_map.get(skill_id, 0)
        
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
    
    # Calculate growth for each company
    result = {}
    for company_id in company_ids:
        current_count = current_map.get(company_id, 0)
        previous_count = previous_map.get(company_id, 0)
        result[company_id] = calculate_growth_pct(current_count, previous_count)
    
    return result


def _get_all_role_growth_bulk(role_ids: List[int], window_days: int = 30) -> Dict[int, Optional[float]]:
    """
    Calculate posting growth % for multiple roles in bulk.
    Returns dict mapping role_id -> growth_pct
    """
    if not role_ids:
        return {}
    
    today = datetime.utcnow().date()
    current_end = today
    current_start = today - timedelta(days=window_days)
    previous_end = current_start
    previous_start = previous_end - timedelta(days=window_days)
    
    job_date = func.coalesce(Job.posted_at, Job.scraped_at)
    
    # Bulk query: count jobs per role in current period
    current_counts = db.session.query(
        Job.role_id,
        func.count(Job.id).label('count')
    ).filter(
        Job.role_id.in_(role_ids),
        job_date < current_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= current_start)
    ).group_by(Job.role_id).all()
    
    current_map = {role_id: count for role_id, count in current_counts}
    
    # Bulk query: count jobs per role in previous period
    previous_counts = db.session.query(
        Job.role_id,
        func.count(Job.id).label('count')
    ).filter(
        Job.role_id.in_(role_ids),
        job_date < previous_end,
        db.or_(Job.closed_at.is_(None), Job.closed_at >= previous_start)
    ).group_by(Job.role_id).all()
    
    previous_map = {role_id: count for role_id, count in previous_counts}
    
    # Calculate growth for each role
    result = {}
    for role_id in role_ids:
        current_count = current_map.get(role_id, 0)
        previous_count = previous_map.get(role_id, 0)
        result[role_id] = calculate_growth_pct(current_count, previous_count)
    
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
    
    if not role_name:
        return jsonify({'success': False, 'error': 'role is required'}), 400
    
    # Find the role
    role = Role.query.filter(
        func.lower(Role.normalized_title) == func.lower(role_name)
    ).first()
    
    if not role:
        role = Role.query.filter(
            Role.normalized_title.ilike(f'%{role_name}%')
        ).first()
    
    if not role:
        suggestions = _suggest_similar_roles(role_name)
        return jsonify({
            'success': False,
            'error': f'Role "{role_name}" not found',
            'suggestions': suggestions
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
    jobs = jobs_query.all()
    job_ids = [j.id for j in jobs]
    total_jobs = len(job_ids)

    # ============================================
    # GET TREND DATA
    # ============================================
    

    trend_data = get_trend_data(
        role.id, 
        months=6,
        seniority=filters_applied.get('seniority'),
        locations=filters_applied.get('location'),
        company_ids=filters_applied.get('company_ids')
    )
    
    market_trend = get_market_trend(
        role.id, 
        window_days=30,
        seniority=filters_applied.get('seniority'),
        locations=filters_applied.get('location'),
        company_ids=filters_applied.get('company_ids')
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
        func.count(JobSkill.id).label('job_count')
    ).join(JobSkill).filter(
        JobSkill.job_id.in_(job_ids)
    ).group_by(Skill.id).order_by(
        func.count(JobSkill.id).desc()
    ).all()

    # Get all skill IDs for bulk growth calculation
    all_skill_ids = [s[0] for s in skill_counts]
    
    # Bulk calculate growth for all skills at once
    skill_growth_map = get_all_skill_growth_bulk(role.id, all_skill_ids, window_days=30)

    skills = []
    for skill_id, skill_name, category, job_count in skill_counts:
        demand = round(job_count / total_jobs * 100, 1)
        
        skills.append({
            'skill_id': skill_id,
            'name': skill_name,
            'category': category or 'technical',
            'job_count': job_count,
            'demand': demand,
            'growth_pct': skill_growth_map.get(skill_id)
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
        func.count(Job.id).label('job_count')
    ).join(Job).filter(
        Job.id.in_(job_ids)
    ).group_by(Company.id).order_by(
        func.count(Job.id).desc()
    ).all()

    # Get all company IDs for bulk growth calculation
    all_company_ids = [c[0] for c in top_companies]
    
    # Bulk calculate growth for all companies at once
    company_growth_map = get_all_company_growth_bulk(role.id, all_company_ids, window_days=30)

    top_companies_list = []
    for cid, cname, industry, jcount in top_companies:
        top_companies_list.append({
            'id': cid,
            'name': cname,
            'industry': industry,
            'job_count': jcount,
            'growth_pct': company_growth_map.get(cid)
        })

    # ============================================
    # GET ALTERNATIVE ROLES
    # ============================================
    
    alternative_roles = _get_alternative_roles(role.id, job_ids, skills[:20])

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
        'onsite_count': onsite_count
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
    
    role = Role.query.filter(
        func.lower(Role.normalized_title) == func.lower(role_name)
    ).first()
    
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
    
    alternatives = _get_alternative_roles(role.id, job_ids, skills)
    
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
    current_skills: List[Dict]
) -> List[Dict]:
    """
    Find roles with similar skill requirements.
    Returns top 5 roles ranked by skill overlap (Jaccard similarity).
    Includes USD salary data for each alternative role.
    """
    if not current_skills or not job_ids:
        return []
    
    total_current_jobs = len(job_ids)
    
    # Get ALL skills for current role WITH their frequency
    current_skills_with_counts = db.session.query(
        JobSkill.skill_id,
        func.count(JobSkill.id).label('job_count')
    ).filter(
        JobSkill.job_id.in_(job_ids)
    ).group_by(JobSkill.skill_id).all()
    
    all_current_skill_ids = set(skill_id for skill_id, _ in current_skills_with_counts)
    current_skill_demand = {skill_id: count for skill_id, count in current_skills_with_counts}
    
    # Get skill names for current role
    current_skill_names_query = db.session.query(Skill.id, Skill.name).filter(
        Skill.id.in_(all_current_skill_ids)
    ).all()
    current_skill_name_map = {s.id: s.name for s in current_skill_names_query}
    
    # Get all other roles with active jobs
    other_roles = db.session.query(
        Role.id,
        Role.normalized_title,
        Role.category,
        func.count(Job.id).label('job_count')
    ).join(Job).filter(
        Role.id != current_role_id,
        Job.is_active == True
    ).group_by(Role.id).having(
        func.count(Job.id) >= 3
    ).all()
    
    role_overlaps = []
    
    # Collect role IDs for bulk calculations
    candidate_role_ids = [r[0] for r in other_roles]
    
    # Bulk calculate growth for all candidate roles
    role_growth_map = _get_all_role_growth_bulk(candidate_role_ids, window_days=30)
    
    # Bulk calculate USD salary data for all candidate roles
    role_salary_map = _get_all_role_salaries_bulk(candidate_role_ids)
    
    for role_id, role_title, role_category, job_count in other_roles:
        role_job_ids = [
            j.id for j in Job.query.filter(
                Job.role_id == role_id,
                Job.is_active == True
            ).limit(100).all()
        ]
        
        if not role_job_ids:
            continue
        
        total_role_jobs = len(role_job_ids)
        
        # Get skills for this role WITH their frequency
        role_skills_with_counts = db.session.query(
            JobSkill.skill_id,
            func.count(JobSkill.id).label('job_count')
        ).filter(
            JobSkill.job_id.in_(role_job_ids)
        ).group_by(JobSkill.skill_id).all()
        
        role_skill_ids = set(skill_id for skill_id, _ in role_skills_with_counts)
        role_skill_demand = {skill_id: count for skill_id, count in role_skills_with_counts}
        
        # Calculate Jaccard similarity: intersection / union
        shared_skill_ids = all_current_skill_ids.intersection(role_skill_ids)
        union_skill_ids = all_current_skill_ids.union(role_skill_ids)
        
        # Skills in alternative role that current role doesn't have
        new_skill_ids = role_skill_ids - all_current_skill_ids
        
        # Require minimum overlap
        if len(shared_skill_ids) < 3:
            continue
        
        # Jaccard similarity as percentage
        overlap_percentage = round(len(shared_skill_ids) / len(union_skill_ids) * 100)
        
        # Calculate combined relevance score for shared skills
        shared_skills_scored = []
        for sid in shared_skill_ids:
            current_demand_pct = (current_skill_demand.get(sid, 0) / total_current_jobs) * 100
            alt_demand_pct = (role_skill_demand.get(sid, 0) / total_role_jobs) * 100
            combined_score = current_demand_pct + alt_demand_pct
            shared_skills_scored.append((sid, combined_score))
        
        # Sort by combined score (highest first)
        shared_skills_scored.sort(key=lambda x: x[1], reverse=True)
        
        # Get top shared skill names
        top_shared_ids = [sid for sid, _ in shared_skills_scored[:6]]
        shared_skill_names = [
            current_skill_name_map[sid] 
            for sid in top_shared_ids 
            if sid in current_skill_name_map
        ]
        
        # Get new skill names - sorted by demand in the alternative role
        new_skill_names = []
        if new_skill_ids:
            sorted_new_skill_ids = sorted(
                new_skill_ids, 
                key=lambda sid: role_skill_demand.get(sid, 0), 
                reverse=True
            )
            
            top_new_skill_ids = sorted_new_skill_ids[:10]
            new_skills = db.session.query(Skill.id, Skill.name).filter(
                Skill.id.in_(top_new_skill_ids)
            ).all()
            
            new_skill_name_map = {s.id: s.name for s in new_skills}
            new_skill_names = [
                new_skill_name_map[sid] 
                for sid in top_new_skill_ids 
                if sid in new_skill_name_map
            ][:4]
        
        # Get USD salary data for this role
        salary_data = role_salary_map.get(role_id, {})
        
        role_overlaps.append({
            'title': role_title,
            'category': role_category,
            'job_count': job_count,
            'skill_overlap': overlap_percentage,
            'shared_skills': shared_skill_names,
            'new_skills': new_skill_names,
            'shared_count': len(shared_skill_ids),
            'new_count': len(new_skill_ids),
            'posting_growth_pct': role_growth_map.get(role_id),
            'salary_min': salary_data.get('avg_min'),
            'salary_max': salary_data.get('avg_max'),
            'jobs_with_salary': salary_data.get('jobs_with_salary', 0)
        })
    
    # Sort by overlap percentage (descending) and return top 5
    role_overlaps.sort(key=lambda x: x['skill_overlap'], reverse=True)
    
    return role_overlaps[:5]