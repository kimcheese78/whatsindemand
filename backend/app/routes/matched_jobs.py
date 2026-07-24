# backend/app/routes/matched_jobs.py
"""Matched Jobs — live postings where the user's skills cover most of the
job's extracted skills.

Match % = (verified job skills the user has) / (job's verified skill count).
Only jobs with >= 3 verified skills are considered (below that the ratio is
noise). Everything is computed in one aggregation query per request (plus one
small query to name the matched/missing skills for the visible slice) — no
per-job Python loops.
"""
from flask import Blueprint, request, jsonify
from app.models import db, User, UserProfile, UserSkill
from app.routes.roles import _find_role
from app.utils.jwt_handler import token_required

matched_jobs_bp = Blueprint('matched_jobs', __name__, url_prefix='/api/matched-jobs')

MATCH_THRESHOLD = 0.6   # minimum skill coverage to count as a match
MIN_SKILLS = 3          # jobs with fewer verified skills are excluded
LIST_LIMIT = 50         # max rows the detailed list returns

# One aggregation query. `agg` counts the job's verified skills and how many the
# user has; the outer WHERE applies the >=3 and >=60% thresholds; the window
# functions yield total qualifying count + new-this-week count regardless of the
# LIMIT (windows run before LIMIT), so a single query serves both the list and
# the summary.
_MATCH_SQL = """
SELECT id, title, company_name, logo_url,
       location_city, location_state, location_country, location_is_remote,
       seniority_level, posted_at, source_url, match_pct, new_this_week,
       COUNT(*) OVER () AS total_count,
       SUM(CASE WHEN new_this_week THEN 1 ELSE 0 END) OVER () AS new_count
FROM (
  SELECT q.*, (q.matched::float / q.total_skills) AS match_pct,
         (COALESCE(q.posted_at, q.scraped_at) >= NOW() - INTERVAL '7 days') AS new_this_week
  FROM (
    SELECT j.id, j.title, c.name AS company_name, c.logo_url,
           j.location_city, j.location_state, j.location_country,
           j.location_is_remote, j.seniority_level, j.posted_at,
           j.scraped_at, j.source_url,
           COUNT(*) FILTER (WHERE s.is_verified) AS total_skills,
           COUNT(*) FILTER (WHERE s.is_verified AND js.skill_id IN :uids) AS matched
    FROM jobs j
    JOIN companies c ON c.id = j.company_id
    JOIN job_skills js ON js.job_id = j.id
    JOIN skills s ON s.id = js.skill_id
    WHERE j.is_active = TRUE AND j.role_id = :rid
    GROUP BY j.id, c.name, c.logo_url
  ) q
  WHERE q.total_skills >= :min_skills
    AND q.matched >= :threshold * q.total_skills
) scored
ORDER BY match_pct DESC, posted_at DESC NULLS LAST
LIMIT :lim
"""

_SKILL_NAMES_SQL = """
SELECT js.job_id, s.id AS skill_id, s.name
FROM job_skills js
JOIN skills s ON s.id = js.skill_id
WHERE js.job_id IN :job_ids AND s.is_verified = TRUE
"""


def _resolve_context(user_id):
    """Return (user, user_skill_ids:set, role) or (user, set, None) if the user
    has no target role / no skills / the role can't be resolved."""
    user = User.query.get(user_id)
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    # Only skills the user actually has count toward coverage — 'learning' rows
    # (Learning Tracker) are aspirational and must not inflate the match.
    skill_ids = {us.skill_id for us in
                 UserSkill.query.filter_by(user_id=user_id, status='have').all()}

    role = None
    if profile and profile.target_role and skill_ids:
        role = _find_role(profile.target_role)
    return user, skill_ids, role


def _query_matches(role_id, skill_ids, limit):
    """Run the aggregation. Returns (rows, total_count, new_count)."""
    stmt = db.text(_MATCH_SQL).bindparams(
        db.bindparam('uids', value=sorted(skill_ids), expanding=True)
    )
    rows = db.session.execute(stmt, {
        'rid': role_id,
        'min_skills': MIN_SKILLS,
        'threshold': MATCH_THRESHOLD,
        'lim': limit,
    }).mappings().all()
    if not rows:
        return [], 0, 0
    return rows, rows[0]['total_count'], rows[0]['new_count']


def _skill_split(job_ids, skill_ids):
    """For the given jobs, return {job_id: (matched_names, missing_names)}
    using verified skills only."""
    if not job_ids:
        return {}
    stmt = db.text(_SKILL_NAMES_SQL).bindparams(
        db.bindparam('job_ids', value=list(job_ids), expanding=True)
    )
    matched, missing = {}, {}
    for r in db.session.execute(stmt).mappings():
        bucket = matched if r['skill_id'] in skill_ids else missing
        bucket.setdefault(r['job_id'], []).append(r['name'])
    return {jid: (matched.get(jid, []), missing.get(jid, [])) for jid in job_ids}


def _serialize(row, names):
    matched_names, missing_names = names
    return {
        'id': row['id'],
        'title': row['title'],
        'company': row['company_name'],
        'logo_url': row['logo_url'],
        'location': {
            'city': row['location_city'],
            'state': row['location_state'],
            'country': row['location_country'],
            'is_remote': row['location_is_remote'],
        },
        'seniority_level': row['seniority_level'],
        'posted_at': row['posted_at'].isoformat() if row['posted_at'] else None,
        'source_url': row['source_url'],
        'match_pct': round(row['match_pct'], 3),
        'new_this_week': row['new_this_week'],
        'matched_skills': matched_names,
        'missing_skills': missing_names[:5],
    }


@matched_jobs_bp.route('', methods=['GET'])
@token_required
def get_matched_jobs():
    """Ranked matches — all of them (up to LIST_LIMIT), available to every user."""
    user, skill_ids, role = _resolve_context(request.user_id)
    if role is None:
        return jsonify({'matches': [], 'total_matches': 0, 'new_this_week': 0,
                        'locked_count': 0, 'is_pro': bool(user and user.has_pro_access)})

    rows, total, new_count = _query_matches(role.id, skill_ids, LIST_LIMIT)
    names = _skill_split([r['id'] for r in rows], skill_ids)
    matches = [_serialize(r, names.get(r['id'], ([], []))) for r in rows]

    return jsonify({
        'matches': matches,
        'total_matches': total,
        'new_this_week': new_count,
        'locked_count': 0,
        'is_pro': bool(user and user.has_pro_access),
    })


@matched_jobs_bp.route('/summary', methods=['GET'])
@token_required
def get_matched_jobs_summary():
    """Compact counts for the dashboard card and the weekly digest."""
    user, skill_ids, role = _resolve_context(request.user_id)
    if role is None:
        return jsonify({'total_matches': 0, 'new_this_week': 0, 'top_match': None})

    rows, total, new_count = _query_matches(role.id, skill_ids, 1)
    top = None
    if rows:
        r = rows[0]
        top = {'title': r['title'], 'company': r['company_name'],
               'match_pct': round(r['match_pct'], 3)}
    return jsonify({'total_matches': total, 'new_this_week': new_count, 'top_match': top})
