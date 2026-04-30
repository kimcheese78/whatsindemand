"""Re-infer seniority_level for every job by running the shared infer_seniority
helper over the job title. Dry-run first shows the migration matrix.

Run: PYTHONPATH=. python3 scripts/backfill_seniority.py           # dry run
     PYTHONPATH=. python3 scripts/backfill_seniority.py --apply
"""
import sys
from collections import Counter, defaultdict

from app import create_app
from app.models import db, Job
from app.utils.seniority import infer_seniority

APPLY = '--apply' in sys.argv


def main():
    app = create_app()
    with app.app_context():
        rows = db.session.execute(db.text(
            "SELECT id, title, seniority_level FROM jobs"
        )).all()

        migrations = Counter()   # (old, new) -> count
        by_old = Counter()
        by_new = Counter()
        changes = []             # (job_id, old, new)

        for r in rows:
            old = (r.seniority_level or '').lower() or 'null'
            new = infer_seniority(r.title)
            by_old[old] += 1
            by_new[new] += 1
            if old != new:
                migrations[(old, new)] += 1
                changes.append((r.id, old, new))

        print(f'Jobs scanned: {len(rows)}')
        print(f'Labels unchanged: {len(rows) - len(changes)}')
        print(f'Labels changing: {len(changes)}')
        print()

        print('=== Old distribution ===')
        for lv, n in sorted(by_old.items(), key=lambda x: -x[1]):
            print(f'  {lv:<16} {n:>6}')

        print()
        print('=== New distribution ===')
        for lv, n in sorted(by_new.items(), key=lambda x: -x[1]):
            print(f'  {lv:<16} {n:>6}')

        print()
        print('=== Top migrations (old -> new) ===')
        for (o, n), cnt in migrations.most_common(25):
            print(f'  {o:<16} -> {n:<16} {cnt:>5}')

        if APPLY:
            print('\nApplying...')
            # Bulk update via parameterized chunks
            CHUNK = 1000
            for i in range(0, len(changes), CHUNK):
                batch = changes[i:i + CHUNK]
                # build VALUES clause once per chunk
                values = ','.join(f'({jid},:lv{k})' for k, (jid, _, _) in enumerate(batch))
                params = {f'lv{k}': new for k, (_, _, new) in enumerate(batch)}
                sql = f"""
                    UPDATE jobs SET seniority_level = v.lv
                    FROM (VALUES {values}) AS v(id, lv)
                    WHERE jobs.id = v.id
                """
                db.session.execute(db.text(sql), params)
                db.session.commit()
                print(f'  committed {min(i + CHUNK, len(changes))}/{len(changes)}')

            print(f'Done. Updated {len(changes)} rows.')


if __name__ == '__main__':
    main()
