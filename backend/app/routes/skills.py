# backend/app/routes/skills.py

import os
import tempfile
from flask import Blueprint, request, jsonify
from app.models import db, Skill, JobSkill, Job, Role
from app.services.skill_extractor import SkillExtractor
from app.services.resume_parser import ResumeParser
from app import limiter
from sqlalchemy import func

skills_bp = Blueprint('skills', __name__, url_prefix='/api/skills')


# Public, stateless skill extraction — used by the onboarding flow before signup.
# Auth-gated persistence still lives in /api/resume.
@skills_bp.route('/extract', methods=['POST'])
@limiter.limit("5 per minute; 20 per hour")
def extract_skills_from_input():
    """
    Extract skills from pasted text or an uploaded resume file.

    Accepts either:
      - multipart/form-data with `file` (PDF/DOCX), or
      - JSON `{"text": "..."}`

    Returns: { "skills": [{skill_id, name, category, confidence}, ...] }
    """
    text = None

    if 'file' in request.files:
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in {'pdf', 'docx', 'doc', 'txt'}:
            return jsonify({'error': 'Unsupported file type. Use PDF, DOCX, or TXT.'}), 400

        # Hard cap: 5MB
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > 5 * 1024 * 1024:
            return jsonify({'error': 'File too large (max 5MB).'}), 400

        try:
            if ext == 'txt':
                text = file.read().decode('utf-8', errors='ignore')
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name
                try:
                    text = ResumeParser().extract_text(tmp_path)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
        except Exception as e:
            return jsonify({'error': f'Could not read file: {e}'}), 400
    else:
        body = request.get_json(silent=True) or {}
        text = (body.get('text') or '').strip()

    if not text or len(text) < 30:
        return jsonify({'error': 'Not enough text to extract skills from.'}), 400

    # document_type='resume' skips JD section filtering and matches against full text
    body = request.get_json(silent=True) or {}
    is_resume = (body.get('document_type') == 'resume') or ('file' in request.files)

    extractor = SkillExtractor()
    extracted = extractor.extract_skills(text, is_resume=is_resume)

    # Hydrate with skill metadata
    skill_ids = [s['skill_id'] for s in extracted]
    skill_rows = {s.id: s for s in Skill.query.filter(Skill.id.in_(skill_ids)).all()} if skill_ids else {}

    skills_out = []
    for s in extracted:
        row = skill_rows.get(s['skill_id'])
        if not row:
            continue
        skills_out.append({
            'skill_id': row.id,
            'name': row.name,
            'category': row.category,
            'confidence': s['confidence'],
        })

    return jsonify({'skills': skills_out, 'total': len(skills_out)}), 200


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