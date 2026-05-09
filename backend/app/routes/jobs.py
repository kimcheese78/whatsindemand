from flask import Blueprint, request, jsonify
from app.models import Job, Company
from app.utils.jwt_handler import token_required

bp = Blueprint('jobs', __name__)

@bp.route('/search', methods=['POST'])
@token_required
def search_jobs():
    data = request.get_json() or {}

    query_text = data.get('query', '')
    location = data.get('location')
    limit = int(data.get('limit', 10))

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
    from sqlalchemy import func
    from app.models import db

    rows = db.session.query(
        Company.id,
        Company.name,
        Company.logo_url,
        Company.website,
        func.count(Job.id).label('job_count')
    ).join(Job, (Job.company_id == Company.id) & (Job.is_active == True)
    ).filter(Company.is_active == True
    ).group_by(Company.id
    ).having(func.count(Job.id) > 0
    ).all()

    return jsonify({
        'total': len(rows),
        'companies': [
            {'id': cid, 'name': name, 'logo_url': logo, 'website': website, 'job_count': jc}
            for cid, name, logo, website, jc in rows
        ]
    }), 200


@bp.route('/stats', methods=['GET'])
def get_job_stats():
    from sqlalchemy import func
    from app.models import db

    total_jobs = Job.query.filter_by(is_active=True).count()
    total_companies = Company.query.filter_by(is_active=True).count()

    seniority_stats = db.session.query(
        Job.seniority_level,
        func.count(Job.id)
    ).filter(Job.is_active == True).group_by(Job.seniority_level).all()

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
