"""Sample test of skill extraction after Lightcast ingest.

Picks N random recent jobs, runs extract_skills, and reports:
- timing (load + per-job)
- total unique skills matched across sample
- breakdown by category (showing Lightcast expansion)
- skills-per-job histogram
"""
import random
import time
from collections import Counter

from app import create_app
from app.models import db, Job, Skill
from app.services.skill_extractor import SkillExtractor

N_SAMPLE = 30
LIGHTCAST_CATEGORIES = None  # set at runtime


def main():
    app = create_app()
    with app.app_context():
        # Identify "Lightcast" skill IDs by category (anything not in old taxonomy)
        old_cats = {'technical', 'soft', 'domain'}
        lightcast_skill_ids = {
            s.id for s in Skill.query.filter(~Skill.category.in_(old_cats)).all()
        }
        print(f'Skill table: {Skill.query.count()} total, {len(lightcast_skill_ids)} Lightcast-category')

        # Sample recent jobs with real descriptions
        jobs = Job.query.filter(
            Job.is_active == True,
            Job.description_text.isnot(None),
        ).order_by(db.func.random()).limit(N_SAMPLE).all()
        print(f'Sampled {len(jobs)} active jobs')

        t0 = time.time()
        extractor = SkillExtractor()
        # warm cache
        extractor._load_skills()
        t_load = time.time() - t0
        print(f'_load_skills: {t_load:.2f}s  ({len(extractor.skill_cache)} patterns compiled)')

        per_job_counts = []
        per_job_times = []
        category_counter = Counter()
        lightcast_hits = Counter()  # skill_name -> job count
        curated_hits = Counter()

        for job in jobs:
            t1 = time.time()
            results = extractor.extract_skills(job.description_text, company_name=None)
            per_job_times.append(time.time() - t1)
            per_job_counts.append(len(results))

            for r in results:
                category_counter[r['category']] += 1
                if r['skill_id'] in lightcast_skill_ids:
                    lightcast_hits[r['name']] += 1
                else:
                    curated_hits[r['name']] += 1

        print(f'\n=== Timing ===')
        print(f'_load_skills: {t_load:.2f}s (one-time)')
        print(f'Per-job extract: avg {sum(per_job_times)/len(per_job_times)*1000:.0f}ms, '
              f'min {min(per_job_times)*1000:.0f}ms, max {max(per_job_times)*1000:.0f}ms')

        print(f'\n=== Skills per job (histogram) ===')
        bins = Counter()
        for n in per_job_counts:
            bucket = (n // 5) * 5
            bins[bucket] += 1
        for b in sorted(bins):
            print(f'  {b:3d}-{b+4}: {"#" * bins[b]} ({bins[b]})')

        print(f'\n=== Top Lightcast-category hits (new) ===')
        for name, cnt in lightcast_hits.most_common(25):
            print(f'  {cnt:3d}x  {name}')

        print(f'\n=== Top curated hits (old) ===')
        for name, cnt in curated_hits.most_common(10):
            print(f'  {cnt:3d}x  {name}')

        print(f'\n=== Category breakdown of all matches ===')
        for cat, cnt in category_counter.most_common():
            print(f'  {cnt:4d}  {cat}')


if __name__ == '__main__':
    main()
