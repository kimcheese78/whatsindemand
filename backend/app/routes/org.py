# backend/app/routes/org.py
"""B2B coach console — organizations, cohorts, managed clients.

Serves bootcamp career-services teams (Phase 1 of the B2B tier). A managed
Client reuses the consumer per-user machinery: skills live in user_skills
(client_id rows), weekly Position Score history in user_week_snapshots, and
matched jobs / skill gap reuse the shipped query helpers. The console is built
around at-a-glance reads: the cohort rollup and curriculum-fit endpoints return
everything a coach needs without further drilling.
"""
import json
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.models import (db, Client, Cohort, Organization, OrgMembership,
                        Skill, User, UserSkill, UserWeekSnapshot)
from app.routes.matched_jobs import _query_matches, _skill_split, _serialize
from app.services.skill_gap_analyzer import SkillGapAnalyzer
from app.utils.jwt_handler import token_required

org_bp = Blueprint('org', __name__, url_prefix='/api/org')
analyzer = SkillGapAnalyzer()

SNAPSHOT_HISTORY_WEEKS = 12
CURRICULUM_TOP_MARKET = 40   # market skills considered for coverage/emerging
EMERGING_GROWTH_PCT = 5      # growth threshold for "emerging" flag


# ── Auth ──────────────────────────────────────────────────────────────────────

def require_org(*roles):
    """Auth guard: valid JWT + membership in an org (optionally restricted to
    given roles). Sets request.org_id / request.org_role."""
    def decorator(f):
        @wraps(f)
        @token_required
        def wrapped(*args, **kwargs):
            m = OrgMembership.query.filter_by(user_id=request.user_id).first()
            if m is None:
                return jsonify({'error': 'No organization membership'}), 403
            if roles and m.role not in roles:
                return jsonify({'error': 'Insufficient org role'}), 403
            request.org_id = m.org_id
            request.org_role = m.role
            return f(*args, **kwargs)
        return wrapped
    return decorator


def _own(model, obj_id):
    """Fetch an org-scoped object, enforcing tenancy."""
    obj = model.query.get(obj_id)
    if obj is None or obj.org_id != request.org_id:
        return None
    return obj


# ── Snapshot computation for managed clients ─────────────────────────────────

def _snapshot_utils():
    """Score helpers live in the weekly script; import lazily and tolerate the
    web app's differing sys.path."""
    try:
        from scripts.compute_week_snapshots import (compute_components,
                                                    compute_drivers,
                                                    iso_week_start)
    except ImportError:
        import os
        import sys
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.path.insert(0, backend_dir)
        from scripts.compute_week_snapshots import (compute_components,
                                                    compute_drivers,
                                                    iso_week_start)
    return compute_components, compute_drivers, iso_week_start


def _get_insights(role_title, cache):
    """Role insights via the same internal-HTTP pattern as the weekly digest,
    cached per role so a cohort costs one computation."""
    if role_title in cache:
        return cache[role_title]
    resp = current_app.test_client().post('/api/roles/insights',
                                          json={'role': role_title})
    ok = resp.status_code == 200 and (resp.get_json() or {}).get('success')
    cache[role_title] = resp.get_json() if ok else None
    return cache[role_title]


def compute_client_snapshot(client, insights_cache, commit=False):
    """Compute + upsert this ISO week's snapshot for a managed client.
    Returns the snapshot or None (no role / no skills / insights unavailable)."""
    compute_components, compute_drivers, iso_week_start = _snapshot_utils()

    if not client.target_role:
        return None
    skill_ids = {us.skill_id for us in
                 UserSkill.query.filter_by(client_id=client.id, status='have').all()}
    if not skill_ids:
        return None
    insights = _get_insights(client.target_role, insights_cache)
    if not insights or not insights.get('total_jobs_analyzed'):
        return None

    comp = compute_components(insights, skill_ids)
    drivers = compute_drivers(comp['top30'], skill_ids)
    role_id = (insights.get('role') or {}).get('id')
    _, matched_total, matched_new = (
        _query_matches(role_id, skill_ids, 1) if role_id else ([], 0, 0))

    week_start = iso_week_start()
    snap = UserWeekSnapshot.query.filter_by(
        client_id=client.id, week_start=week_start).first()
    if snap is None:
        snap = UserWeekSnapshot(client_id=client.id, week_start=week_start)
        db.session.add(snap)
    snap.position_score = comp['score']
    snap.match_pct = round(comp['coverage'], 4)
    snap.market_momentum = comp['raw_growth']
    snap.ai_exposure = comp['ai_pct']
    snap.matched_jobs_count = matched_total
    snap.new_matched_jobs = matched_new
    snap.details_json = json.dumps({
        'components': {
            'skill_coverage': round(comp['coverage'], 4),
            'momentum': round(comp['momentum'], 4),
            'ai_exposure_norm': round(comp['ai_norm'], 4),
        },
        'weights': {'skill_coverage': 55, 'momentum': 25, 'ai_low_exposure': 20},
        'drivers': drivers,
    })
    if commit:
        db.session.commit()
    return snap


def _replace_client_skills(client, skill_ids):
    """Replace a client's 'have' skills; keeps 'learning' rows untouched."""
    valid = {s.id for s in Skill.query.filter(Skill.id.in_(skill_ids)).all()} if skill_ids else set()
    existing = {us.skill_id: us for us in
                UserSkill.query.filter_by(client_id=client.id).all()}
    now = datetime.utcnow()
    for sid in valid:
        us = existing.get(sid)
        if us is None:
            db.session.add(UserSkill(client_id=client.id, skill_id=sid,
                                     status='have', confidence_score=100,
                                     is_custom=False))
        elif us.status != 'have':
            us.status = 'have'
            us.status_changed_at = now
    for sid, us in existing.items():
        if us.status == 'have' and sid not in valid:
            db.session.delete(us)


# ── Organization + membership ────────────────────────────────────────────────

@org_bp.route('', methods=['GET'])
@token_required
def get_my_org():
    m = OrgMembership.query.filter_by(user_id=request.user_id).first()
    if m is None:
        return jsonify({'organization': None})
    org = Organization.query.get(m.org_id)
    return jsonify({'organization': org.to_dict(), 'role': m.role,
                    'cohort_count': Cohort.query.filter_by(org_id=org.id).count(),
                    'client_count': Client.query.filter_by(org_id=org.id).count()})


@org_bp.route('', methods=['POST'])
@token_required
def create_org():
    if OrgMembership.query.filter_by(user_id=request.user_id).first():
        return jsonify({'error': 'You already belong to an organization'}), 400
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    org = Organization(name=name,
                       org_type=data.get('org_type') or 'bootcamp')
    db.session.add(org)
    db.session.flush()
    db.session.add(OrgMembership(org_id=org.id, user_id=request.user_id, role='admin'))
    db.session.commit()
    return jsonify({'organization': org.to_dict(), 'role': 'admin'}), 201


@org_bp.route('/members', methods=['POST'])
@require_org('admin')
def add_member():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    role = data.get('role') or 'coach'
    if role not in ('admin', 'coach'):
        return jsonify({'error': 'role must be admin or coach'}), 400
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user is None:
        return jsonify({'error': 'No account with that email — they must sign up first'}), 404
    if OrgMembership.query.filter_by(user_id=user.id).first():
        return jsonify({'error': 'That user already belongs to an organization'}), 409
    db.session.add(OrgMembership(org_id=request.org_id, user_id=user.id, role=role))
    db.session.commit()
    return jsonify({'added': email, 'role': role}), 201


# ── Cohorts ──────────────────────────────────────────────────────────────────

def _cohort_payload(data, cohort):
    if 'name' in data:
        cohort.name = (data.get('name') or '').strip() or cohort.name
    if 'target_role' in data:
        cohort.target_role = data.get('target_role')
    if 'curriculum_skill_ids' in data:
        ids = data.get('curriculum_skill_ids') or []
        cohort.curriculum_skill_ids = [int(i) for i in ids]
    for field in ('start_date', 'end_date'):
        if field in data and data[field]:
            setattr(cohort, field, date.fromisoformat(data[field]))


@org_bp.route('/cohorts', methods=['GET'])
@require_org()
def list_cohorts():
    cohorts = Cohort.query.filter_by(org_id=request.org_id).order_by(Cohort.created_at.desc()).all()
    counts = dict(db.session.query(Client.cohort_id, db.func.count(Client.id))
                  .filter(Client.org_id == request.org_id)
                  .group_by(Client.cohort_id).all())
    return jsonify({'cohorts': [{**c.to_dict(), 'client_count': counts.get(c.id, 0)}
                                for c in cohorts]})


@org_bp.route('/cohorts', methods=['POST'])
@require_org()
def create_cohort():
    data = request.get_json() or {}
    if not (data.get('name') or '').strip():
        return jsonify({'error': 'name is required'}), 400
    cohort = Cohort(org_id=request.org_id, name=data['name'].strip())
    _cohort_payload(data, cohort)
    db.session.add(cohort)
    db.session.commit()
    return jsonify({'cohort': cohort.to_dict()}), 201


@org_bp.route('/cohorts/<int:cohort_id>', methods=['PATCH'])
@require_org()
def update_cohort(cohort_id):
    cohort = _own(Cohort, cohort_id)
    if cohort is None:
        return jsonify({'error': 'Cohort not found'}), 404
    _cohort_payload(request.get_json() or {}, cohort)
    db.session.commit()
    return jsonify({'cohort': cohort.to_dict()})


@org_bp.route('/cohorts/<int:cohort_id>/rollup', methods=['GET'])
@require_org()
def cohort_rollup(cohort_id):
    """The at-a-glance view: cohort-level stats + one row per client with
    score/delta, top gap, matches, learning — all read from stored snapshots
    (fast), no per-client recomputation."""
    cohort = _own(Cohort, cohort_id)
    if cohort is None:
        return jsonify({'error': 'Cohort not found'}), 404

    clients = Client.query.filter_by(cohort_id=cohort.id).order_by(Client.display_name).all()
    client_ids = [c.id for c in clients]

    latest, previous, weeks = {}, {}, {}
    if client_ids:
        rows = db.session.execute(db.text("""
            SELECT client_id, week_start, position_score, matched_jobs_count,
                   new_matched_jobs, details_json,
                   ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY week_start DESC) rn,
                   COUNT(*) OVER (PARTITION BY client_id) total
            FROM user_week_snapshots WHERE client_id IN :ids
        """).bindparams(db.bindparam('ids', value=client_ids, expanding=True))).mappings()
        for r in rows:
            weeks[r['client_id']] = r['total']
            if r['rn'] == 1:
                latest[r['client_id']] = r
            elif r['rn'] == 2:
                previous[r['client_id']] = r

    learning = dict(db.session.query(UserSkill.client_id, db.func.count(UserSkill.id))
                    .filter(UserSkill.client_id.in_(client_ids or [0]),
                            UserSkill.status == 'learning')
                    .group_by(UserSkill.client_id).all())

    out, scores, deltas, new_matches_total = [], [], [], 0
    for c in clients:
        cur, prev = latest.get(c.id), previous.get(c.id)
        score = cur['position_score'] if cur else None
        delta = (score - prev['position_score']
                 if cur and prev and score is not None
                 and prev['position_score'] is not None else None)
        top_gap = None
        if cur and cur['details_json']:
            try:
                drivers = (json.loads(cur['details_json']) or {}).get('drivers') or []
                if drivers:
                    top_gap = drivers[0].get('skill')
            except (ValueError, TypeError):
                pass
        if score is not None:
            scores.append(score)
        if delta is not None:
            deltas.append(delta)
        new_matches_total += (cur['new_matched_jobs'] or 0) if cur else 0
        out.append({
            'id': c.id, 'display_name': c.display_name,
            'target_role': c.target_role, 'seniority': c.seniority,
            'score': score, 'delta': delta, 'top_gap': top_gap,
            'matched_jobs': cur['matched_jobs_count'] if cur else None,
            'new_matches': cur['new_matched_jobs'] if cur else None,
            'learning_count': learning.get(c.id, 0),
            'weeks_tracked': weeks.get(c.id, 0),
        })

    coverage = None
    if cohort.target_role and cohort.curriculum_skill_ids:
        gap = analyzer.analyze_gap(cohort.target_role, cohort.curriculum_skill_ids)
        if gap.get('success'):
            coverage = gap['analysis']['match_score']

    return jsonify({
        'cohort': cohort.to_dict(),
        'stats': {
            'clients': len(clients),
            'avg_score': round(sum(scores) / len(scores)) if scores else None,
            'avg_delta': round(sum(deltas) / len(deltas), 1) if deltas else None,
            'new_matches_this_week': new_matches_total,
            'learning_total': sum(learning.values()),
            'curriculum_coverage_pct': coverage,
        },
        'clients': out,
    })


@org_bp.route('/cohorts/<int:cohort_id>/refresh', methods=['POST'])
@require_org()
def refresh_cohort(cohort_id):
    """Recompute this week's snapshot for every client in the cohort now
    (per-role insights cache: one role costs one computation)."""
    cohort = _own(Cohort, cohort_id)
    if cohort is None:
        return jsonify({'error': 'Cohort not found'}), 404
    cache, computed, skipped = {}, 0, 0
    for c in Client.query.filter_by(cohort_id=cohort.id).all():
        snap = compute_client_snapshot(c, cache)
        computed += 1 if snap else 0
        skipped += 0 if snap else 1
    db.session.commit()
    return jsonify({'computed': computed, 'skipped': skipped})


@org_bp.route('/cohorts/<int:cohort_id>/curriculum-fit', methods=['GET'])
@require_org()
def curriculum_fit(cohort_id):
    """Curriculum-vs-market: is this cohort's syllabus teaching what employers
    ask for? Reuses the skill-gap analyzer with the curriculum as the 'person'."""
    cohort = _own(Cohort, cohort_id)
    if cohort is None:
        return jsonify({'error': 'Cohort not found'}), 404
    if not cohort.target_role:
        return jsonify({'error': 'Cohort has no target role'}), 400
    curriculum = cohort.curriculum_skill_ids or []
    if not curriculum:
        return jsonify({'error': 'Cohort has no curriculum skills yet'}), 400

    gap = analyzer.analyze_gap(cohort.target_role, curriculum)
    if not gap.get('success'):
        return jsonify({'error': gap.get('error', 'analysis failed')}), 400

    covered = gap['skills_you_have'][:CURRICULUM_TOP_MARKET]
    missing = [s for s in gap['skills_missing'] if s['priority'] in ('high', 'medium')][:15]

    # Emerging: fast-growing market skills the curriculum lacks
    from app.routes.roles import get_all_skill_growth_bulk
    market_top = (gap['skills_you_have'] + gap['skills_missing'])
    market_top.sort(key=lambda s: s['demand'], reverse=True)
    top_ids = [s['skill_id'] for s in market_top[:CURRICULUM_TOP_MARKET]]
    growth = get_all_skill_growth_bulk(gap['role']['id'], top_ids)
    curriculum_set = set(curriculum)
    emerging = sorted(
        [{**s, 'growth_pct': growth.get(s['skill_id'])}
         for s in market_top[:CURRICULUM_TOP_MARKET]
         if s['skill_id'] not in curriculum_set
         and (growth.get(s['skill_id']) or 0) >= EMERGING_GROWTH_PCT],
        key=lambda s: s['growth_pct'], reverse=True)[:8]

    return jsonify({
        'role': gap['role'],
        'coverage_pct': gap['analysis']['match_score'],
        'jobs_analyzed': gap['analysis']['total_jobs_analyzed'],
        'covered': covered,
        'missing': missing,
        'emerging': emerging,
    })


# ── Clients ──────────────────────────────────────────────────────────────────

@org_bp.route('/clients', methods=['GET'])
@require_org()
def list_clients():
    q = Client.query.filter_by(org_id=request.org_id)
    cohort_id = request.args.get('cohort_id', type=int)
    if cohort_id:
        q = q.filter_by(cohort_id=cohort_id)
    return jsonify({'clients': [c.to_dict() for c in q.order_by(Client.display_name).all()]})


@org_bp.route('/clients', methods=['POST'])
@require_org()
def create_client():
    data = request.get_json() or {}
    name = (data.get('display_name') or '').strip()
    if not name:
        return jsonify({'error': 'display_name is required'}), 400
    cohort_id = data.get('cohort_id')
    if cohort_id is not None and _own(Cohort, cohort_id) is None:
        return jsonify({'error': 'Cohort not found'}), 404
    client = Client(org_id=request.org_id, cohort_id=cohort_id,
                    coach_user_id=request.user_id,
                    display_name=name, email=data.get('email'),
                    target_role=data.get('target_role'),
                    seniority=data.get('seniority'))
    db.session.add(client)
    db.session.flush()
    _replace_client_skills(client, data.get('skill_ids') or [])
    db.session.flush()
    # First snapshot immediately so the roster is never empty until Friday.
    compute_client_snapshot(client, {})
    db.session.commit()
    return jsonify({'client': client.to_dict()}), 201


@org_bp.route('/clients/<int:client_id>', methods=['PATCH'])
@require_org()
def update_client(client_id):
    client = _own(Client, client_id)
    if client is None:
        return jsonify({'error': 'Client not found'}), 404
    data = request.get_json() or {}
    for field in ('display_name', 'email', 'target_role', 'seniority'):
        if field in data:
            setattr(client, field, data[field])
    if 'cohort_id' in data:
        if data['cohort_id'] is not None and _own(Cohort, data['cohort_id']) is None:
            return jsonify({'error': 'Cohort not found'}), 404
        client.cohort_id = data['cohort_id']
    if 'skill_ids' in data:
        _replace_client_skills(client, data.get('skill_ids') or [])
    db.session.flush()
    compute_client_snapshot(client, {})
    db.session.commit()
    return jsonify({'client': client.to_dict()})


@org_bp.route('/clients/<int:client_id>', methods=['DELETE'])
@require_org()
def delete_client(client_id):
    client = _own(Client, client_id)
    if client is None:
        return jsonify({'error': 'Client not found'}), 404
    db.session.delete(client)  # cascades to skills + snapshots
    db.session.commit()
    return jsonify({'deleted': client_id})


@org_bp.route('/clients/<int:client_id>', methods=['GET'])
@require_org()
def client_detail(client_id):
    """Everything a coach needs for one client on a single screen: profile,
    skills, score history, top gaps, and live matched jobs."""
    client = _own(Client, client_id)
    if client is None:
        return jsonify({'error': 'Client not found'}), 404

    skills = (db.session.query(UserSkill, Skill)
              .join(Skill, Skill.id == UserSkill.skill_id)
              .filter(UserSkill.client_id == client.id).all())
    have = [{'skill_id': s.id, 'name': s.name, 'category': s.category}
            for us, s in skills if us.status == 'have']
    learning = [{'skill_id': s.id, 'name': s.name, 'category': s.category,
                 'since': us.status_changed_at.isoformat() if us.status_changed_at else None}
                for us, s in skills if us.status == 'learning']

    snaps = (UserWeekSnapshot.query.filter_by(client_id=client.id)
             .order_by(UserWeekSnapshot.week_start.desc())
             .limit(SNAPSHOT_HISTORY_WEEKS).all())
    history = [{'week_start': s.week_start.isoformat(),
                'position_score': s.position_score} for s in reversed(snaps)]
    current = snaps[0] if snaps else None
    drivers = []
    if current and current.details_json:
        try:
            drivers = (json.loads(current.details_json) or {}).get('drivers') or []
        except (ValueError, TypeError):
            pass

    matches, total_matches, new_matches = [], 0, 0
    gap = None
    if client.target_role:
        g = analyzer.analyze_gap(client.target_role, [s['skill_id'] for s in have])
        if g.get('success'):
            gap = {'match_score': g['analysis']['match_score'],
                   'top_missing': g['skills_missing'][:8]}
            role_id = g['role']['id']
            skill_id_set = {s['skill_id'] for s in have}
            rows, total_matches, new_matches = _query_matches(role_id, skill_id_set, 10)
            names = _skill_split([r['id'] for r in rows], skill_id_set)
            matches = [_serialize(r, names.get(r['id'], ([], []))) for r in rows]

    return jsonify({
        'client': client.to_dict(),
        'skills': {'have': have, 'learning': learning},
        'score': {
            'current': current.position_score if current else None,
            'history': history,
            'drivers': drivers,
        },
        'gap': gap,
        'matched_jobs': {'total': total_matches, 'new_this_week': new_matches,
                         'top': matches},
    })
