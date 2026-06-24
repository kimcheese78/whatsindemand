"""
Merge a source skill into a destination skill.

Usage:
    PYTHONPATH=. python scripts/merge_skill.py --src "Continuous Integration" --dst "CI/CD"
    PYTHONPATH=. python scripts/merge_skill.py --src "Continuous Integration" --dst "CI/CD" --apply
"""
import argparse
import os
import sys

PROD_DSN = os.environ.get('DATABASE_URL')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', required=True, help='Name of skill to merge away')
    parser.add_argument('--dst', required=True, help='Name of skill to keep')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    from app import create_app
    from app.models import db, Skill, JobSkill
    from sqlalchemy import func

    app = create_app()
    with app.app_context():
        src = Skill.query.filter_by(name=args.src).first()
        dst = Skill.query.filter_by(name=args.dst).first()

        if not src:
            sys.exit(f'Source skill not found: {args.src!r}')
        if not dst:
            sys.exit(f'Destination skill not found: {args.dst!r}')

        src_js = JobSkill.query.filter_by(skill_id=src.id).count()
        dst_js = JobSkill.query.filter_by(skill_id=dst.id).count()

        print(f'Source:      [{src.id}] {src.name!r}  aliases={src.aliases}  jobs={src.total_job_count}  job_skill rows={src_js}')
        print(f'Destination: [{dst.id}] {dst.name!r}  aliases={dst.aliases}  jobs={dst.total_job_count}  job_skill rows={dst_js}')

        # JobSkill rows to move
        src_rows = JobSkill.query.filter_by(skill_id=src.id).all()
        dst_job_ids = {row.job_id for row in JobSkill.query.filter_by(skill_id=dst.id).all()}

        migrate, skip = [], []
        for row in src_rows:
            if row.job_id in dst_job_ids:
                skip.append(row.job_id)
            else:
                migrate.append(row)

        print(f'\nJobSkill rows to migrate: {len(migrate)}')
        print(f'JobSkill rows to drop (job already has dst skill): {len(skip)}')

        # Aliases to absorb
        existing_aliases = set(a.lower() for a in (dst.aliases or []))
        candidates = [args.src] + list(src.aliases or [])
        new_aliases = [a for a in candidates if a.lower() not in existing_aliases and a.lower() != args.dst.lower()]
        print(f'\nAliases to add to {args.dst!r}: {new_aliases}')

        if not args.apply:
            print('\nDry run — pass --apply to execute.')
            return

        from sqlalchemy import text

        # Delete conflicting rows (job already has dst skill) — bulk single statement
        db.session.execute(text(
            "DELETE FROM job_skills WHERE skill_id = :src_id AND job_id IN "
            "(SELECT job_id FROM job_skills WHERE skill_id = :dst_id)"
        ), {'src_id': src.id, 'dst_id': dst.id})

        # Move remaining rows — single bulk UPDATE
        db.session.execute(text(
            "UPDATE job_skills SET skill_id = :dst_id WHERE skill_id = :src_id"
        ), {'dst_id': dst.id, 'src_id': src.id})

        # Absorb aliases
        dst.aliases = list(dst.aliases or []) + new_aliases

        # Recompute total_job_count for dst from actual rows
        new_count_row = db.session.execute(text(
            "SELECT COUNT(*) FROM job_skills WHERE skill_id = :dst_id"
        ), {'dst_id': dst.id}).scalar()
        dst.total_job_count = new_count_row

        # Delete source skill
        db.session.delete(src)
        db.session.commit()

        print(f'\nDone. {args.dst!r} now has {new_count_row} job_skill rows.')
        print(f'Aliases: {dst.aliases}')


if __name__ == '__main__':
    main()
