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


def format_email(scrape_stats, total_duration_min):
    text = f"""Weekly maintenance scrape complete.

  Companies processed: {scrape_stats['companies_processed']}
  Successful: {scrape_stats['successful']}
  Failed: {scrape_stats['failed']}
  Jobs saved: {scrape_stats['jobs_saved']:,}
  Duration: {scrape_stats['duration_min']} min

Total run time: {total_duration_min:.1f} min
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

    total_duration = (datetime.utcnow() - start).total_seconds() / 60

    alert_email = os.environ.get("ALERT_EMAIL")
    if alert_email:
        text, html = format_email(scrape_stats, total_duration)
        send_email(
            to=alert_email,
            subject=f"WhatsInDemand weekly scrape: {scrape_stats['jobs_saved']:,} jobs",
            html=html,
            text=text,
        )
        log(f"Email sent to {alert_email}")
    else:
        log("ALERT_EMAIL not set — no email report sent")

    log(f"=== MAINTENANCE RUN DONE in {total_duration:.1f} min ===")


if __name__ == "__main__":
    main()
