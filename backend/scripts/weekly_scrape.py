#!/usr/bin/env python3
"""
Weekly job scraping script — Steps 1 + 2 only (scrape + skill discovery).

Run via cron: 0 17 * * 6 /Users/henry_c/WhatsInDemand/backend/venv/bin/python /Users/henry_c/WhatsInDemand/backend/scripts/weekly_scrape.py >> /Users/henry_c/WhatsInDemand/backend/logs/weekly_scrape.log 2>&1
# 17:00 UTC Saturday = 02:00 KST Sunday

After scrape completes, manually review skill candidates and unmatched role titles,
then run scripts/extract_skills.py to execute Step 3 with the updated taxonomy.
"""

import sys
import os
import argparse
from datetime import datetime

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Load .env explicitly so cron picks up DATABASE_URL etc.
from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

from app import create_app
from app.services.job_aggregator import JobAggregator


def run_weekly_scrape(resume_after: datetime = None, skip_extraction: bool = False, max_workers: int = 5):
    """Run the weekly scraping job (Steps 1 + 2, optionally Step 3)."""

    start_time = datetime.utcnow()
    print(f"\n{'=' * 60}")
    print(f"WEEKLY SCRAPE STARTED: {start_time.isoformat()}")
    if resume_after:
        print(f"RESUMING: skipping companies scraped after {resume_after.isoformat()}")
    if skip_extraction:
        print(f"NOTE: skill extraction (Step 3) skipped — run extract_skills.py after review")
    print(f"{'=' * 60}\n")

    app = create_app()

    with app.app_context():
        aggregator = JobAggregator()

        try:
            # ── Step 1: Scrape — saves jobs with skills_dirty=True, no extraction yet ──
            results = aggregator.scrape_from_db(resume_after=resume_after, max_workers=max_workers)

            print(f"\n── Step 1 complete ──")
            print(f"Companies processed: {results['total_companies']}")
            print(f"Successful: {results['successful']}  Failed: {results['failed']}")
            print(f"Total jobs saved: {results['total_jobs']}")
            if results['errors']:
                print(f"Errors ({len(results['errors'])}):")
                for err in results['errors'][:10]:
                    print(f"  - {err['company']}: {err['error']}")

            # ── Step 2: Discovery — finds new skill candidates, logs qualifying ones ──
            print(f"\n── Step 2: Incremental skill discovery ──")
            try:
                from scripts.discover_new_skills import run as run_discovery
                run_discovery()
            except Exception as e:
                print(f"  ⚠ Discovery failed (non-fatal): {e}")

            if skip_extraction:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                print(f"\n{'=' * 60}")
                print(f"SCRAPE + DISCOVERY COMPLETE: {end_time.isoformat()}")
                print(f"Duration: {duration:.1f}s ({duration / 60:.1f} min)")
                print(f"\nNext: review skill candidates + unmatched role titles,")
                print(f"then run: python scripts/extract_skills.py")
                print(f"{'=' * 60}\n")
                return results

            # ── Step 3: Skill extraction — run manually via extract_skills.py after review ──
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-after', type=str, default=None,
        help='Skip companies scraped at or after this UTC timestamp (e.g. 2026-05-14T23:17:23)')
    parser.add_argument('--with-extraction', action='store_true', default=False,
        help='Also run extraction (Step 3) immediately after discovery — skip this to wait until after skill review')
    parser.add_argument('--workers', type=int, default=5,
        help='Number of parallel scrape workers (default: 5)')
    args = parser.parse_args()

    resume_after = None
    if args.resume_after:
        resume_after = datetime.fromisoformat(args.resume_after)

    run_weekly_scrape(resume_after=resume_after, skip_extraction=not args.with_extraction, max_workers=args.workers)