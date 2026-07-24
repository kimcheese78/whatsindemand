#!/usr/bin/env python3
"""Compute each user's weekly Position Score snapshot.

For every verified user with a target role and at least one saved skill, pull
the same insights payload the dashboard uses (cached per role, like
send_weekly_digest.py) and compute an explainable 0-100 score:

    position_score = round(55 * skill_coverage
                           + 25 * momentum_component
                           + 20 * (1 - ai_exposure_norm))

- skill_coverage: demand-weighted coverage of the role's top-30 skills
- momentum_component: postings_growth_pct clamped to [-20,+20], normalized to [0,1]
- ai_exposure_norm: role's AI-skill share (current_pct) / 100, clamped to [0,1]

Upserts one row per user per ISO week into user_week_snapshots. The component
values and the top-3 gap-skill drivers are stored in details_json so the UI can
explain every movement.

Usage:
    python scripts/compute_week_snapshots.py            # dry-run (compute + print)
    python scripts/compute_week_snapshots.py --apply    # commit snapshots
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

from app import create_app
from app.models import db, User, UserProfile, UserSkill, UserWeekSnapshot
from app.routes.matched_jobs import _query_matches


def iso_week_start(d=None):
    """Monday of the ISO week containing d (default today)."""
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def compute_components(insights, user_skill_ids):
    """Pure score computation from an insights payload + the user's skill ids."""
    skills = insights.get('skills') or []
    top30 = sorted(skills, key=lambda s: s.get('demand') or 0, reverse=True)[:30]
    total_w = sum((s.get('demand') or 0) for s in top30) or 1.0
    have_w = sum((s.get('demand') or 0) for s in top30
                 if s.get('skill_id') in user_skill_ids)
    coverage = have_w / total_w  # 0..1

    mt = insights.get('market_trend') or {}
    growth = mt.get('postings_growth_pct')
    growth_clamped = max(-20.0, min(20.0, growth)) if growth is not None else 0.0
    momentum = (growth_clamped + 20.0) / 40.0  # 0..1

    ai = insights.get('ai_exposure') or {}
    ai_pct = ai.get('current_pct')
    ai_norm = max(0.0, min(1.0, (ai_pct or 0.0) / 100.0))

    score = round(55 * coverage + 25 * momentum + 20 * (1 - ai_norm))
    score = max(0, min(100, int(score)))
    return {
        'score': score,
        'coverage': coverage,
        'momentum': momentum,
        'ai_norm': ai_norm,
        'raw_growth': growth,
        'ai_pct': ai_pct,
        'top30': top30,
    }


def compute_drivers(top30, user_skill_ids):
    """Top 3 explainers: high-demand, rising skills the user is missing."""
    gaps = [s for s in top30
            if s.get('skill_id') not in user_skill_ids and s.get('category') != 'soft']
    gaps.sort(key=lambda s: ((s.get('growth_pct') or 0), (s.get('demand') or 0)),
              reverse=True)
    drivers = []
    for s in gaps[:3]:
        growth = s.get('growth_pct')
        if growth is not None and growth >= 1:
            text = f"{s['name']} demand grew {round(growth)}% this week and you don't have it"
        else:
            text = f"{s['name']} is in {round(s.get('demand') or 0)}% of postings and you don't have it"
        drivers.append({
            'skill': s['name'], 'growth_pct': growth,
            'demand': s.get('demand'), 'have': False, 'text': text,
        })
    return drivers


def run(apply=False):
    """Compute + upsert snapshots for the current ISO week. Returns a stats dict.
    Safe to call inside an existing app context (uses a fresh test client for
    insights)."""
    app = create_app()
    stats = {'users': 0, 'computed': 0, 'inserted': 0, 'updated': 0,
             'skipped': 0, 'errors': 0}
    week_start = iso_week_start()

    with app.app_context():
        client = app.test_client()
        insights_cache = {}

        recipients = db.session.query(User, UserProfile).join(
            UserProfile, UserProfile.user_id == User.id
        ).filter(
            User.email_verified == True,
            UserProfile.target_role.isnot(None),
            UserProfile.target_role != '',
        ).all()
        stats['users'] = len(recipients)
        print(f"Week {week_start}: {len(recipients)} candidate users (apply={apply})", flush=True)

        for user, profile in recipients:
            role_title = profile.target_role
            skill_ids = {us.skill_id for us in
                         UserSkill.query.filter_by(user_id=user.id).all()}
            if not skill_ids:
                stats['skipped'] += 1
                continue

            if role_title not in insights_cache:
                resp = client.post('/api/roles/insights', json={'role': role_title})
                ok = resp.status_code == 200 and (resp.get_json() or {}).get('success')
                insights_cache[role_title] = resp.get_json() if ok else None
                if not ok:
                    print(f"  ! insights failed for '{role_title}'", flush=True)

            insights = insights_cache[role_title]
            if not insights or not insights.get('total_jobs_analyzed'):
                stats['skipped'] += 1
                continue

            try:
                comp = compute_components(insights, skill_ids)
                drivers = compute_drivers(comp['top30'], skill_ids)
                role_id = (insights.get('role') or {}).get('id')
                _, matched_total, matched_new = (
                    _query_matches(role_id, skill_ids, 1) if role_id else ([], 0, 0)
                )
                details = json.dumps({
                    'components': {
                        'skill_coverage': round(comp['coverage'], 4),
                        'momentum': round(comp['momentum'], 4),
                        'ai_exposure_norm': round(comp['ai_norm'], 4),
                    },
                    'weights': {'skill_coverage': 55, 'momentum': 25, 'ai_low_exposure': 20},
                    'drivers': drivers,
                })

                snap = UserWeekSnapshot.query.filter_by(
                    user_id=user.id, week_start=week_start).first()
                is_new = snap is None
                if is_new:
                    snap = UserWeekSnapshot(user_id=user.id, week_start=week_start)
                    db.session.add(snap)
                snap.position_score = comp['score']
                snap.match_pct = round(comp['coverage'], 4)
                snap.market_momentum = comp['raw_growth']
                snap.ai_exposure = comp['ai_pct']
                snap.matched_jobs_count = matched_total
                snap.new_matched_jobs = matched_new
                snap.details_json = details

                stats['computed'] += 1
                stats['inserted' if is_new else 'updated'] += 1
                top_driver = drivers[0]['text'] if drivers else '—'
                print(f"  {user.email}: score={comp['score']} "
                      f"cover={comp['coverage']:.2f} match_jobs={matched_total} "
                      f"({'new' if is_new else 'upd'})  driver: {top_driver}", flush=True)
            except Exception as e:
                stats['errors'] += 1
                print(f"  ✗ {user.email}: {e}", flush=True)

        if apply:
            db.session.commit()
            print("Committed.", flush=True)
        else:
            db.session.rollback()
            print("Dry-run — nothing written. Pass --apply to commit.", flush=True)

    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Commit snapshots')
    args = parser.parse_args()
    result = run(apply=args.apply)
    print(f"\nDone: {result}")
