"""Re-extract skills for all active jobs with descriptions.

Wipes existing JobSkill rows per job, runs SkillExtractor, saves top-10.
Matches JobAggregator._extract_skills behavior.

Run: PYTHONPATH=. python3 scripts/reextract_all_skills.py
     PYTHONPATH=. python3 scripts/reextract_all_skills.py --limit 100  # test
"""
import sys
import time
import traceback
from datetime import datetime

from app import create_app
from app.models import db, Job, JobSkill
from app.services.skill_extractor import SkillExtractor

LIMIT = None
for i, a in enumerate(sys.argv):
    if a == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])

LOG_EVERY = 200
COMMIT_EVERY = 100


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def main():
    app = create_app()
    with app.app_context():
        extractor = SkillExtractor()
        extractor._load_skills()
        log(f'SkillExtractor ready ({len(extractor.skill_cache)} verified skills)')

        id_q = db.session.query(Job.id).filter(Job.is_active == True, Job.description_text.isnot(None))
        if LIMIT:
            id_q = id_q.limit(LIMIT)
        job_ids = [row[0] for row in id_q.all()]
        total = len(job_ids)
        log(f'Re-extracting over {total} jobs')

        t0 = time.time()
        stats = {'done': 0, 'errors': 0, 'skills_saved': 0}

        for job_id in job_ids:
            job = Job.query.get(job_id)
            if job is None or not job.description_text:
                continue
            try:
                JobSkill.query.filter_by(job_id=job.id).delete(synchronize_session=False)

                results = extractor.extract_skills(job.description_text)
                for r in results[:10]:
                    db.session.add(JobSkill(
                        job_id=job.id,
                        skill_id=r['skill_id'],
                        is_required=r['confidence'] >= 80,
                    ))
                    stats['skills_saved'] += 1

                stats['done'] += 1

                if stats['done'] % COMMIT_EVERY == 0:
                    db.session.commit()

                if stats['done'] % LOG_EVERY == 0:
                    elapsed = time.time() - t0
                    rate = stats['done'] / elapsed
                    eta = (total - stats['done']) / rate if rate > 0 else 0
                    log(f'{stats["done"]}/{total} ({100*stats["done"]/total:.1f}%) '
                        f'rate={rate:.1f}/s eta={eta/60:.0f}min skills={stats["skills_saved"]} errs={stats["errors"]}')

            except Exception as e:
                stats['errors'] += 1
                log(f'ERROR job {job.id}: {e}')
                traceback.print_exc()
                db.session.rollback()

        db.session.commit()
        elapsed = time.time() - t0
        log(f'=== DONE === {stats} in {elapsed/60:.1f}min')


if __name__ == '__main__':
    main()
