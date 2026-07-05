#!/usr/bin/env python3
"""
Targeted job_skills backfill for newly promoted skills.

Single pass over all jobs — all new skills matched per job, bulk inserted per
batch. Much faster than the old per-skill approach (N scans → 1 scan).

Usage:
    python scripts/backfill_skills.py --skill-ids 4710 4711 4712
    python scripts/backfill_skills.py --min-id 4710   # all skills with id >= 4710
"""
import sys
import os
import re
import time
import argparse
from datetime import datetime

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

from app import create_app
from app.models import db, Skill, JobSkill
from app.services.skill_extractor import extract_requirements_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError

app = create_app()

BATCH_SIZE = 500
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds


def fetch_batch(last_id):
    """Fetch one batch, retrying on connection errors."""
    for attempt in range(MAX_RETRIES):
        try:
            with app.app_context():
                rows = db.session.execute(db.text("""
                    SELECT id, description_text FROM jobs
                    WHERE id > :last_id
                      AND description_text IS NOT NULL
                      AND description_text != ''
                    ORDER BY id
                    LIMIT :limit
                """), {'last_id': last_id, 'limit': BATCH_SIZE}).fetchall()
                return list(rows)
        except OperationalError as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  Connection error on fetch (attempt {attempt+1}), retrying in {RETRY_DELAY}s...", flush=True)
                time.sleep(RETRY_DELAY)
            else:
                raise


def insert_batch(new_rows):
    """Insert one batch, retrying on connection errors."""
    for attempt in range(MAX_RETRIES):
        try:
            with app.app_context():
                if new_rows:
                    db.session.execute(
                        pg_insert(JobSkill.__table__).on_conflict_do_nothing(
                            index_elements=['job_id', 'skill_id']
                        ),
                        new_rows,
                    )
                db.session.commit()
            return
        except OperationalError as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  Connection error on insert (attempt {attempt+1}), retrying in {RETRY_DELAY}s...", flush=True)
                time.sleep(RETRY_DELAY)
            else:
                raise


def run(skill_ids: list, start_id: int = 0) -> None:
    # Load skill patterns in one short-lived connection
    with app.app_context():
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        if not skills:
            print("No skills found for given IDs.")
            return
        skill_patterns = []
        for skill in skills:
            terms = [skill.name] + (skill.aliases or [])
            patterns = [
                re.compile(r'\b' + re.escape(t) + r'\b', re.IGNORECASE)
                for t in terms if t and len(t.strip()) >= 2
            ]
            if patterns:
                skill_patterns.append((skill.id, patterns))

    print(f"Backfilling {len(skill_patterns)} skill(s) in a single pass over all jobs...")
    start = datetime.utcnow()

    last_id = start_id
    total_inserted = 0
    jobs_processed = 0

    while True:
        # Each batch uses its own short-lived connection — avoids Railway proxy timeouts
        rows = fetch_batch(last_id)
        if not rows:
            break

        new_rows = []
        for job_id, description_text in rows:
            search_text, _ = extract_requirements_text(description_text)
            for skill_id, patterns in skill_patterns:
                if any(p.search(search_text) for p in patterns):
                    new_rows.append({
                        'job_id': job_id,
                        'skill_id': skill_id,
                        'is_required': True,
                    })

        insert_batch(new_rows)

        last_id = rows[-1][0]
        jobs_processed += len(rows)
        total_inserted += len(new_rows)
        elapsed = (datetime.utcnow() - start).total_seconds()
        rate = jobs_processed / elapsed if elapsed > 0 else 0
        print(f"  {jobs_processed:,} jobs  ({rate:.0f}/s)  {total_inserted:,} inserted  last_id={last_id}", flush=True)

    duration = (datetime.utcnow() - start).total_seconds()
    print(f"\nDone. {total_inserted:,} job_skills rows inserted for {len(skill_patterns)} skills in {duration:.0f}s.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-ids', nargs='+', type=int, default=[],
        help='Specific skill IDs to backfill')
    parser.add_argument('--min-id', type=int, default=None,
        help='Backfill all skills with id >= this value (e.g. first newly promoted ID)')
    parser.add_argument('--start-job-id', type=int, default=0,
        help='Resume scanning jobs with id > this value (checkpoint from a prior interrupted run)')
    args = parser.parse_args()

    ids = list(args.skill_ids)
    if args.min_id is not None:
        with app.app_context():
            ids += [s.id for s in Skill.query.filter(Skill.id >= args.min_id).all()]

    if not ids:
        print("Provide --skill-ids or --min-id. Exiting.")
        sys.exit(1)

    run(list(set(ids)), start_id=args.start_job_id)
