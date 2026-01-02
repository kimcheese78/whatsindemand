# backend/app/routes/companies.py

from flask import Blueprint, request, jsonify
from app.models import db, Company, Job, Role
from sqlalchemy import func

companies_bp = Blueprint('companies', __name__, url_prefix='/api/companies')

# In companies.py, add a new endpoint:

@companies_bp.route('/industries', methods=['GET'])
def get_industries():
    """Get all unique industries from companies."""
    from sqlalchemy import func
    
    # Get distinct industries from companies table
    results = db.session.query(Company.industry).filter(
        Company.is_active == True,
        Company.industry.isnot(None)
    ).distinct().order_by(Company.industry).all()
    
    industries = [r[0] for r in results if r[0]]
    
    return jsonify({
        'success': True,
        'industries': industries
    })

@companies_bp.route('', methods=['GET'])
def get_companies():
    """
    Get all companies with job counts.
    
    Query params:
    - min_jobs: minimum number of active jobs (default: 1)
    - industry: filter by industry
    """
    min_jobs = request.args.get('min_jobs', 1, type=int)
    industry = request.args.get('industry')
    
    query = db.session.query(
        Company.id,
        Company.name,
        Company.website,
        Company.logo_url,
        Company.ats_type,
        Company.industry,  # <-- ADD THIS LINE
        func.count(Job.id).label('job_count')
    ).outerjoin(Job, db.and_(
        Job.company_id == Company.id,
        Job.is_active == True
    )).filter(
        Company.is_active == True
    ).group_by(Company.id).having(
        func.count(Job.id) >= min_jobs
    ).order_by(
        func.count(Job.id).desc()
    )
    
    companies = query.all()
    
    return jsonify({
        'success': True,
        'companies': [
            {
                'id': c.id,
                'name': c.name,
                'website': c.website,
                'logo_url': c.logo_url,
                'ats_type': c.ats_type,
                'industry': c.industry,  # <-- ADD THIS LINE
                'job_count': c.job_count
            }
            for c in companies
        ],
        'total': len(companies)
    })


@companies_bp.route('/<int:company_id>', methods=['GET'])
def get_company_details(company_id):
    """Get details for a specific company including roles they're hiring for."""
    company = Company.query.get(company_id)
    
    if not company:
        return jsonify({'success': False, 'error': 'Company not found'}), 404
    
    # Get active job count
    job_count = Job.query.filter(
        Job.company_id == company_id,
        Job.is_active == True
    ).count()
    
    # Get roles they're hiring for
    roles_hiring = db.session.query(
        Role.id,
        Role.normalized_title,
        func.count(Job.id).label('job_count')
    ).join(Job).filter(
        Job.company_id == company_id,
        Job.is_active == True
    ).group_by(Role.id).order_by(
        func.count(Job.id).desc()
    ).limit(10).all()
    
    return jsonify({
        'success': True,
        'company': {
            'id': company.id,
            'name': company.name,
            'website': company.website,
            'logo_url': company.logo_url,
            'ats_type': company.ats_type,
            'job_count': job_count,
            'roles_hiring': [
                {
                    'id': r.id,
                    'title': r.normalized_title,
                    'job_count': r.job_count
                }
                for r in roles_hiring
            ]
        }
    })


@companies_bp.route('/<int:company_id>/skills', methods=['GET'])
def get_company_skill_demand(company_id):
    """Get skill demand for a specific company."""
    company = Company.query.get(company_id)
    
    if not company:
        return jsonify({'success': False, 'error': 'Company not found'}), 404
    
    role = request.args.get('role')
    
    # Build job query
    jobs_query = Job.query.filter(
        Job.company_id == company_id,
        Job.is_active == True
    )
    
    # Optionally filter by role
    if role:
        role_obj = Role.query.filter(
            func.lower(Role.normalized_title) == func.lower(role)
        ).first()
        if role_obj:
            jobs_query = jobs_query.filter(Job.role_id == role_obj.id)
    
    job_ids = [j.id for j in jobs_query.all()]
    total_jobs = len(job_ids)
    
    if total_jobs == 0:
        return jsonify({
            'success': True,
            'company': company.name,
            'skills': [],
            'total_jobs': 0
        })
    
    # Get skill demand
    from app.models import Skill, JobSkill
    
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
    
    skills = [
        {
            'skill_id': skill_id,
            'name': skill_name,
            'category': category or 'technical',
            'job_count': job_count,
            'demand': round(job_count / total_jobs * 100, 1)
        }
        for skill_id, skill_name, category, job_count in skill_counts
    ]
    
    return jsonify({
        'success': True,
        'company': company.name,
        'skills': skills,
        'total_jobs': total_jobs
    })