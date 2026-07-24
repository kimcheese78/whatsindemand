# backend/app/routes/learning.py
"""Learning Tracker — let users mark gap skills as 'learning' and see market
validation of that choice.

The status mutation naturally belongs with user-skill writes; the app's
resume.py blueprint (the historical home for those) is not registered, so these
authed routes live in their own registered blueprint instead.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from app.models import db, Skill, UserSkill, UserProfile, Job, JobSkill, SkillDemand
from app.routes.roles import _find_role
from app.utils.jwt_handler import token_required

learning_bp = Blueprint('learning', __name__, url_prefix='/api/learning')

VALID_STATUSES = {'have', 'learning'}


@learning_bp.route('/skills/<int:skill_id>/status', methods=['POST'])
@token_required
def set_skill_status(skill_id):
    """Mark a skill 'learning' or 'have'. Upserts the user_skills row (a missing
    skill has no row until it's marked), stamping status_changed_at."""
    data = request.get_json() or {}
    status = (data.get('status') or '').strip().lower()
    if status not in VALID_STATUSES:
        return jsonify({'error': f"status must be one of {sorted(VALID_STATUSES)}"}), 400

    if not Skill.query.get(skill_id):
        return jsonify({'error': 'Skill not found'}), 404

    us = UserSkill.query.filter_by(user_id=request.user_id, skill_id=skill_id).first()
    now = datetime.utcnow()
    if us is None:
        us = UserSkill(user_id=request.user_id, skill_id=skill_id, status=status,
                       status_changed_at=now, confidence_score=0, is_custom=False)
        db.session.add(us)
    else:
        us.status = status
        us.status_changed_at = now
    db.session.commit()
    return jsonify({'skill_id': skill_id, 'status': us.status,
                    'status_changed_at': us.status_changed_at.isoformat()})


@learning_bp.route('', methods=['GET'])
@token_required
def get_learning():
    """Each skill the user is learning, with market validation: current demand
    within their target role, weeks since they started, and demand growth since
    then when SkillDemand history covers it (else null)."""
    learning = (db.session.query(UserSkill, Skill)
                .join(Skill, Skill.id == UserSkill.skill_id)
                .filter(UserSkill.user_id == request.user_id,
                        UserSkill.status == 'learning')
                .all())
    if not learning:
        return jsonify({'learning': []})

    profile = UserProfile.query.filter_by(user_id=request.user_id).first()
    role = _find_role(profile.target_role) if profile and profile.target_role else None

    demand_by_skill = {}
    total_role_jobs = 0
    if role:
        total_role_jobs = Job.query.filter_by(role_id=role.id, is_active=True).count()
        sids = [us.skill_id for us, _ in learning]
        rows = db.session.execute(db.text("""
            SELECT js.skill_id, COUNT(DISTINCT j.id) AS c
            FROM jobs j JOIN job_skills js ON js.job_id = j.id
            WHERE j.role_id = :rid AND j.is_active = TRUE AND js.skill_id IN :sids
            GROUP BY js.skill_id
        """).bindparams(db.bindparam('sids', value=sids, expanding=True)),
            {'rid': role.id}).mappings()
        demand_by_skill = {r['skill_id']: r['c'] for r in rows}

    out = []
    for us, skill in learning:
        job_count = demand_by_skill.get(skill.id, 0)
        demand_pct = round(job_count / total_role_jobs * 100, 1) if total_role_jobs else None
        weeks = None
        if us.status_changed_at:
            weeks = max(0, (datetime.utcnow() - us.status_changed_at).days // 7)

        growth_pct = None
        if role and us.status_changed_at:
            growth_pct = _demand_growth(skill.id, role.id, us.status_changed_at.date())

        out.append({
            'skill_id': skill.id,
            'name': skill.name,
            'category': skill.category,
            'started_at': us.status_changed_at.isoformat() if us.status_changed_at else None,
            'weeks_learning': weeks,
            'demand_pct': demand_pct,
            'job_count': job_count,
            'growth_pct': growth_pct,
        })
    out.sort(key=lambda s: (s['demand_pct'] or 0), reverse=True)
    return jsonify({'learning': out})


def _demand_growth(skill_id, role_id, since):
    """Growth in the skill's job_count for this role from the first weekly
    SkillDemand snapshot on/after `since` to the latest. None if history is too
    thin to be meaningful."""
    rows = db.session.execute(db.text("""
        SELECT period_date, job_count FROM skills_demand
        WHERE skill_id = :sk AND role_id = :ro AND period_type = 'week'
          AND period_date >= :since
        ORDER BY period_date ASC
    """), {'sk': skill_id, 'ro': role_id, 'since': since}).fetchall()
    if len(rows) < 2:
        return None
    first, last = rows[0][1], rows[-1][1]
    if not first:
        return None
    return round((last - first) / first * 100, 1)
