"""Admin API for the weekly pipeline review.

The claude.ai cloud routine cannot reach the Railway Postgres directly
(its egress proxy blocks raw TCP to non-443 ports), so it drives the
review pipeline over HTTPS through these endpoints instead:

  GET  /api/admin/pipeline/queues          — scrape stats + pending queues + reference data
  POST /api/admin/pipeline/skill-decisions — promote/reject skill candidates
  POST /api/admin/pipeline/role-decisions  — map/reject unmatched titles

Auth: Authorization: Bearer $ADMIN_TOKEN (set in Railway env vars).
Extraction and backfill are NOT exposed here — they run on Railway in
scripts/agent_run.py, which sits next to the database.
"""
import os
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request

from app.models import db, Skill

bp = Blueprint('pipeline_admin', __name__)


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = os.environ.get('ADMIN_TOKEN')
        if not token:
            return jsonify({'error': 'ADMIN_TOKEN not configured'}), 503
        if request.headers.get('Authorization', '') != f'Bearer {token}':
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return wrapper


def _queue_counts():
    sc = db.session.execute(db.text(
        "SELECT COUNT(*) FROM skill_candidates WHERE status='pending' AND company_count >= 2"
    )).scalar()
    ut = db.session.execute(db.text(
        "SELECT COUNT(*) FROM unmatched_titles WHERE status='pending'"
    )).scalar()
    dirty = db.session.execute(db.text(
        "SELECT COUNT(*) FROM jobs WHERE skills_dirty=true"
        " AND description_text IS NOT NULL AND description_text != ''"
    )).scalar()
    return {'skill_candidates_pending': sc, 'unmatched_titles_pending': ut, 'dirty_jobs': dirty}


@bp.route('/queues', methods=['GET'])
@require_admin
def get_queues():
    from scripts.ai_map_roles import fetch_jd_snippets

    # Scrape stats
    dr = db.session.execute(db.text(
        "SELECT id, started_at, completed_at, jobs_processed, candidates_upserted, status, error"
        " FROM discovery_runs ORDER BY id DESC LIMIT 1"
    )).fetchone()
    new_jobs = db.session.execute(db.text(
        "SELECT COUNT(*) FROM jobs WHERE scraped_at >= NOW() - INTERVAL '7 days'"
    )).scalar()
    new_cos = db.session.execute(db.text(
        "SELECT COUNT(DISTINCT company_id) FROM jobs WHERE scraped_at >= NOW() - INTERVAL '7 days'"
    )).scalar()

    # Skill candidate queue + taxonomy reference
    cand_rows = db.session.execute(db.text("""
        SELECT id, name, job_count, company_count, example_contexts
        FROM skill_candidates
        WHERE status = 'pending' AND company_count >= 2
        ORDER BY company_count DESC, job_count DESC LIMIT 300
    """)).fetchall()
    candidates = [{'id': r[0], 'name': r[1], 'job_count': r[2],
                   'company_count': r[3], 'contexts': list(r[4] or [])} for r in cand_rows]
    skills = db.session.execute(db.text(
        "SELECT name, aliases FROM skills WHERE is_verified=true"
    )).fetchall()
    taxonomy = [s[0] for s in skills] + [a for s in skills for a in (s[1] or [])]

    # Role queue + canonical roles reference
    title_rows = db.session.execute(db.text("""
        SELECT id, raw_title, job_count FROM unmatched_titles
        WHERE status='pending' ORDER BY job_count DESC LIMIT 400
    """)).fetchall()
    titles = [{'id': r[0], 'raw_title': r[1], 'job_count': r[2]} for r in title_rows]
    jd_map = fetch_jd_snippets([t['raw_title'] for t in titles])
    for t in titles:
        info = jd_map.get(t['raw_title'], {})
        t['dept'] = info.get('department', '')
        t['jd'] = (info.get('jd', '') or '')[:250]
    role_rows = db.session.execute(db.text(
        'SELECT id, normalized_title, category, job_family FROM roles ORDER BY category, normalized_title'
    )).fetchall()
    canonical_roles = [{'id': r[0], 'title': r[1], 'category': r[2], 'job_family': r[3]}
                       for r in role_rows]

    return jsonify({
        'scrape': {
            'latest_discovery_run': dict(dr._mapping) if dr else None,
            'new_jobs_7d': new_jobs,
            'companies_with_new_jobs_7d': new_cos,
        },
        'queue_counts': _queue_counts(),
        'skill_candidates': candidates,
        'existing_taxonomy': taxonomy,
        'unmatched_titles': titles,
        'canonical_roles': canonical_roles,
    })


@bp.route('/skill-decisions', methods=['POST'])
@require_admin
def apply_skill_decisions():
    """Body: {"keeps": [{"candidate_id", "name", "category", "subcategory",
    "aliases", "job_count"}...], "drop_ids": [...]}"""
    from scripts.discover_new_skills import _build_taxonomy_set, _is_in_taxonomy

    body = request.get_json(force=True) or {}
    keeps = body.get('keeps', [])
    drop_ids = body.get('drop_ids', [])

    taxonomy_set = _build_taxonomy_set(Skill.query.all())
    inserted, skipped_dup = 0, 0
    new_ids = []
    now = datetime.utcnow()

    for entry in keeps:
        canonical = entry['name']
        cid = entry['candidate_id']

        exact = Skill.query.filter(db.func.lower(Skill.name) == canonical.lower()).first()
        if exact or _is_in_taxonomy(canonical.lower(), taxonomy_set):
            if exact and entry.get('subcategory') and not exact.subcategory:
                exact.subcategory = entry['subcategory']
            db.session.execute(db.text(
                "UPDATE skill_candidates SET status='rejected', rejected_reason='already_in_taxonomy'"
                " WHERE id=:cid"
            ), {'cid': cid})
            skipped_dup += 1
            continue

        skill = Skill(
            name=canonical,
            category=entry['category'].lower(),
            subcategory=entry.get('subcategory') or None,
            aliases=entry.get('aliases') or [],
            is_verified=True,
            total_job_count=entry.get('job_count', 0),
            trending_score=0.0,
            created_at=now,
            updated_at=now,
        )
        db.session.add(skill)
        db.session.flush()
        new_ids.append(skill.id)

        # Backfill job_skills from the candidate's known jobs
        db.session.execute(db.text("""
            INSERT INTO job_skills (job_id, skill_id, is_required, created_at)
            SELECT scj.job_id, :sid, true, NOW()
            FROM skill_candidate_jobs scj
            WHERE scj.candidate_id = :cid
            AND NOT EXISTS (
                SELECT 1 FROM job_skills js
                WHERE js.job_id = scj.job_id AND js.skill_id = :sid
            )
        """), {'sid': skill.id, 'cid': cid})
        db.session.execute(db.text("""
            UPDATE skill_candidates
            SET status='approved', promoted_skill_id=:sid, promoted_at=NOW()
            WHERE id=:cid
        """), {'sid': skill.id, 'cid': cid})

        taxonomy_set.add(canonical.lower())
        for a in (entry.get('aliases') or []):
            taxonomy_set.add(a.lower())
        inserted += 1

    rejected = 0
    if drop_ids:
        result = db.session.execute(db.text(
            "UPDATE skill_candidates SET status='rejected', rejected_reason='ai_triage_dropped'"
            " WHERE id = ANY(:ids) AND status='pending'"
        ), {'ids': drop_ids})
        rejected = result.rowcount

    db.session.commit()
    return jsonify({
        'inserted': inserted,
        'skipped_duplicates': skipped_dup,
        'rejected': rejected,
        'new_skill_ids': new_ids,
        'queue_counts': _queue_counts(),
    })


@bp.route('/role-decisions', methods=['POST'])
@require_admin
def apply_role_decisions():
    """Body: {"decisions": [...ai_role_decisions.json shape...],
    "reject_remaining": bool}. Returns alias entries for the caller to
    commit to backend/data/aliases.yaml (the normalizer is file-based and
    Railway's filesystem is ephemeral, so persistence happens via git)."""
    from scripts.ai_map_roles import apply_decisions, compute_alias_entries, load_canonical_roles

    body = request.get_json(force=True) or {}
    decisions = body.get('decisions', [])
    reject_remaining = bool(body.get('reject_remaining', False))

    role_map = {r['title'].lower(): r['id'] for r in load_canonical_roles()}
    stats = apply_decisions(decisions, role_map) if decisions else {}
    alias_entries = compute_alias_entries(decisions) if decisions else []

    bulk_rejected = 0
    if reject_remaining:
        result = db.session.execute(db.text(
            "UPDATE unmatched_titles SET status='rejected', rejected_reason='ai_triage_dropped'"
            " WHERE status='pending'"
        ))
        bulk_rejected = result.rowcount
        db.session.commit()

    return jsonify({
        'stats': dict(stats),
        'bulk_rejected': bulk_rejected,
        'alias_entries': [{'title': t, 'canonical_id': c} for t, c in alias_entries],
        'queue_counts': _queue_counts(),
    })
