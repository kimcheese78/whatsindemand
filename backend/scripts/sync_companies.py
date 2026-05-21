#!/usr/bin/env python3
"""
Sync companies.py registry → DB companies table.

Inserts any company from the registry that isn't already in the DB.
Safe to run multiple times (upsert by ats_type + greenhouse_slug).

Usage:
    python scripts/sync_companies.py
    python scripts/sync_companies.py --dry-run
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db, Company
from app.scrapers.companies import COMPANIES


def sync(dry_run: bool = False):
    existing = {
        (c.ats_type, c.greenhouse_slug): c
        for c in Company.query.all()
    }
    print(f"Existing companies in DB: {len(existing)}")
    print(f"Companies in registry:    {len(COMPANIES)}")

    to_add = []
    for c in COMPANIES:
        ats = c['ats']
        slug = c.get('slug')
        key = (ats, slug)
        if key not in existing:
            to_add.append(Company(
                name=c['name'],
                ats_type=ats,
                greenhouse_slug=slug if ats == 'greenhouse' else None,
                industry=c.get('industry') if c.get('industry') != 'TBD' else None,
                scrape_enabled=True,
            ))

    print(f"New companies to insert:  {len(to_add)}")

    # Reset sequence to avoid conflicts when existing rows were inserted with explicit IDs
    db.session.execute(db.text(
        "SELECT setval('companies_id_seq', (SELECT COALESCE(MAX(id), 0) FROM companies))"
    ))
    db.session.commit()

    if dry_run:
        print("(dry-run — no changes written)")
        for c in to_add[:20]:
            print(f"  {c.name} [{c.ats_type}] {c.greenhouse_slug}")
        if len(to_add) > 20:
            print(f"  ... and {len(to_add) - 20} more")
        return

    batch_size = 500
    for i in range(0, len(to_add), batch_size):
        batch = to_add[i:i + batch_size]
        db.session.add_all(batch)
        db.session.commit()
        print(f"  Inserted {min(i + batch_size, len(to_add))}/{len(to_add)}...")

    print(f"✅ Done. Added {len(to_add)} companies.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        sync(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
