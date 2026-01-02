from flask import Blueprint, request, jsonify
from app.models import Job, Company
from app.utils.jwt_handler import token_required, pro_access_required
from app.services.job_matcher import JobMatcher

bp = Blueprint('jobs', __name__)

@bp.route('/matches', methods=['POST'])
@token_required
@pro_access_required
def get_job_matches():
    """
    Get jobs matching user's skills
    
    Requires Pro Access
    
    Body:
        role: Filter by role (optional)
        location: Filter by location (optional)
        seniority: Filter by seniority (optional)
        limit: Number of results (default: 20)
    """
    data = request.get_json() or {}
    
    # Build filters
    filters = {}
    if data.get('role'):
        filters['role'] = data['role']
    if data.get('location'):
        filters['location'] = data['location']
    if data.get('seniority'):
        filters['seniority'] = data['seniority']
    
    limit = int(data.get('limit', 20))
    
    # Get matched jobs
    matcher = JobMatcher()
    matches = matcher.find_matching_jobs(request.user_id, filters)
    
    # Limit results
    matches = matches[:limit]
    
    return jsonify({
        'total_matches': len(matches),
        'matches': matches
    }), 200

@bp.route('/search', methods=['POST'])
@token_required
def search_jobs():
    """
    Search jobs (basic search, available to all users)
    
    Body:
        query: Search query
        location: Location filter (optional)
        limit: Number of results (default: 10)
    """
    data = request.get_json() or {}
    
    query_text = data.get('query', '')
    location = data.get('location')
    limit = int(data.get('limit', 10))
    
    # Build query
    job_query = Job.query.filter(Job.is_active == True)
    
    if query_text:
        job_query = job_query.filter(
            (Job.title.ilike(f"%{query_text}%")) |
            (Job.description_text.ilike(f"%{query_text}%"))
        )
    
    if location:
        job_query = job_query.filter(
            (Job.location_city.ilike(f"%{location}%")) |
            (Job.location_state.ilike(f"%{location}%")) |
            (Job.location_is_remote == True)
        )
    
    jobs = job_query.limit(limit).all()
    
    return jsonify({
        'total': len(jobs),
        'jobs': [job.to_dict() for job in jobs]
    }), 200

@bp.route('/companies', methods=['GET'])
def get_companies():
    """Get list of companies with job counts"""
    companies = Company.query.filter_by(is_active=True).all()
    
    company_list = []
    for company in companies:
        job_count = Job.query.filter_by(
            company_id=company.id,
            is_active=True
        ).count()
        
        if job_count > 0:
            company_list.append({
                'id': company.id,
                'name': company.name,
                'job_count': job_count,
                'logo_url': company.logo_url,
                'website': company.website
            })
    
    return jsonify({
        'total': len(company_list),
        'companies': company_list
    }), 200

@bp.route('/stats', methods=['GET'])
def get_job_stats():
    """Get overall job statistics"""
    from sqlalchemy import func
    from app.models import db
    
    total_jobs = Job.query.filter_by(is_active=True).count()
    total_companies = Company.query.filter_by(is_active=True).count()
    
    # Jobs by seniority
    seniority_stats = db.session.query(
        Job.seniority_level,
        func.count(Job.id)
    ).filter(Job.is_active == True).group_by(Job.seniority_level).all()
    
    # Top locations
    location_stats = db.session.query(
        Job.location_city,
        func.count(Job.id)
    ).filter(
        Job.is_active == True,
        Job.location_city != '',
        Job.location_city != None
    ).group_by(Job.location_city).order_by(func.count(Job.id).desc()).limit(10).all()
    
    return jsonify({
        'total_jobs': total_jobs,
        'total_companies': total_companies,
        'by_seniority': [
            {'level': level, 'count': count}
            for level, count in seniority_stats
        ],
        'top_locations': [
            {'city': city, 'count': count}
            for city, count in location_stats
        ]
    }), 200

@bp.route('/test')
def test():
    return jsonify({'message': 'Jobs route working'}), 200
