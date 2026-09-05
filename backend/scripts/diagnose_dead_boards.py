"""Re-probe scrape_enabled companies that currently have 0 active jobs, and
categorize why: DEAD (board 404/errors), EMPTY (board valid but 0 openings),
or ALIVE (board actually returns jobs — a transient scrape miss).

Read-only. Run:
    DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/diagnose_dead_boards.py
"""
import requests
from collections import Counter

from app import create_app
from app.models import db, Company, Job
from sqlalchemy import func

UA = {'User-Agent': 'WhatsInDemand/1.0'}


def probe(ats, slug):
    """Return (status, job_count). status in {alive, empty, dead}."""
    try:
        if ats == 'greenhouse':
            r = requests.get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs', timeout=10, headers=UA)
            if r.status_code != 200:
                return 'dead', 0
            n = len(r.json().get('jobs', []))
        elif ats == 'lever':
            r = requests.get(f'https://api.lever.co/v0/postings/{slug}?mode=json', timeout=10, headers=UA)
            if r.status_code != 200:
                return 'dead', 0
            n = len(r.json())
        elif ats == 'ashby':
            # Must be GET (matches AshbyScraper). POST returns 401 for valid boards
            # and would falsely flag every Ashby company as dead.
            r = requests.get('https://api.ashbyhq.com/posting-api/job-board/' + slug, timeout=10, headers=UA)
            if r.status_code != 200:
                return 'dead', 0
            n = len(r.json().get('jobs', []))
        elif ats == 'workable':
            r = requests.get(f'https://apply.workable.com/api/v1/widget/accounts/{slug}?details=false', timeout=10, headers=UA)
            if r.status_code != 200:
                return 'dead', 0
            n = len(r.json().get('jobs', []))
        else:
            return 'unknown', 0
        return ('empty' if n == 0 else 'alive'), n
    except Exception:
        return 'dead', 0


app = create_app()
with app.app_context():
    active_ids = db.session.query(func.distinct(Job.company_id)).filter(Job.is_active == True).subquery()
    targets = db.session.query(Company).filter(
        Company.scrape_enabled == True,
        Company.id.notin_(db.session.query(active_ids)),
    ).all()

    print(f"Re-probing {len(targets)} companies with 0 active jobs...\n")
    tally = Counter()
    dead, alive = [], []
    for c in targets:
        status, n = probe(c.ats_type, c.greenhouse_slug)
        tally[status] += 1
        if status == 'dead':
            dead.append(c)
        elif status == 'alive':
            alive.append((c, n))
        print(f"  {status:>7} ({n:>3})  {c.name}  [{c.ats_type}/{c.greenhouse_slug}]")

    print("\n=== summary ===")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    print(f"\nDEAD (candidates to fix slug or remove): {len(dead)}")
    print(f"ALIVE (transient scrape miss, will self-heal next run): {len(alive)}")
