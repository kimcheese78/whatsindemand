#!/usr/bin/env python3
"""
Step 3: Extract skills for all dirty jobs.

Run this manually on review day, after:
  1. Promoting new skill candidates (scripts/promote_curated_skills.py)
  2. Adding new roles and backfilling unmatched titles

Usage:
    python scripts/extract_skills.py
"""
import sys
import os
from datetime import datetime

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

from app import create_app
from app.services.job_aggregator import JobAggregator

app = create_app()

with app.app_context():
    from app.models import db, Job

    dirty_count = Job.query.filter_by(skills_dirty=True).filter(
        Job.description_text.isnot(None),
        Job.description_text != '',
    ).count()

    if dirty_count == 0:
        print("No dirty jobs — nothing to extract.")
        sys.exit(0)

    print(f"\n{'=' * 60}")
    print(f"SKILL EXTRACTION STARTED: {datetime.utcnow().isoformat()}")
    print(f"Jobs to process: {dirty_count:,}")
    print(f"{'=' * 60}\n")

    aggregator = JobAggregator()
    start = datetime.utcnow()
    extracted = aggregator.extract_dirty_jobs()
    duration = (datetime.utcnow() - start).total_seconds()

    print(f"\n{'=' * 60}")
    print(f"EXTRACTION COMPLETE: {datetime.utcnow().isoformat()}")
    print(f"Extracted skills for {extracted:,} jobs in {duration:.1f}s ({duration/60:.1f} min)")
    print(f"{'=' * 60}\n")
