#!/usr/bin/env python3
"""
Weekly "what changed in your role" digest.

For every verified user with a target role and weekly_digest enabled, compute
the week's market deltas from the same insights pipeline the dashboard uses,
and send one short email. Insights are cached per role, so 50 users tracking
"Software Engineer" cost one computation, not fifty.

Usage:
    python scripts/send_weekly_digest.py            # dry-run: print, send nothing
    python scripts/send_weekly_digest.py --apply    # actually send
    python scripts/send_weekly_digest.py --apply --only-email someone@x.com
"""
import argparse
import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

from app import create_app
from app.models import db, User, UserProfile, UserSkill
from app.services.email import send_email
from app.services import email_templates

app = create_app()

# Public backend URL for unsubscribe links (must be reachable from an email client)
API_PUBLIC_URL = os.environ.get(
    'API_PUBLIC_URL', 'https://whatsindemand-production.up.railway.app'
).rstrip('/')


def build_digest_data(insights: dict, user_skill_ids: set) -> dict:
    """Reduce a full insights payload to the handful of numbers worth emailing."""
    d = {}

    mt = insights.get('market_trend') or {}
    if mt.get('postings_growth_pct') is not None:
        d['growth_pct'] = round(mt['postings_growth_pct'])

    ai = insights.get('ai_exposure') or {}
    if ai.get('current_pct') is not None:
        d['ai_pct'] = ai['current_pct']
        d['ai_delta'] = ai.get('delta_pct_points')

    skills = insights.get('skills') or []

    # Meaningful movers only: real growth, real presence, and not generic
    # soft skills — "Communication is rising" is never the week's news.
    rising = [
        s for s in skills
        if s.get('growth_pct') is not None and s['growth_pct'] >= 3
        and (s.get('demand') or 0) >= 3
        and s.get('category') != 'soft'
    ]
    rising.sort(key=lambda s: s['growth_pct'], reverse=True)
    if rising:
        d['rising_skills'] = [
            {'name': s['name'], 'growth_pct': s['growth_pct'], 'demand': s.get('demand')}
            for s in rising[:3]
        ]

    companies = insights.get('top_companies') or []
    surging = [c for c in companies if (c.get('growth_pct') or 0) >= 50]
    surging.sort(key=lambda c: c['growth_pct'], reverse=True)
    if surging:
        d['surging_company'] = {'name': surging[0]['name'], 'growth_pct': surging[0]['growth_pct']}

    d['total_jobs'] = insights.get('total_jobs_analyzed')

    # Personal gap: highest-demand skill the user doesn't have
    if user_skill_ids:
        by_demand = sorted(skills, key=lambda s: s.get('demand') or 0, reverse=True)
        for s in by_demand[:15]:
            if s.get('skill_id') not in user_skill_ids:
                d['gap_skill'] = s['name']
                break

    return d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Actually send emails')
    parser.add_argument('--only-email', help='Restrict to a single recipient (testing)')
    args = parser.parse_args()

    client = app.test_client()
    insights_cache = {}

    with app.app_context():
        from app.routes.auth import make_digest_unsubscribe_token

        recipients = db.session.query(User, UserProfile).join(
            UserProfile, UserProfile.user_id == User.id
        ).filter(
            User.email_verified == True,
            UserProfile.weekly_digest == True,
            UserProfile.target_role.isnot(None),
            UserProfile.target_role != '',
        ).all()

        if args.only_email:
            recipients = [(u, p) for u, p in recipients if u.email == args.only_email]

        print(f"Recipients: {len(recipients)}  (apply={args.apply})")

        sent = failed = skipped = 0
        for user, profile in recipients:
            role_title = profile.target_role

            if role_title not in insights_cache:
                resp = client.post('/api/roles/insights', json={'role': role_title})
                if resp.status_code != 200 or not (resp.get_json() or {}).get('success'):
                    print(f"  ! insights failed for role '{role_title}' — skipping its users")
                    insights_cache[role_title] = None
                else:
                    insights_cache[role_title] = resp.get_json()

            insights = insights_cache[role_title]
            if not insights or not insights.get('total_jobs_analyzed'):
                skipped += 1
                continue

            skill_ids = {
                us.skill_id for us in UserSkill.query.filter_by(user_id=user.id).all()
            }
            data = build_digest_data(insights, skill_ids)
            if data.get('growth_pct') is None and not data.get('rising_skills'):
                # Nothing meaningful to say — don't send a hollow email
                skipped += 1
                continue

            token = make_digest_unsubscribe_token(user.id)
            unsub_url = f"{API_PUBLIC_URL}/api/auth/digest-unsubscribe?token={token}"
            subject, html, text = email_templates.weekly_digest(user, role_title, data, unsub_url)

            if args.apply:
                ok = send_email(user.email, subject, html, text)
                sent += 1 if ok else 0
                failed += 0 if ok else 1
                print(f"  {'✓' if ok else '✗'} {user.email}  [{role_title}] {subject}")
            else:
                print(f"  DRY {user.email}  [{role_title}]")
                print(f"      subject: {subject}")
                for line in text.splitlines():
                    print(f"      {line}")

        print(f"\nDone. sent={sent} failed={failed} skipped={skipped} dry_run={not args.apply}")


if __name__ == '__main__':
    main()
