"""Map roles to BLS occupation codes (SOC) and attach projection data.

Reads Role rows, matches each indexable role to a SOC code from a curated seed,
looks up the projection in app/data/bls_projections.json, and writes a review
CSV flagging (a) roles it could not map and (b) roles whose BLS projection
declines while the role is still actively hiring (a likely bad map — eyeball it).

Run (production):
  DATABASE_URL='postgresql://...' PYTHONPATH=. python3 scripts/map_roles_to_bls.py
  DATABASE_URL='postgresql://...' PYTHONPATH=. python3 scripts/map_roles_to_bls.py --apply

Dry-run by default; --apply writes bls_soc_code/pct/period onto Role rows.
"""
import csv
import os
import sys

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

from app import create_app
from app.models import db, Role
from app.services.ai_verdict import bls_for, FLAT_FLOOR

APPLY = '--apply' in sys.argv
MIN_JOBS = 30

# Curated title -> SOC seed. Only confident mappings belong here; anything not
# listed is REPORTED for a human to add, never guessed. Extend as you review.
SEED = {
    "software engineer": "15-1252",     # Software Developers
    "data scientist": "15-2051",        # Data Scientists
    "accountant": "13-2011",            # Accountants and Auditors
    "financial analyst": "13-2051",     # Financial and Investment Analysts
    "graphic designer": "27-1024",      # Graphic Designers
    "marketing manager": "11-2021",     # Marketing Managers
    "mechanical engineer": "17-2141",   # Mechanical Engineers
    "electrical engineer": "17-2071",   # Electrical Engineers
    "registered nurse": "29-1141",      # Registered Nurses
    "project manager": "13-1082",       # Project Management Specialists
    # TODO(reviewer): extend with the roles reported as unmatched below.
}


def _match_soc(title_lower):
    if title_lower in SEED:
        return SEED[title_lower]
    # simple contains fallback (e.g. "senior software engineer")
    for key, soc in SEED.items():
        if key in title_lower:
            return soc
    return None


def main():
    app = create_app()
    with app.app_context():
        roles = Role.query.filter(Role.total_active_jobs >= MIN_JOBS).all()

        rows, updated = [], 0
        for r in roles:
            title_lower = r.normalized_title.lower()
            soc = _match_soc(title_lower)
            rec = bls_for(soc) if soc else None
            pct = rec['pct'] if rec else None
            period = rec['period'] if rec else None

            if soc is None:
                flag = 'UNMATCHED (add a SOC to SEED)'
            elif rec is None:
                flag = 'SOC needs BLS numbers (add to bls_projections.json)'
            elif pct is not None and pct < FLAT_FLOOR:
                flag = 'DIVERGENCE: BLS declines but role is hiring — verify the SOC'
            else:
                flag = 'ok'

            rows.append({
                'role': r.normalized_title, 'active_jobs': r.total_active_jobs,
                'soc': soc or '', 'bls_pct': '' if pct is None else pct,
                'period': period or '', 'flag': flag,
            })

            if APPLY and soc is not None and rec is not None and flag == 'ok':
                r.bls_soc_code = soc
                r.bls_projection_pct = pct
                r.bls_projection_period = period
                updated += 1

        out_dir = os.path.join(os.path.dirname(__file__), '_out')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'bls_mapping_review.csv')
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['role', 'active_jobs', 'soc',
                                              'bls_pct', 'period', 'flag'])
            w.writeheader()
            w.writerows(rows)

        n_ok = sum(1 for x in rows if x['flag'] == 'ok')
        n_unmatched = sum(1 for x in rows if x['flag'].startswith('UNMATCHED'))
        n_needsnum = sum(1 for x in rows if x['flag'].startswith('SOC needs'))
        n_diverge = sum(1 for x in rows if x['flag'].startswith('DIVERGENCE'))
        print(f"roles considered: {len(rows)}")
        print(f"  ok mapped:        {n_ok}")
        print(f"  unmatched:        {n_unmatched}")
        print(f"  SOC needs BLS #:  {n_needsnum}")
        print(f"  divergence flags: {n_diverge}")
        print(f"review file: {out_path}")

        if APPLY:
            db.session.commit()
            print(f"APPLIED: wrote BLS data onto {updated} roles.")
        else:
            print("dry-run — no writes. Re-run with --apply once the review looks right.")


if __name__ == '__main__':
    main()
