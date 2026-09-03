# backend/app/routes/market.py
"""Market-wide insight endpoint — reads precomputed market_insight_snapshots (cheap,
no live computation). Powers the insight-first landing. Written by
scripts/compute_market_insights.py weekly."""
import json
from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app.models import db, MarketInsightSnapshot

market_bp = Blueprint('market', __name__, url_prefix='/api/market')

# Snapshots are recomputed by the weekly cron (agent_run.py). If the newest one
# is older than this, the recompute step has silently stopped and the landing is
# drifting from the live role dashboards — surface it so the UI can hide trends.
STALE_AFTER_DAYS = 10

# Short client cache so an out-of-band recompute (e.g. a correction) reaches
# recent visitors within the hour, not a day. Data only changes weekly, so the
# 7-day stale-while-revalidate keeps this effectively free on the origin.
INSIGHTS_CACHE_HEADER = 'public, max-age=3600, stale-while-revalidate=604800'


@market_bp.route('/insights', methods=['GET'])
def market_insights():
    """Latest week's insights for a scope (default 'overall'), grouped by kind, plus the
    list of available scopes (sectors/industries) for the filter UI."""
    scope = request.args.get('scope', 'overall')
    latest_week = db.session.query(func.max(MarketInsightSnapshot.week_start)).scalar()
    if not latest_week:
        return jsonify({'week': None, 'scope': scope, 'insights': {}, 'scopes': []})

    rows = (MarketInsightSnapshot.query
            .filter_by(week_start=latest_week, scope=scope)
            .order_by(MarketInsightSnapshot.kind, MarketInsightSnapshot.rank).all())
    insights = defaultdict(list)
    for r in rows:
        insights[r.kind].append(json.loads(r.payload) if r.payload else {})

    scopes = sorted(s for (s,) in db.session.query(MarketInsightSnapshot.scope)
                    .filter_by(week_start=latest_week).distinct().all())

    age_days = (date.today() - latest_week).days
    stale = age_days > STALE_AFTER_DAYS

    resp = jsonify({'week': latest_week.isoformat(), 'scope': scope,
                    'insights': dict(insights), 'scopes': scopes,
                    'stale': stale, 'age_days': age_days})
    resp.headers['Cache-Control'] = INSIGHTS_CACHE_HEADER
    return resp
