#!/usr/bin/env python3
"""
Weekly job scraping script.
Run via cron: 0 2 * * 0 /path/to/venv/bin/python /path/to/backend/scripts/weekly_scrape.py

This script:
1. Scrapes all companies in the registry
2. Marks jobs as inactive if they've been removed from ATS
3. Logs results
"""

import sys
import os
from datetime import datetime

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import create_app
from app.services.job_aggregator import JobAggregator


def run_weekly_scrape():
    """Run the weekly scraping job."""
    
    start_time = datetime.utcnow()
    print(f"\n{'=' * 60}")
    print(f"WEEKLY SCRAPE STARTED: {start_time.isoformat()}")
    print(f"{'=' * 60}\n")
    
    app = create_app()
    
    with app.app_context():
        aggregator = JobAggregator()
        
        try:
            results = aggregator.scrape_from_registry()
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n{'=' * 60}")
            print(f"WEEKLY SCRAPE COMPLETED: {end_time.isoformat()}")
            print(f"{'=' * 60}")
            print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            print(f"Companies processed: {results['total_companies']}")
            print(f"Successful: {results['successful']}")
            print(f"Failed: {results['failed']}")
            print(f"Total jobs saved: {results['total_jobs']}")
            
            if results['errors']:
                print(f"\nErrors ({len(results['errors'])}):")
                for err in results['errors'][:10]:  # Show first 10 errors
                    print(f"  - {err['company']}: {err['error']}")
            
            print(f"{'=' * 60}\n")
            
            return results
            
        except Exception as e:
            print(f"\n❌ SCRAPE FAILED: {e}")
            raise


if __name__ == '__main__':
    run_weekly_scrape()