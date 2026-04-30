"""Autonomously expand company coverage into underrepresented industries.

For each candidate (name, preferred_slug, preferred_ats, industry):
  1. Skip if already in DB.
  2. Probe preferred_ats with the slug; if hit, scrape.
  3. If preferred fails, probe the other 3 ATSes with the same slug.
  4. If all fail, try 1-2 slug variants (strip/hyphenate).

Logs everything with timestamps. Robust to per-company failure.

Run: python scripts/expand_coverage.py                # processes full list
     python scripts/expand_coverage.py --batch <file> # candidates from file
"""
import sys
import time
import traceback
from datetime import datetime

from app import create_app
from app.models import db, Company
from app.services.job_aggregator import JobAggregator
from app.scrapers.greenhouse.scraper import GreenhouseScraper
from app.scrapers.lever.scraper import LeverScraper
from app.scrapers.ashby.scraper import AshbyScraper
import requests

ATS_ORDER = ['greenhouse', 'lever', 'ashby', 'workable']


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def slug_variants(slug):
    s = slug.lower().strip()
    variants = [s]
    if '-' in s:
        variants.append(s.replace('-', ''))
    if s.endswith('ai'):
        variants.append(s + '-ai')
    if s.endswith('inc'):
        variants.append(s[:-3])
    return list(dict.fromkeys(variants))


def probe_ats(ats, slug, probes):
    """Return job count (>=0) if valid, None otherwise. Uses cached results."""
    key = (ats, slug)
    if key in probes:
        return probes[key]
    try:
        if ats == 'greenhouse':
            r = requests.get(
                f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs',
                timeout=8, headers={'User-Agent': 'WhatsInDemand/1.0'}
            )
            n = len(r.json().get('jobs', [])) if r.status_code == 200 else None
        elif ats == 'lever':
            r = requests.get(
                f'https://api.lever.co/v0/postings/{slug}?mode=json',
                timeout=8, headers={'User-Agent': 'WhatsInDemand/1.0'}
            )
            data = r.json() if r.status_code == 200 else None
            n = len(data) if isinstance(data, list) else None
        elif ats == 'ashby':
            r = requests.get(
                f'https://api.ashbyhq.com/posting-api/job-board/{slug}',
                timeout=8, headers={'User-Agent': 'WhatsInDemand/1.0'}
            )
            n = len(r.json().get('jobs', [])) if r.status_code == 200 else None
        elif ats == 'workable':
            r = requests.post(
                f'https://apply.workable.com/api/v3/accounts/{slug}/jobs',
                json={'query': '', 'location': [], 'department': [], 'worktype': [], 'remote': []},
                headers={'Content-Type': 'application/json', 'User-Agent': 'WhatsInDemand/1.0'},
                timeout=8,
            )
            if r.status_code == 200:
                data = r.json()
                n = data.get('total', len(data.get('results', [])))
            else:
                n = None
        else:
            n = None
    except Exception:
        n = None
    probes[key] = n
    time.sleep(0.4)  # polite pacing across probes
    return n


def find_ats_for_company(name, preferred_slug, preferred_ats, probes):
    """Return (ats, slug, job_count) or None."""
    # Order: preferred first, then others
    atses = [preferred_ats] + [a for a in ATS_ORDER if a != preferred_ats]
    for slug in slug_variants(preferred_slug):
        for ats in atses:
            n = probe_ats(ats, slug, probes)
            if n is not None and n > 0:
                return ats, slug, n
    return None


def main():
    app = create_app()
    aggregator = None

    import os, importlib
    module = os.environ.get('CANDIDATES_MODULE', 'scripts.expansion_candidates')
    mod = importlib.import_module(module)
    CANDIDATES = mod.CANDIDATES

    log(f'Loaded {len(CANDIDATES)} candidates from {module}')

    with app.app_context():
        aggregator = JobAggregator()

        existing = {
            (c.ats_type, c.greenhouse_slug)
            for c in Company.query.with_entities(Company.ats_type, Company.greenhouse_slug).all()
        }
        existing_names = {c.name.lower() for c in Company.query.with_entities(Company.name).all()}
        log(f'DB has {len(existing)} existing (ats, slug) pairs')

        probes = {}
        stats = {
            'attempted': 0, 'already_in_db': 0, 'probe_miss': 0,
            'scraped_ok': 0, 'scrape_err': 0, 'total_jobs': 0,
        }

        for i, cand in enumerate(CANDIDATES):
            name = cand['name']
            pref_slug = cand.get('slug') or name.lower().replace(' ', '')
            pref_ats = cand.get('ats', 'greenhouse')
            industry = cand.get('industry', 'Other')
            stats['attempted'] += 1

            if name.lower() in existing_names:
                log(f'[{i+1}/{len(CANDIDATES)}] SKIP (name exists) {name}')
                stats['already_in_db'] += 1
                continue

            hit = find_ats_for_company(name, pref_slug, pref_ats, probes)
            if not hit:
                log(f'[{i+1}/{len(CANDIDATES)}] MISS {name} (tried {pref_ats}/{pref_slug})')
                stats['probe_miss'] += 1
                continue

            ats, slug, n_jobs = hit
            if (ats, slug) in existing:
                log(f'[{i+1}/{len(CANDIDATES)}] SKIP (slug exists) {name} -> {ats}/{slug}')
                stats['already_in_db'] += 1
                continue

            log(f'[{i+1}/{len(CANDIDATES)}] HIT  {name} -> {ats}/{slug} ({n_jobs} jobs) [{industry}]')
            try:
                saved = aggregator.scrape_company_jobs(
                    company_name=name, company_slug=slug,
                    ats_type=ats, industry=industry,
                )
                log(f'  saved {saved} jobs for {name}')
                stats['scraped_ok'] += 1
                stats['total_jobs'] += saved or 0
                existing.add((ats, slug))
                existing_names.add(name.lower())
            except Exception as e:
                log(f'  ERROR scraping {name}: {e}')
                stats['scrape_err'] += 1
                traceback.print_exc()
                db.session.rollback()

            if (i + 1) % 25 == 0:
                log(f'--- progress: {stats} ---')

        log(f'=== DONE === {stats}')


if __name__ == '__main__':
    main()
