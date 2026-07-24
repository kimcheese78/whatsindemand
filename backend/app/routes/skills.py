# backend/app/routes/skills.py

import os
import tempfile
from datetime import datetime
from flask import Blueprint, request, jsonify
from app.models import db, Skill, JobSkill, Job, Role, UserSkill
from app.services.skill_extractor import SkillExtractor
from app.services.resume_parser import ResumeParser
from app.utils.jwt_handler import token_required
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
    
    # Get total jobs requiring this skill — only role-mapped jobs count
    jobs_query = db.session.query(Job.id).join(JobSkill).filter(
        JobSkill.skill_id == skill_id,
        Job.is_active == True,
        Job.role_id.isnot(None)
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
        Job.is_active == True,
        Job.role_id.isnot(None)
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
            'subcategory': skill.subcategory,
            'industry': skill.industry,
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


@skills_bp.route('/<int:skill_id>/co-occurring', methods=['GET'])
def get_co_occurring_skills(skill_id):
    """
    Skills that appear alongside this one in real postings — the learning
    context ("people hired for X are also expected to know Y").

    Query params:
    - role_id: restrict to one role's postings (recommended; without it the
      signal is diluted across unrelated professions)

    Ubiquitous skills (present in >60% of the role's postings) are excluded:
    they co-occur with everything, so they say nothing about THIS skill.
    """
    role_id = request.args.get('role_id', type=int)

    target_filters = [
        JobSkill.skill_id == skill_id,
        Job.is_active == True,
    ]
    if role_id:
        target_filters.append(Job.role_id == role_id)

    target_job_ids = [
        j for (j,) in db.session.query(Job.id).join(JobSkill).filter(*target_filters).all()
    ]
    n_target = len(target_job_ids)
    if n_target < 5:
        return jsonify({'success': True, 'skills': [], 'sample_size': n_target}), 200

    co_rows = db.session.query(
        Skill.id,
        Skill.name,
        Skill.subcategory,
        func.count(JobSkill.job_id).label('co_count')
    ).join(JobSkill, JobSkill.skill_id == Skill.id).filter(
        JobSkill.job_id.in_(target_job_ids),
        JobSkill.skill_id != skill_id,
        Skill.is_verified == True,
    ).group_by(Skill.id).order_by(
        func.count(JobSkill.job_id).desc()
    ).limit(30).all()

    # Base rates within the role, to drop skills that co-occur with everything
    base_pct_map = {}
    if role_id and co_rows:
        n_role = db.session.query(func.count(Job.id)).filter(
            Job.role_id == role_id, Job.is_active == True
        ).scalar() or 0
        if n_role > 0:
            base_rows = db.session.query(
                JobSkill.skill_id,
                func.count(func.distinct(JobSkill.job_id))
            ).join(Job, JobSkill.job_id == Job.id).filter(
                Job.role_id == role_id,
                Job.is_active == True,
                JobSkill.skill_id.in_([r[0] for r in co_rows]),
            ).group_by(JobSkill.skill_id).all()
            base_pct_map = {sid: round(c / n_role * 100, 1) for sid, c in base_rows}

    out = []
    for sid, name, subcategory, co_count in co_rows:
        base_pct = base_pct_map.get(sid)
        if base_pct is not None and base_pct > 60:
            continue
        out.append({
            'skill_id': sid,
            'name': name,
            'subcategory': subcategory,
            'co_pct': round(co_count / n_target * 100, 1),
            'base_pct': base_pct,
        })
        if len(out) >= 8:
            break

    return jsonify({'success': True, 'skills': out, 'sample_size': n_target}), 200


@skills_bp.route('', methods=['GET'])
def get_all_skills():
    """Get all skills organized by category."""
    skills = Skill.query.filter(Skill.is_verified == True).order_by(Skill.category, Skill.name).all()
    
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
            'subcategory': skill.subcategory,
            'industry': skill.industry,
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

# Persist a logged-in user's current skill set to the database. The app keeps
# skills client-side; this upserts them into user_skills (status='have') so the
# retention features (matched jobs, position score, learning tracker) have data
# to read. 'learning' rows are preserved — a skill promoted into the have-set is
# flipped to 'have', not duplicated.
@skills_bp.route('/sync', methods=['POST'])
@token_required
def sync_user_skills():
    data = request.get_json() or {}
    raw = data.get('skill_ids') or []
    try:
        incoming = {int(s) for s in raw}
    except (TypeError, ValueError):
        return jsonify({'error': 'skill_ids must be integers'}), 400

    # Ignore ids that don't exist so a bad client payload can't fail the commit.
    if incoming:
        incoming &= {s.id for s in Skill.query.filter(Skill.id.in_(incoming)).all()}

    existing = {us.skill_id: us for us in
                UserSkill.query.filter_by(user_id=request.user_id).all()}
    now = datetime.utcnow()
    added = removed = promoted = 0

    for sid in incoming:
        us = existing.get(sid)
        if us is None:
            db.session.add(UserSkill(user_id=request.user_id, skill_id=sid,
                                     status='have', confidence_score=100, is_custom=False))
            added += 1
        elif us.status != 'have':
            us.status = 'have'
            us.status_changed_at = now
            promoted += 1

    for sid, us in existing.items():
        if us.status == 'have' and sid not in incoming:
            db.session.delete(us)
            removed += 1

    db.session.commit()
    total_have = UserSkill.query.filter_by(user_id=request.user_id, status='have').count()
    return jsonify({'synced': True, 'added': added, 'removed': removed,
                    'promoted': promoted, 'total_have': total_have})
