# backend/app/routes/skill_gap.py

from flask import Blueprint, request, jsonify
from app.services.skill_gap_analyzer import SkillGapAnalyzer
from app.models import UserSkill
from app.utils.jwt_handler import token_required

skill_gap_bp = Blueprint('skill_gap', __name__, url_prefix='/api/skill-gap')
analyzer = SkillGapAnalyzer()


@skill_gap_bp.route('/roles', methods=['GET'])
def get_available_roles():
    """Get all available roles for selection"""
    min_jobs = request.args.get('min_jobs', type=int)
    roles = analyzer.get_available_roles(min_jobs=min_jobs)
    return jsonify({'success': True, 'roles': roles, 'total': len(roles)})


@skill_gap_bp.route('/skills', methods=['GET'])
def get_skills_for_selection():
    """Get all skills organized by category"""
    skills = analyzer.get_skills_for_selection()
    return jsonify({'success': True, 'skills': skills})


@skill_gap_bp.route('/analyze', methods=['POST'])
@token_required
def analyze_skill_gap():
    """Analyze skill gap using user's saved skills"""
    data = request.get_json() or {}
    
    target_role = data.get('target_role') or data.get('role')
    if not target_role:
        return jsonify({'success': False, 'error': 'target_role is required'}), 400
    
    user_skills = UserSkill.query.filter_by(user_id=request.user_id).all()
    user_skill_ids = [us.skill_id for us in user_skills]
    
    result = analyzer.analyze_gap(
        target_role=target_role,
        user_skill_ids=user_skill_ids,
        seniority_filter=data.get('seniority'),
        location_filter=data.get('location')
    )
    return jsonify(result)


@skill_gap_bp.route('/analyze/preview', methods=['POST'])
def analyze_skill_gap_preview():
    """Analyze skill gap without auth (accepts skill_ids directly)"""
    data = request.get_json() or {}
    
    target_role = data.get('target_role') or data.get('role')
    if not target_role:
        return jsonify({'success': False, 'error': 'target_role is required'}), 400
    
    result = analyzer.analyze_gap(
        target_role=target_role,
        user_skill_ids=data.get('skill_ids', []),
        seniority_filter=data.get('seniority'),
        location_filter=data.get('location')
    )
    return jsonify(result)