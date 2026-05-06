"""Rebuild roles using the canonical-taxonomy normalizer (role_normalizer_v2).

Run:
  python scripts/rebuild_roles_v2.py           # dry run, prints changes
  python scripts/rebuild_roles_v2.py --apply   # write changes

Behavior:
  1. Run every job's title through role_normalizer_v2.normalize_title.
  2. For each canonical_id seen, upsert a Role keyed by canonical name.
     Seniority is now job-level, so role.seniority_level is left NULL.
  3. Reassign job.role_id; populate job.seniority_level from per-job result.
  4. Rebuild role_title_variations from raw titles seen.
  5. Recompute role.total_active_jobs.
  6. Delete now-empty roles.
  7. Print summary including count of jobs that landed in canonical_id=None
     (the manual-review queue).
"""
import sys
import time
from collections import Counter, defaultdict

from app import create_app
from app.models import db, Job, Role, RoleTitleVariation
from app.utils.role_normalizer_v2 import normalize_title, _load_taxonomy

APPLY = '--apply' in sys.argv
app = create_app()


def log(msg):
    print(msg, flush=True)


def main():
    t0 = time.time()
    canonical_taxonomy, _ = _load_taxonomy()

    with app.app_context():
        log(f'[{time.time()-t0:.1f}s] loading jobs...')
        jobs = Job.query.with_entities(
            Job.id, Job.title, Job.is_active, Job.role_id, Job.seniority_level
        ).all()
        log(f'[{time.time()-t0:.1f}s] Jobs: {len(jobs)}')

        # 1) normalize
        log(f'[{time.time()-t0:.1f}s] normalizing titles...')
        norm_cache = {}
        job_to_canonical = {}        # job.id -> canonical_id (or None)
        job_to_seniority = {}        # job.id -> seniority or None
        active_jobs_by_canonical = Counter()
        variations_by_canonical = defaultdict(Counter)  # canonical_id -> {title: freq}
        unmapped_titles = Counter()  # raw title -> freq (for manual review)
        skipped = 0

        for i, job in enumerate(jobs):
            title = job.title or ''
            if title not in norm_cache:
                norm_cache[title] = normalize_title(title)
            res = norm_cache[title]
            cid = res['canonical_id']
            sen = res['seniority_level']

            if res['category'] == 'Skip':
                skipped += 1
                job_to_canonical[job.id] = None
                job_to_seniority[job.id] = None
                continue

            job_to_canonical[job.id] = cid
            job_to_seniority[job.id] = sen

            if cid is None:
                unmapped_titles[title] += 1
            else:
                variations_by_canonical[cid][title] += 1
                if job.is_active:
                    active_jobs_by_canonical[cid] += 1

            if (i + 1) % 5000 == 0:
                log(f'[{time.time()-t0:.1f}s]   normalized {i+1}/{len(jobs)}')

        canonical_seen = set(c for c in job_to_canonical.values() if c)
        log(f'[{time.time()-t0:.1f}s] Canonical IDs hit: {len(canonical_seen)} / {len(canonical_taxonomy)}')
        log(f'[{time.time()-t0:.1f}s] Distinct raw titles: {len(norm_cache)}')
        log(f'[{time.time()-t0:.1f}s] Skipped (junk): {skipped} jobs')
        log(f'[{time.time()-t0:.1f}s] Unmapped: {sum(unmapped_titles.values())} jobs '
            f'({len(unmapped_titles)} distinct titles)')

        # 2) upsert roles by canonical name (== normalized_title)
        log(f'[{time.time()-t0:.1f}s] upserting roles...')
        existing_roles = {r.normalized_title: r for r in Role.query.all()}
        canonical_to_role_id = {}
        created = 0
        updated = 0
        for cid in canonical_seen:
            taxon = canonical_taxonomy[cid]
            name = taxon['name']
            r = existing_roles.get(name)
            if r is None:
                if APPLY:
                    r = Role(
                        normalized_title=name,
                        category=taxon['category'],
                        job_family=taxon['job_family'],
                        seniority_level=None,  # job-level now
                        total_active_jobs=0,
                    )
                    db.session.add(r)
                    db.session.flush()
                    existing_roles[name] = r
                    canonical_to_role_id[cid] = r.id
                created += 1
            else:
                if (r.category != taxon['category'] or
                        r.job_family != taxon['job_family'] or
                        r.seniority_level is not None):
                    if APPLY:
                        r.category = taxon['category']
                        r.job_family = taxon['job_family']
                        r.seniority_level = None
                    updated += 1
                canonical_to_role_id[cid] = r.id

        if APPLY:
            db.session.commit()
        log(f'  Roles created: {created}, updated: {updated}')

        # 3) reassign job.role_id and job.seniority_level
        log(f'[{time.time()-t0:.1f}s] computing job reassignments...')
        reassignments = []
        for job in jobs:
            cid = job_to_canonical.get(job.id)
            new_role_id = canonical_to_role_id.get(cid) if cid else None
            new_sen = job_to_seniority.get(job.id)
            if job.role_id != new_role_id or job.seniority_level != new_sen:
                reassignments.append({
                    'id': job.id,
                    'role_id': new_role_id,
                    'seniority_level': new_sen,
                })
        log(f'[{time.time()-t0:.1f}s] Jobs to reassign: {len(reassignments)}')

        if APPLY and reassignments:
            BATCH = 2000
            for i in range(0, len(reassignments), BATCH):
                db.session.bulk_update_mappings(Job, reassignments[i:i+BATCH])
                db.session.commit()
            log(f'[{time.time()-t0:.1f}s] reassignments committed')

        # 4) recompute total_active_jobs
        if APPLY:
            Role.query.update({Role.total_active_jobs: 0})
            for cid, cnt in active_jobs_by_canonical.items():
                rid = canonical_to_role_id.get(cid)
                if rid:
                    Role.query.filter_by(id=rid).update({Role.total_active_jobs: cnt})
            db.session.commit()
        log(f'  total_active_jobs recomputed for {len(active_jobs_by_canonical)} roles')

        # 5) rebuild role_title_variations
        if APPLY:
            RoleTitleVariation.query.delete()
            db.session.commit()
            batch = []
            for cid, titles in variations_by_canonical.items():
                rid = canonical_to_role_id.get(cid)
                if not rid:
                    continue
                for t, freq in titles.items():
                    batch.append(RoleTitleVariation(
                        role_id=rid, original_title=t, frequency=freq))
                    if len(batch) >= 1000:
                        db.session.bulk_save_objects(batch)
                        db.session.commit()
                        batch = []
            if batch:
                db.session.bulk_save_objects(batch)
                db.session.commit()
        n_variations = sum(len(v) for v in variations_by_canonical.values())
        log(f'  Variations rebuilt: {n_variations}')

        # 6) delete empty roles
        log(f'[{time.time()-t0:.1f}s] finding empty roles...')
        empty_role_ids = [rid for (rid,) in db.session.execute(db.text("""
            SELECT r.id FROM roles r
            LEFT JOIN jobs j ON j.role_id = r.id
            LEFT JOIN role_title_variations rtv ON rtv.role_id = r.id
            LEFT JOIN skills_demand sd ON sd.role_id = r.id
            WHERE j.id IS NULL AND rtv.id IS NULL AND sd.id IS NULL
        """)).all()]
        log(f'  Empty roles to delete: {len(empty_role_ids)}')
        if APPLY and empty_role_ids:
            db.session.execute(
                db.text("DELETE FROM roles WHERE id = ANY(:ids)"),
                {'ids': empty_role_ids})
            db.session.commit()

        # 7) report
        log('')
        log(f'=== Final state (mode={"APPLY" if APPLY else "DRY-RUN"}) ===')
        log(f'Roles in DB: {Role.query.count()}')
        log(f'Active jobs: {Job.query.filter_by(is_active=True).count()}')
        log(f'Active jobs with role_id: {Job.query.filter(Job.is_active.is_(True), Job.role_id.isnot(None)).count()}')
        log(f'Active jobs unmapped (role_id IS NULL): {Job.query.filter(Job.is_active.is_(True), Job.role_id.is_(None)).count()}')
        log('')
        log('Top 20 unmapped raw titles (manual-review queue):')
        for t, c in unmapped_titles.most_common(20):
            log(f'  ({c:>3}) {t}')
        log('')
        if APPLY:
            top = Role.query.order_by(Role.total_active_jobs.desc()).limit(15).all()
            log('Top roles by active jobs:')
            for r in top:
                log(f'  {(r.total_active_jobs or 0):>5}  [{r.category}] {r.normalized_title}')
        log(f'[{time.time()-t0:.1f}s] done')


if __name__ == '__main__':
    main()
