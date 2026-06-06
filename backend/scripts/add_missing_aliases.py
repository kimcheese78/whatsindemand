"""Add missing aliases to skills that have well-known variants/abbreviations.

Dry-run by default; pass --apply to commit.

Usage:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/add_missing_aliases.py
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/add_missing_aliases.py --apply
"""
import os, sys
from datetime import datetime

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Skill

app = create_app()
APPLY = '--apply' in sys.argv

# id → [aliases to add]
ADDITIONS = {
    # Technical
    272:  ['a11y', 'WCAG', 'web accessibility'],                    # Accessibility
    3102: ['dev ops'],                                               # DevOps
    348:  ['General Data Protection Regulation',
           'data protection regulation'],                            # GDPR
    1098: ['CSAT', 'customer sat'],                                  # Customer Satisfaction
    807:  ['stats', 'statistical analysis'],                         # Statistics
    3134: ['debug'],                                                  # Debugging
    651:  ['data engineer'],                                          # Data Engineering
    3023: ['scripting languages', 'shell script'],                   # Scripting
    407:  ['resiliency'],                                            # Resilience

    # Domain
    350:  ['health care'],                                           # Healthcare
    1097: ['customer support', 'client service', 'client support'],  # Customer Service
    362:  ['financial technology'],                                   # FinTech
    332:  ['taxation'],                                              # Tax
    333:  ['auditing'],                                              # Audit
    2182: ['behavioral health', 'mental wellness'],                  # Mental Health
    1339: ['program manager'],                                       # Program Management
    369:  ['public sector'],                                         # Government
    335:  ['risk mitigation'],                                       # Risk Management
    313:  ['continuous improvement', 'process optimization'],        # Process Improvement
    1383: ['mentoring', 'coaching'],                                  # Mentorship
}


def main():
    with app.app_context():
        now = datetime.utcnow()
        total_added = 0

        for skill_id, new_aliases in ADDITIONS.items():
            skill = Skill.query.get(skill_id)
            if not skill:
                print(f'  MISSING id={skill_id}')
                continue

            existing = {a.lower() for a in (skill.aliases or [])}
            to_add = [a for a in new_aliases if a.lower() not in existing]

            if not to_add:
                print(f'  [{skill_id:5d}] {skill.name} — already has all aliases, skipping')
                continue

            print(f'  [{skill_id:5d}] {skill.name} (jobs={skill.total_job_count or 0:,})')
            for a in to_add:
                print(f'    + "{a}"')

            if APPLY:
                skill.aliases = list(skill.aliases or []) + to_add
                skill.updated_at = now
                total_added += len(to_add)

        if APPLY:
            db.session.commit()
            print(f'\n✓ Committed. Added {total_added} aliases.')
        else:
            total = sum(
                len([a for a in aliases if a.lower() not in
                     {x.lower() for x in (Skill.query.get(sid).aliases or [])}])
                for sid, aliases in ADDITIONS.items()
                if Skill.query.get(sid)
            )
            print(f'\nDry-run. {total} aliases would be added. Pass --apply to execute.')


if __name__ == '__main__':
    main()
