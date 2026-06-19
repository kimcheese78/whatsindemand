"""Re-extract skills for all active jobs.

Batch-optimised: eliminates per-job SELECT/DELETE/INSERT roundtrips.

Run:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/reextract_all_skills.py
    ... --limit 2000        # smoke test
    ... --batch-size 1000   # tune batch size (default 1000)
"""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Job, JobSkill, Skill
from app.services.skill_extractor import SkillExtractor

MAX_SKILLS_PER_JOB = 10


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def update_job_counts():
    """Rebuild Skill.total_job_count from job_skills for all verified skills."""
    log('Updating Skill.total_job_count ...')
    db.session.execute(db.text("""
        UPDATE skills s
        SET total_job_count = sub.cnt
        FROM (
            SELECT js.skill_id, COUNT(DISTINCT js.job_id) AS cnt
            FROM job_skills js
            JOIN jobs j ON js.job_id = j.id
            WHERE j.is_active = true
              AND j.role_id IS NOT NULL
            GROUP BY js.skill_id
        ) sub
        WHERE s.id = sub.skill_id
          AND s.is_verified = true
    """))
    # Zero out skills that lost all their jobs
    db.session.execute(db.text("""
        UPDATE skills
        SET total_job_count = 0
        WHERE is_verified = true
          AND id NOT IN (
              SELECT DISTINCT js.skill_id FROM job_skills js
              JOIN jobs j ON js.job_id = j.id
              WHERE j.is_active = true AND j.role_id IS NOT NULL
          )
          AND (total_job_count IS NULL OR total_job_count > 0)
    """))
    db.session.commit()
    log('total_job_count updated.')


def run(limit: int | None, batch_size: int):
    app = create_app()
    with app.app_context():
        extractor = SkillExtractor()
        extractor._load_skills()
        log(f'SkillExtractor ready — {len(extractor.skill_cache)} verified skills, '
            f'{sum(len(v) for v in extractor._skill_patterns.values())} patterns')

        # All jobs with descriptions — active and inactive.
        # Full consistency across all historical trend windows.
        id_rows = db.session.query(Job.id).filter(
            Job.description_text.isnot(None),
            Job.description_text != '',
        ).all()
        all_ids = [r[0] for r in id_rows]
        if limit:
            all_ids = all_ids[:limit]
        total = len(all_ids)
        log(f'{total:,} jobs to process in batches of {batch_size} (all jobs)')

        t0 = time.time()
        stats = {'done': 0, 'errors': 0, 'skills_saved': 0}
        now = datetime.utcnow()

        for batch_start in range(0, total, batch_size):
            batch_ids = all_ids[batch_start:batch_start + batch_size]

            try:
                # 1. Bulk-fetch description_text for this batch (one query)
                rows = db.session.query(Job.id, Job.description_text).filter(
                    Job.id.in_(batch_ids)
                ).all()

                # 2. Bulk-delete existing job_skills for this batch (one query)
                db.session.execute(
                    db.text('DELETE FROM job_skills WHERE job_id = ANY(:ids)'),
                    {'ids': batch_ids}
                )

                # 3. Extract and accumulate new records
                new_records = []
                for job_id, description_text in rows:
                    if not description_text:
                        continue
                    try:
                        results = extractor.extract_skills(description_text)
                        for r in results[:MAX_SKILLS_PER_JOB]:
                            new_records.append({
                                'job_id': job_id,
                                'skill_id': r['skill_id'],
                                'is_required': r['confidence'] >= 80,
                                'created_at': now,
                            })
                        stats['done'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        log(f'  ERROR job {job_id}: {e}')

                # 4. Bulk-insert all new records (one query)
                if new_records:
                    db.session.bulk_insert_mappings(JobSkill, new_records)
                    stats['skills_saved'] += len(new_records)

                db.session.commit()

            except Exception as e:
                db.session.rollback()
                stats['errors'] += len(batch_ids)
                log(f'  BATCH ERROR at {batch_start}: {e}')
                continue

            # Progress
            elapsed = time.time() - t0
            rate = stats['done'] / max(elapsed, 1)
            eta = (total - stats['done']) / rate if rate > 0 else 0
            log(f'{stats["done"]:,}/{total:,} ({100*stats["done"]/total:.1f}%)  '
                f'{rate:.0f} jobs/s  ETA {eta/60:.0f}min  '
                f'skills={stats["skills_saved"]:,}  errs={stats["errors"]}')

        elapsed = time.time() - t0
        log(f'=== Extraction done: {stats["done"]:,} jobs, '
            f'{stats["skills_saved"]:,} job_skills, '
            f'{stats["errors"]} errors in {elapsed/60:.1f}min ===')

        # 5. Rebuild denormalised job counts
        update_job_counts()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--batch-size', type=int, default=1000)
    args = p.parse_args()
    run(args.limit, args.batch_size)


if __name__ == '__main__':
    main()
