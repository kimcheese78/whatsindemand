#!/usr/bin/env python3
"""
Validate all company slugs and find correct ones.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrapers.greenhouse.scraper import GreenhouseScraper
from app.scrapers.lever.scraper import LeverScraper
from app.scrapers.ashby.scraper import AshbyScraper
from app.scrapers.companies import get_companies_by_ats


def validate_ats(ats: str, scraper):
    """Validate all companies for a specific ATS"""
    companies = get_companies_by_ats(ats)
    
    print(f"\n{'=' * 60}")
    print(f"VALIDATING {ats.upper()}: {len(companies)} companies")
    print(f"{'=' * 60}\n")
    
    valid = []
    invalid = []
    
    for company in companies:
        slug = company['slug']
        name = company['name']
        
        job_count = scraper.validate_company_slug(slug)
        
        if job_count is not None:
            print(f"✅ {name} ({slug}): {job_count} jobs")
            valid.append({'slug': slug, 'name': name, 'jobs': job_count})
        else:
            print(f"❌ {name} ({slug}): INVALID")
            invalid.append({'slug': slug, 'name': name})
    
    print(f"\n{'-' * 40}")
    print(f"Valid: {len(valid)}/{len(companies)}")
    print(f"Invalid: {len(invalid)}/{len(companies)}")
    
    if invalid:
        print(f"\nInvalid slugs to fix:")
        for c in invalid:
            print(f"  - {c['name']}: {c['slug']}")
    
    return valid, invalid


def main():
    # Only validate Lever since that's what failed
    print("Validating Lever companies...")
    lever_valid, lever_invalid = validate_ats('lever', LeverScraper(verbose=False))
    
    # Optionally validate others
    # print("\nValidating Ashby companies...")
    # ashby_valid, ashby_invalid = validate_ats('ashby', AshbyScraper(verbose=False))


if __name__ == '__main__':
    main()