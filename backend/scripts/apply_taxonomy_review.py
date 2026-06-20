"""Apply taxonomy review decisions: deactivate duplicates + enrich aliases.

Decisions sourced from fuzzy-dedup analysis of 182 pairs in taxonomy_review_flagged.json.
Most pairs are false positives (programming-language cross-matches). Only clear
same-concept duplicates are deactivated here.

Run:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/apply_taxonomy_review.py
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/apply_taxonomy_review.py --apply
"""
import os
import sys
from datetime import datetime

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Skill

app = create_app()
APPLY = '--apply' in sys.argv

# Deactivate: plural/variant forms that are true duplicates of a kept canonical.
# Format: kept_id -> [deactivate_id, ...]
DEACTIVATE_KEEP_MAP = {
    239:  [2623],   # Vulnerability Assessment  ← Vulnerability Assessments
    231:  [2665],   # Cybersecurity             ← Cyber Security
    244:  [3182],   # System Design             ← Systems Design
    345:  [3440],   # Corporate Law             ← Corporate Laws
    177:  [645],    # Data Pipelines            ← Data Pipeline
    236:  [2968],   # Firewalls                 ← Firewall
    111:  [3623],   # Marketing Strategy        ← Marketing Strategies
    276:  [961],    # Business Strategy         ← Business Strategies
    123:  [3024],   # Shell Scripting           ← Shell Script
    163:  [2856],   # Infrastructure as Code    ← Infrastructure as Code (IaC)
    354:  [2299],   # Pharmaceutical            ← Pharmaceuticals
}

# Add aliases to canonical skills (merge the deactivated variant's name as alias)
ALIAS_ADDITIONS = {
    231: ['Cyber Security'],                          # Cybersecurity
    163: ['IaC', 'Infrastructure as Code (IaC)'],    # Infrastructure as Code
    236: ['Firewall'],                                # Firewalls
    239: ['Vulnerability Assessments'],               # Vulnerability Assessment
    177: ['Data Pipeline'],                           # Data Pipelines
}


def _add_aliases(skill, new_aliases):
    existing = {a.lower() for a in (skill.aliases or [])}
    added = []
    for a in new_aliases:
        if a.lower() not in existing:
            existing.add(a.lower())
            added.append(a)
    if added:
        skill.aliases = list(skill.aliases or []) + added
        skill.updated_at = datetime.utcnow()
    return added


def main():
    with app.app_context():
        now = datetime.utcnow()
        all_deactivate_ids = [did for dids in DEACTIVATE_KEEP_MAP.values() for did in dids]

        print('=== Deactivations (true duplicates) ===')
        for kept_id, deactivate_ids in DEACTIVATE_KEEP_MAP.items():
            kept = Skill.query.get(kept_id)
            if not kept:
                print(f'  MISSING kept id={kept_id}')
                continue
            for did in deactivate_ids:
                dup = Skill.query.get(did)
                if not dup:
                    print(f'  MISSING deactivate id={did}')
                    continue
                status = 'already unverified' if not dup.is_verified else 'will deactivate'
                print(f'  [{did}] {dup.name!r} → deactivate  (kept: [{kept_id}] {kept.name!r})  {status}')
                if APPLY and dup.is_verified:
                    dup.is_verified = False
                    dup.updated_at = now

        print(f'\n=== Alias enrichments ===')
        for skill_id, aliases in ALIAS_ADDITIONS.items():
            skill = Skill.query.get(skill_id)
            if not skill:
                print(f'  MISSING id={skill_id}')
                continue
            added = _add_aliases(skill, aliases) if APPLY else [
                a for a in aliases if a.lower() not in {x.lower() for x in (skill.aliases or [])}
            ]
            print(f'  [{skill_id}] {skill.name}: +{len(added)} aliases {added}')

        if APPLY:
            db.session.commit()
            print(f'\n✓ Committed. {len(all_deactivate_ids)} deactivated.')
        else:
            print(f'\nDry-run. {len(all_deactivate_ids)} to deactivate. Pass --apply to execute.')


if __name__ == '__main__':
    main()
