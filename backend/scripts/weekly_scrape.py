#!/usr/bin/env python3
"""
Weekly job scraping script.
Run via cron: 0 17 * * 6 /Users/henry_c/WhatsInDemand/backend/venv/bin/python /Users/henry_c/WhatsInDemand/backend/scripts/weekly_scrape.py >> /Users/henry_c/WhatsInDemand/backend/logs/weekly_scrape.log 2>&1
# 17:00 UTC Saturday = 02:00 KST Sunday
"""

import sys
import os
from datetime import datetime

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Load .env explicitly so cron picks up DATABASE_URL etc.
from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

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
            # ── Step 1: Scrape — saves jobs with skills_dirty=True, no extraction yet ──
            results = aggregator.scrape_from_db()

            print(f"\n── Step 1 complete ──")
            print(f"Companies processed: {results['total_companies']}")
            print(f"Successful: {results['successful']}  Failed: {results['failed']}")
            print(f"Total jobs saved: {results['total_jobs']}")
            if results['errors']:
                print(f"Errors ({len(results['errors'])}):")
                for err in results['errors'][:10]:
                    print(f"  - {err['company']}: {err['error']}")

            # ── Step 2: Discovery — incremental, may promote new skills into taxonomy ──
            print(f"\n── Step 2: Incremental skill discovery ──")
            try:
                from scripts.discover_new_skills import run as run_discovery
                run_discovery(since_dt=start_time)
            except Exception as e:
                print(f"  ⚠ Discovery failed (non-fatal): {e}")

            # ── Step 3: Skill extraction — fresh SkillExtractor includes promoted skills ──
            print(f"\n── Step 3: Skill extraction ──")
            extracted = aggregator.extract_dirty_jobs()
            print(f"  Extracted skills for {extracted} jobs")

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            print(f"\n{'=' * 60}")
            print(f"WEEKLY SCRAPE COMPLETED: {end_time.isoformat()}")
            print(f"Duration: {duration:.1f}s ({duration / 60:.1f} min)")
            print(f"{'=' * 60}\n")

            return results

        except Exception as e:
            print(f"\n❌ SCRAPE FAILED: {e}")
            raise


if __name__ == '__main__':
    run_weekly_scrape()