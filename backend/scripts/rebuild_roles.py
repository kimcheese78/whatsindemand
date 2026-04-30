"""
Re-normalize every job title with the current normalizer, rebuild role_title_variations,
merge roles whose normalized_title now matches, and delete now-empty roles.

Run: python scripts/rebuild_roles.py           # dry run: prints what would change
     python scripts/rebuild_roles.py --apply   # actually writes changes
"""
import sys
import time
from collections import Counter, defaultdict

from app import create_app
from app.models import db, Job, Role, RoleTitleVariation
from app.utils.role_normalizer import normalize_title

APPLY = '--apply' in sys.argv
app = create_app()


def log(msg):
    print(msg, flush=True)


def main():
    t0 = time.time()
    with app.app_context():
        log(f'[{time.time()-t0:.1f}s] loading jobs...')
        jobs = Job.query.with_entities(Job.id, Job.title, Job.is_active, Job.role_id).all()
        log(f'[{time.time()-t0:.1f}s] Jobs: {len(jobs)}')

        # Step 1: normalize every job title -> compute target role attributes
        # Keep counters by target normalized_title
        target_info = {}  # normalized_title -> dict of category/job_family/seniority (from first seen)
        job_to_target = {}  # job.id -> normalized_title
        target_job_count_active = Counter()
        variations_by_target = defaultdict(Counter)  # normalized -> {original_title: freq}

        log(f'[{time.time()-t0:.1f}s] normalizing titles...')
        # Cache normalization by raw title (many jobs share a title)
        norm_cache = {}
        for i, job in enumerate(jobs):
            title = job.title or ''
            if title not in norm_cache:
                norm_cache[title] = normalize_title(title)
            result = norm_cache[title]
            norm = result['normalized_title']
            job_to_target[job.id] = norm
            if norm not in target_info:
                target_info[norm] = {
                    'category': result['category'],
                    'job_family': result['job_family'],
                    'seniority_level': result['seniority_level'],
                }
            if job.is_active:
                target_job_count_active[norm] += 1
            variations_by_target[norm][title] += 1
            if (i + 1) % 5000 == 0:
                log(f'[{time.time()-t0:.1f}s]   normalized {i+1}/{len(jobs)}')

        log(f'[{time.time()-t0:.1f}s] Distinct target normalized_titles: {len(target_info)}')
        log(f'[{time.time()-t0:.1f}s] Distinct raw titles normalized: {len(norm_cache)}')
        log(f'[{time.time()-t0:.1f}s] Currently existing roles: {Role.query.count()}')

        # Step 2: upsert roles by normalized_title
        existing_roles = {r.normalized_title: r for r in Role.query.all()}
        created = 0
        for norm, info in target_info.items():
            r = existing_roles.get(norm)
            if not r:
                if APPLY:
                    r = Role(
                        normalized_title=norm,
                        category=info['category'],
                        job_family=info['job_family'],
                        seniority_level=info['seniority_level'],
                        total_active_jobs=0,
                    )
                    db.session.add(r)
                    db.session.flush()
                    existing_roles[norm] = r
                created += 1
        print(f'Roles to create: {created}')

        if APPLY:
            db.session.commit()
            existing_roles = {r.normalized_title: r for r in Role.query.all()}

        # Step 3: reassign job.role_id (bulk update via mappings)
        log(f'[{time.time()-t0:.1f}s] computing reassignments...')
        reassignments = []  # list of (job_id, new_role_id)
        for job in jobs:
            norm = job_to_target[job.id]
            target = existing_roles.get(norm)
            if target is None:
                continue
            if job.role_id != target.id:
                reassignments.append({'id': job.id, 'role_id': target.id})
        log(f'[{time.time()-t0:.1f}s] Jobs to reassign: {len(reassignments)}')

        if APPLY and reassignments:
            log(f'[{time.time()-t0:.1f}s] applying reassignments in bulk...')
            db.session.bulk_update_mappings(Job, reassignments)
            db.session.commit()
            log(f'[{time.time()-t0:.1f}s] reassignments committed')

        # Step 4: recompute role.total_active_jobs
        if APPLY:
            # zero out
            Role.query.update({Role.total_active_jobs: 0})
            db.session.commit()
            for norm, cnt in target_job_count_active.items():
                r = existing_roles.get(norm)
                if r:
                    r.total_active_jobs = cnt
            db.session.commit()
        print(f'Recomputed total_active_jobs for {len(target_job_count_active)} roles')

        # Step 5: rebuild role_title_variations
        if APPLY:
            RoleTitleVariation.query.delete()
            db.session.commit()
            batch = []
            for norm, titles in variations_by_target.items():
                r = existing_roles.get(norm)
                if not r:
                    continue
                for t, freq in titles.items():
                    batch.append(RoleTitleVariation(role_id=r.id, original_title=t, frequency=freq))
                    if len(batch) >= 1000:
                        db.session.bulk_save_objects(batch)
                        db.session.commit()
                        batch = []
            if batch:
                db.session.bulk_save_objects(batch)
                db.session.commit()
        print(f'Variations to rebuild: {sum(len(v) for v in variations_by_target.values())}')

        # Step 6: delete roles with no jobs (variations were just rebuilt, so if they
        # were rebuilt under a different role this one has none either).
        log(f'[{time.time()-t0:.1f}s] finding empty roles...')
        empty_role_ids = [rid for (rid,) in db.session.execute(db.text("""
            SELECT r.id FROM roles r
            LEFT JOIN jobs j ON j.role_id = r.id
            LEFT JOIN role_title_variations rtv ON rtv.role_id = r.id
            WHERE j.id IS NULL AND rtv.id IS NULL
        """)).all()]
        log(f'[{time.time()-t0:.1f}s] Empty roles to delete: {len(empty_role_ids)}')
        if APPLY and empty_role_ids:
            db.session.execute(db.text("DELETE FROM roles WHERE id = ANY(:ids)"),
                               {'ids': empty_role_ids})
            db.session.commit()

        # Step 7: report
        total_roles = Role.query.count()
        active_jobs = Job.query.filter_by(is_active=True).count()
        log('')
        log(f'=== Final state (mode={"APPLY" if APPLY else "DRY-RUN"}) ===')
        log(f'Roles: {total_roles}')
        log(f'Active jobs: {active_jobs}')
        top = Role.query.order_by(Role.total_active_jobs.desc()).limit(15).all()
        log('Top roles:')
        for r in top:
            log(f'  {r.total_active_jobs:5d}  {r.normalized_title}')
        log(f'[{time.time()-t0:.1f}s] done')


if __name__ == '__main__':
    main()
