"""
Rebuild Company.logo_url using Google Favicon API.

Dry-run by default; pass --apply to write changes.

Usage:
    PYTHONPATH=. venv/bin/python scripts/update_logo_urls.py [--apply]
"""
import os
import sys
import re

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

from app import create_app
from app.models import Company, db

APPLY = '--apply' in sys.argv
FAVICON_BASE = 'https://www.google.com/s2/favicons?domain={domain}&sz=64'


def extract_domain(website: str) -> str | None:
    """Strip scheme, www., and trailing path to get bare domain."""
    if not website:
        return None
    website = website.strip()
    # Remove scheme
    website = re.sub(r'^https?://', '', website, flags=re.IGNORECASE)
    # Remove path
    domain = website.split('/')[0]
    # Remove port
    domain = domain.split(':')[0]
    return domain.lower() if domain else None


def main():
    app = create_app()
    with app.app_context():
        companies = Company.query.filter(Company.website != None, Company.website != '').all()
        no_website = Company.query.filter(
            (Company.website == None) | (Company.website == '')
        ).count()

        updated = 0
        skipped = 0
        samples = []

        for company in companies:
            domain = extract_domain(company.website)
            if not domain:
                skipped += 1
                continue
            new_url = FAVICON_BASE.format(domain=domain)
            if len(samples) < 10:
                samples.append((company.name, domain, new_url))
            company.logo_url = new_url
            updated += 1

        print(f"Companies with website:    {len(companies)}")
        print(f"Companies without website: {no_website}")
        print(f"Would update:              {updated}")
        print(f"Skipped (bad domain):      {skipped}")
        print()
        print("Sample URLs:")
        for name, domain, url in samples:
            print(f"  {name:<35} {url}")

        if APPLY:
            db.session.commit()
            print(f"\nApplied — {updated} logo_url values updated.")
        else:
            db.session.rollback()
            print("\nDry-run. Pass --apply to write changes.")


if __name__ == '__main__':
    main()
