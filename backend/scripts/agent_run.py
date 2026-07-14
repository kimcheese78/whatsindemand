#!/usr/bin/env python3
"""Weekly maintenance scrape: re-scrapes every company in the DB and
emails a summary. No Claude calls — designed to run unattended on
Railway as a cron service.

Coverage expansion (Claude-proposed new companies) lives in
scripts/coverage_expand_agent.py and is run manually.

Run manually with: python scripts/agent_run.py
"""

import os
import sys
import traceback
from datetime import datetime


backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from app import create_app
from app.models import DiscoveryRun
from app.services.job_aggregator import JobAggregator
from app.services.email import send_email


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run_maintenance_scrape(aggregator):
    """Re-scrape every company already in DB. Returns stats dict."""
    log("=== Maintenance scrape start ===")
    start = datetime.utcnow()
    results = aggregator.scrape_from_db()
    duration = (datetime.utcnow() - start).total_seconds()
    log(f"=== Maintenance scrape done in {duration/60:.1f} min ===")
    return {
        "duration_min": round(duration / 60, 1),
        "companies_processed": results.get("total_companies", 0),
        "successful": results.get("successful", 0),
        "failed": results.get("failed", 0),
        "jobs_saved": results.get("total_jobs", 0),
    }


def run_discover_skills():
    """Run incremental skill discovery after scrape. Returns stats dict."""
    log("=== Skill discovery start ===")
    start = datetime.utcnow()
    try:
        from scripts.discover_new_skills import run as discover_run
        discover_run()
        duration = (datetime.utcnow() - start).total_seconds()
        log(f"=== Skill discovery done in {duration/60:.1f} min ===")
        run_rec = DiscoveryRun.query.filter_by(status='completed').order_by(
            DiscoveryRun.started_at.desc()
        ).first()
        return {
            "duration_min": round(duration / 60, 1),
            "jobs_processed": run_rec.jobs_processed if run_rec else 0,
            "candidates_upserted": run_rec.candidates_upserted if run_rec else 0,
            "error": None,
        }
    except Exception as e:
        log(f"ERROR: skill discovery failed: {e}")
        traceback.print_exc()
        return {"duration_min": 0, "jobs_processed": 0, "candidates_upserted": 0, "error": str(e)}



def run_extract(aggregator):
    """Extract skills for all dirty jobs (pure pattern matching, no Claude).
    Returns stats dict."""
    log("=== Skill extraction start ===")
    start = datetime.utcnow()
    try:
        from app.models import Job
        dirty = Job.query.filter_by(skills_dirty=True).filter(
            Job.description_text.isnot(None),
            Job.description_text != '',
        ).count()
        extracted = aggregator.extract_dirty_jobs() if dirty else 0
        duration = (datetime.utcnow() - start).total_seconds()
        log(f"=== Skill extraction done: {extracted:,} jobs in {duration/60:.1f} min ===")
        return {"duration_min": round(duration / 60, 1), "jobs_extracted": extracted, "error": None}
    except Exception as e:
        log(f"ERROR: skill extraction failed: {e}")
        traceback.print_exc()
        return {"duration_min": 0, "jobs_extracted": 0, "error": str(e)}


def run_backfill_new_skills():
    """Backfill job_skills across all historical jobs for skills promoted in
    the past 7 days (by the weekly review routine). Idempotent — inserts use
    ON CONFLICT DO NOTHING. Returns stats dict."""
    log("=== New-skill backfill start ===")
    start = datetime.utcnow()
    try:
        from app.models import db
        ids = [r[0] for r in db.session.execute(db.text(
            "SELECT id FROM skills WHERE is_verified=true"
            " AND created_at >= NOW() - INTERVAL '7 days'"
        )).fetchall()]
        if ids:
            from scripts.backfill_skills import run as backfill_run
            backfill_run(ids)
        from scripts.reextract_all_skills import update_job_counts
        update_job_counts()
        duration = (datetime.utcnow() - start).total_seconds()
        log(f"=== New-skill backfill done: {len(ids)} skills in {duration/60:.1f} min ===")
        return {"duration_min": round(duration / 60, 1), "skills_backfilled": len(ids), "error": None}
    except Exception as e:
        log(f"ERROR: new-skill backfill failed: {e}")
        traceback.print_exc()
        return {"duration_min": 0, "skills_backfilled": 0, "error": str(e)}


def format_email(scrape_stats, discover_stats, extract_stats, backfill_stats, total_duration_min):
    discover_section = f"""
Skill discovery:
  Jobs scanned:       {discover_stats['jobs_processed']:,}
  Candidates found:   {discover_stats['candidates_upserted']:,}
  Duration:           {discover_stats['duration_min']} min
""" if not discover_stats.get('error') else f"\nSkill discovery: FAILED — {discover_stats['error']}\n"

    extract_section = f"""
Skill extraction:
  Jobs extracted:     {extract_stats['jobs_extracted']:,}
  Duration:           {extract_stats['duration_min']} min
""" if not extract_stats.get('error') else f"\nSkill extraction: FAILED — {extract_stats['error']}\n"

    backfill_section = f"""
New-skill backfill:
  Skills backfilled:  {backfill_stats['skills_backfilled']}
  Duration:           {backfill_stats['duration_min']} min
""" if not backfill_stats.get('error') else f"\nNew-skill backfill: FAILED — {backfill_stats['error']}\n"

    text = f"""Weekly maintenance scrape complete.

Scrape:
  Companies processed: {scrape_stats['companies_processed']}
  Successful: {scrape_stats['successful']}
  Failed: {scrape_stats['failed']}
  Jobs saved: {scrape_stats['jobs_saved']:,}
  Duration: {scrape_stats['duration_min']} min
{discover_section}{extract_section}{backfill_section}
Total run time: {total_duration_min:.1f} min

Skill candidate review and role mapping run via the claude.ai weekly
routine (Fri 14:00 UTC) through the admin pipeline API.
"""
    html = "<pre style='font-family:monospace'>" + text.replace("<", "&lt;").replace(">", "&gt;") + "</pre>"
    return text, html


def main():
    start = datetime.utcnow()
    log(f"=== MAINTENANCE RUN STARTED: {start.isoformat()} ===")

    app = create_app()
    with app.app_context():
        aggregator = JobAggregator()
        try:
            scrape_stats = run_maintenance_scrape(aggregator)
        except Exception as e:
            log(f"FATAL: maintenance scrape crashed: {e}")
            traceback.print_exc()
            scrape_stats = {"duration_min": 0, "companies_processed": 0, "successful": 0,
                            "failed": -1, "jobs_saved": 0, "error": str(e)}

        discover_stats = run_discover_skills()
        # Extract BEFORE backfill: extract uses plain inserts (no conflict
        # handling), backfill is ON CONFLICT DO NOTHING — safe in this order.
        extract_stats = run_extract(aggregator)
        backfill_stats = run_backfill_new_skills()

    total_duration = (datetime.utcnow() - start).total_seconds() / 60

    alert_email = os.environ.get("ALERT_EMAIL")
    if alert_email:
        text, html = format_email(scrape_stats, discover_stats, extract_stats, backfill_stats, total_duration)
        candidates = discover_stats.get('candidates_upserted', 0)
        send_email(
            to=alert_email,
            subject=f"WhatsInDemand weekly scrape: {scrape_stats['jobs_saved']:,} jobs · {candidates:,} new candidates",
            html=html,
            text=text,
        )
        log(f"Email sent to {alert_email}")
    else:
        log("ALERT_EMAIL not set — no email report sent")

    log(f"=== MAINTENANCE RUN DONE in {total_duration:.1f} min ===")


if __name__ == "__main__":
    main()
