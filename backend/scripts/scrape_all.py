#!/usr/bin/env python3
"""
Bulk scrape all companies from all ATS platforms.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from datetime import datetime

from app import create_app
from app.services.job_aggregator import JobAggregator
from app.scrapers.companies import get_company_count_by_ats, get_all_ats_types


def main():
    parser = argparse.ArgumentParser(description='Scrape jobs from ATS platforms')
    parser.add_argument('--ats', type=str, choices=['greenhouse', 'lever', 'ashby', 'all'],
                        default='all', help='Which ATS to scrape')
    parser.add_argument('--industry', type=str, default=None, help='Filter by industry')
    parser.add_argument('--dry-run', action='store_true', help='Test without saving to database')
    
    args = parser.parse_args()
    
    print(f"\n{'=' * 60}")
    print(f"Job Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")
    
    # Show stats
    print("\nCompany Registry:")
    for ats, count in sorted(get_company_count_by_ats().items()):
        print(f"  {ats}: {count} companies")
    
    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No data will be saved\n")
        
        # Just test the scrapers
        from app.scrapers.greenhouse.scraper import GreenhouseScraper
        from app.scrapers.lever.scraper import LeverScraper
        from app.scrapers.ashby.scraper import AshbyScraper
        from app.scrapers.companies import get_companies_by_ats
        
        ats_list = [args.ats] if args.ats != 'all' else get_all_ats_types()
        scrapers = {
            'greenhouse': GreenhouseScraper(),
            'lever': LeverScraper(),
            'ashby': AshbyScraper(),
        }
        
        for ats in ats_list:
            companies = get_companies_by_ats(ats)[:2]  # Test first 2 per ATS
            print(f"\nTesting {ats} with {len(companies)} companies...")
            
            for company in companies:
                print(f"  {company['name']}...")
                jobs = scrapers[ats].get_company_jobs(company['slug'])
                print(f"    → Found {len(jobs)} jobs")
        
        print("\n✅ Dry run complete!")
        return
    
    # Real run - need Flask app context for database
    app = create_app()
    
    with app.app_context():
        aggregator = JobAggregator()
        
        ats_filter = None if args.ats == 'all' else args.ats
        
        results = aggregator.scrape_from_registry(
            ats_type=ats_filter,
            industry=args.industry
        )
        
        # Final summary
        print(f"\n{'=' * 60}")
        print("FINAL SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Companies scraped: {results['successful']}/{results['total_companies']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Total jobs saved: {results['total_jobs']}")
        
        if results['errors']:
            print(f"\n  Errors:")
            for err in results['errors'][:10]:  # Show first 10 errors
                print(f"    - {err['company']}: {err['error']}")
        
        print(f"\nFinished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()