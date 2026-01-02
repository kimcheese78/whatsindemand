# backend/app/routes/skills.py

from flask import Blueprint, request, jsonify
from app.models import db, Skill, JobSkill, Job, Role
from sqlalchemy import func

skills_bp = Blueprint('skills', __name__, url_prefix='/api/skills')


@skills_bp.route('/<int:skill_id>', methods=['GET'])
def get_skill_details(skill_id):
    """
    Get details for a specific skill.
    
    Query params:
    - role: filter demand stats by role
    """
    skill = Skill.query.get(skill_id)
    
    if not skill:
        return jsonify({'success': False, 'error': 'Skill not found'}), 404
    
    role_name = request.args.get('role')
    
    # Get total jobs requiring this skill
    jobs_query = db.session.query(Job.id).join(JobSkill).filter(
        JobSkill.skill_id == skill_id,
        Job.is_active == True
    )
    
    role_obj = None
    if role_name:
        role_obj = Role.query.filter(
            func.lower(Role.normalized_title) == func.lower(role_name)
        ).first()
        if role_obj:
            jobs_query = jobs_query.filter(Job.role_id == role_obj.id)
    
    total_jobs = jobs_query.count()
    
    # Get top roles requiring this skill
    top_roles = db.session.query(
        Role.id,
        Role.normalized_title,
        func.count(Job.id).label('job_count')
    ).join(Job).join(JobSkill).filter(
        JobSkill.skill_id == skill_id,
        Job.is_active == True
    ).group_by(Role.id).order_by(
        func.count(Job.id).desc()
    ).limit(5).all()
    
    # Get top companies requiring this skill
    from app.models import Company
    
    top_companies = db.session.query(
        Company.id,
        Company.name,
        func.count(Job.id).label('job_count')
    ).join(Job).join(JobSkill).filter(
        JobSkill.skill_id == skill_id,
        Job.is_active == True
    ).group_by(Company.id).order_by(
        func.count(Job.id).desc()
    ).limit(5).all()
    
    # Calculate demand percentage for the specific role
    demand_percentage = None
    if role_obj:
        total_role_jobs = Job.query.filter(
            Job.role_id == role_obj.id,
            Job.is_active == True
        ).count()
        if total_role_jobs > 0:
            demand_percentage = round(total_jobs / total_role_jobs * 100, 1)
    
    return jsonify({
        'success': True,
        'skill': {
            'id': skill.id,
            'name': skill.name,
            'category': skill.category,
            'total_job_count': total_jobs,
            'demand_percentage': demand_percentage,
            'trending_score': skill.trending_score
        },
        'top_roles': [
            {'id': r.id, 'title': r.normalized_title, 'job_count': r.job_count}
            for r in top_roles
        ],
        'top_companies': [
            {'id': c.id, 'name': c.name, 'job_count': c.job_count}
            for c in top_companies
        ],
        'context': {
            'role': role_name,
            'jobs_in_role': total_jobs
        }
    })


@skills_bp.route('', methods=['GET'])
def get_all_skills():
    """Get all skills organized by category."""
    skills = Skill.query.order_by(Skill.category, Skill.name).all()
    
    categorized = {
        'technical': [],
        'soft': [],
        'domain': [],
        'other': []
    }
    
    for skill in skills:
        skill_data = {
            'id': skill.id,
            'name': skill.name,
            'category': skill.category,
            'total_job_count': skill.total_job_count,
            'trending_score': skill.trending_score
        }
        category = skill.category or 'other'
        if category in categorized:
            categorized[category].append(skill_data)
        else:
            categorized['other'].append(skill_data)
    
    return jsonify({
        'success': True,
        'skills': categorized,
        'total': len(skills)
    })