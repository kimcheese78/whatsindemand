#!/usr/bin/env python3
"""Coverage expansion: ask Claude for new big-name companies, probe each
against the four supported ATSes, scrape the hits, email a summary.

Run manually (requires ANTHROPIC_API_KEY with credits):
    python scripts/coverage_expand_agent.py
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
from app.models import db, Company
from app.services.job_aggregator import JobAggregator
from app.services.coverage_agent import propose_candidates
from app.services.email import send_email
from scripts.expand_coverage import find_ats_for_company


# ---- Tunables ----
CANDIDATES_PER_RUN = 50
MIN_PROBE_HIT_RATE = 0.25  # if below, don't insert (Claude likely hallucinating)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run_coverage_expansion(aggregator):
    log("=== Coverage expansion start ===")

    existing_names = [c.name for c in Company.query.with_entities(Company.name).all()]
    industry_rows = db.session.query(
        Company.industry, db.func.count(Company.id)
    ).group_by(Company.industry).all()
    industry_counts = {ind or "Unknown": cnt for ind, cnt in industry_rows}

    log(f"DB has {len(existing_names)} companies across {len(industry_counts)} industries")

    candidates = propose_candidates(
        existing_names=existing_names,
        industry_counts=industry_counts,
        n=CANDIDATES_PER_RUN,
    )
    log(f"Claude proposed {len(candidates)} candidates")

    if not candidates:
        return {"proposed": 0, "probed_hits": 0, "added": 0, "errors": 0, "added_companies": []}

    probes = {}
    hits = []
    for c in candidates:
        hit = find_ats_for_company(c["name"], c["slug"], c["ats"], probes)
        if hit:
            ats, slug, n_jobs = hit
            hits.append({**c, "ats": ats, "slug": slug, "job_count": n_jobs})
            log(f"  HIT  {c['name']} -> {ats}/{slug} ({n_jobs} jobs)")
        else:
            log(f"  MISS {c['name']} (tried {c['ats']}/{c['slug']})")

    hit_rate = len(hits) / len(candidates) if candidates else 0
    log(f"Hit rate: {len(hits)}/{len(candidates)} = {hit_rate:.0%}")

    if hit_rate < MIN_PROBE_HIT_RATE:
        log(f"Hit rate below {MIN_PROBE_HIT_RATE:.0%} — skipping insertion this run")
        return {
            "proposed": len(candidates),
            "probed_hits": len(hits),
            "added": 0,
            "errors": 0,
            "added_companies": [],
            "skipped_low_hit_rate": True,
        }

    added = []
    errors = 0
    for h in hits:
        try:
            saved = aggregator.scrape_company_jobs(
                company_name=h["name"],
                company_slug=h["slug"],
                ats_type=h["ats"],
                industry=h["industry"],
            )
            log(f"  saved {saved} jobs for {h['name']}")
            added.append({**h, "jobs_saved": saved or 0})
        except Exception as e:
            log(f"  ERROR scraping {h['name']}: {e}")
            errors += 1
            traceback.print_exc()
            db.session.rollback()

    log(f"=== Coverage expansion done: +{len(added)} companies, {errors} errors ===")
    return {
        "proposed": len(candidates),
        "probed_hits": len(hits),
        "added": len(added),
        "errors": errors,
        "added_companies": added,
    }


def format_email(stats, total_duration_min):
    added_lines = "\n".join(
        f"- {c['name']} ({c['ats']}/{c['slug']}, {c.get('jobs_saved', 0)} jobs) — {c.get('reason', '')}"
        for c in stats["added_companies"]
    ) or "(none)"

    text = f"""Coverage expansion complete.

  Candidates proposed by Claude: {stats['proposed']}
  Probe hits: {stats['probed_hits']}
  Added to DB: {stats['added']}
  Errors: {stats['errors']}
  {"  (skipped insertion — hit rate too low)" if stats.get('skipped_low_hit_rate') else ''}

Newly added companies:
{added_lines}

Total run time: {total_duration_min:.1f} min
"""
    html = "<pre style='font-family:monospace'>" + text.replace("<", "&lt;").replace(">", "&gt;") + "</pre>"
    return text, html


def main():
    start = datetime.utcnow()
    log(f"=== COVERAGE EXPANSION STARTED: {start.isoformat()} ===")

    app = create_app()
    with app.app_context():
        aggregator = JobAggregator()
        try:
            stats = run_coverage_expansion(aggregator)
        except Exception as e:
            log(f"FATAL: coverage expansion crashed: {e}")
            traceback.print_exc()
            stats = {"proposed": 0, "probed_hits": 0, "added": 0,
                     "errors": -1, "added_companies": [], "error": str(e)}

    total_duration = (datetime.utcnow() - start).total_seconds() / 60

    alert_email = os.environ.get("ALERT_EMAIL")
    if alert_email:
        text, html = format_email(stats, total_duration)
        send_email(
            to=alert_email,
            subject=f"WhatsInDemand coverage expansion: +{stats['added']} cos",
            html=html,
            text=text,
        )
        log(f"Email sent to {alert_email}")

    log(f"=== COVERAGE EXPANSION DONE in {total_duration:.1f} min ===")


if __name__ == "__main__":
    main()
