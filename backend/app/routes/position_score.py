# backend/app/routes/position_score.py
"""Position Score — the user's single weekly-tracked standing vs. their target
role. Reads snapshots written by scripts/compute_week_snapshots.py; never
recomputes here."""
import json
from flask import Blueprint, jsonify, request
from app.models import UserWeekSnapshot
from app.utils.jwt_handler import token_required

position_score_bp = Blueprint('position_score', __name__, url_prefix='/api/position-score')

HISTORY_WEEKS = 12


def _drivers(snap):
    try:
        return (json.loads(snap.details_json) or {}).get('drivers', []) if snap.details_json else []
    except (ValueError, TypeError):
        return []


def _serialize(snap, with_drivers=False):
    if snap is None:
        return None
    out = {
        'week_start': snap.week_start.isoformat(),
        'position_score': snap.position_score,
        'match_pct': snap.match_pct,
        'market_momentum': snap.market_momentum,
        'ai_exposure': snap.ai_exposure,
        'matched_jobs_count': snap.matched_jobs_count,
        'new_matched_jobs': snap.new_matched_jobs,
    }
    if with_drivers:
        out['drivers'] = _drivers(snap)
    return out


@position_score_bp.route('', methods=['GET'])
@token_required
def get_position_score():
    """Current snapshot + previous + delta + drivers, plus up to 12 weeks of
    history for the sparkline. `tracking` is false until the user has 2+ weeks,
    so the UI can suppress a misleading delta on week one."""
    snaps = (UserWeekSnapshot.query
             .filter_by(user_id=request.user_id)
             .order_by(UserWeekSnapshot.week_start.desc())
             .limit(HISTORY_WEEKS)
             .all())

    if not snaps:
        return jsonify({'current': None, 'previous': None, 'delta': None,
                        'history': [], 'tracking': False})

    current, previous = snaps[0], (snaps[1] if len(snaps) > 1 else None)
    delta = None
    if previous is not None and current.position_score is not None \
            and previous.position_score is not None:
        delta = current.position_score - previous.position_score

    history = [{'week_start': s.week_start.isoformat(),
                'position_score': s.position_score}
               for s in reversed(snaps)]  # oldest → newest for the sparkline

    return jsonify({
        'current': _serialize(current, with_drivers=True),
        'previous': _serialize(previous),
        'delta': delta,
        'history': history,
        'tracking': len(snaps) >= 2,
    })
