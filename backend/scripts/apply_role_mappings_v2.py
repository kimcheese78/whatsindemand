"""Apply decisions from role_mapping_decisions.json to the database.

  map       → set role_id on matching jobs, upsert RoleTitleVariation,
              mark UnmatchedTitle approved
  new_role  → create canonical Role row (if missing), then treat like map
  reject    → mark UnmatchedTitle rejected

Usage (dry-run by default, --apply to write):
    cd backend
    DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/apply_role_mappings_v2.py [--apply]
"""
import json, os, sys
from collections import defaultdict

# Pass DATABASE_URL as an env var — see CLAUDE.md for the prod DSN.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Job, Role, RoleTitleVariation, UnmatchedTitle

APPLY = '--apply' in sys.argv
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DECISIONS_FILE = os.path.join(DATA_DIR, 'role_mapping_decisions.json')

BATCH = 500  # commit cadence


def _upsert_variation(role_id: int, raw_title: str, job_count: int) -> str:
    existing = RoleTitleVariation.query.filter_by(original_title=raw_title).first()
    if existing:
        existing.role_id = role_id
        existing.frequency = max(existing.frequency, job_count)
        return 'updated'
    db.session.add(RoleTitleVariation(role_id=role_id, original_title=raw_title,
                                      frequency=max(1, job_count)))
    return 'created'


def _approve_unmatched(raw_title: str, role_id: int):
    ut = UnmatchedTitle.query.filter_by(raw_title=raw_title).first()
    if ut:
        ut.status = 'approved'
        ut.mapped_role_id = role_id


def apply_map(decisions: list, roles_by_id: dict) -> dict:
    stats = defaultdict(int)
    for i, dec in enumerate(decisions):
        rid, raw_title, jobs = dec['role_id'], dec['title'], dec['jobs']
        if rid not in roles_by_id:
            stats['missing_role'] += 1
            continue

        updated = db.session.query(Job).filter(Job.title == raw_title, Job.role_id.is_(None)
                                               ).update({'role_id': rid}, synchronize_session=False)
        stats['jobs_updated'] += updated

        action = _upsert_variation(rid, raw_title, jobs)
        stats[f'variation_{action}'] += 1

        _approve_unmatched(raw_title, rid)
        stats['candidates_approved'] += 1

        if APPLY and (i + 1) % BATCH == 0:
            db.session.commit()
            print(f'  … committed {i+1}/{len(decisions)} map decisions')

    return stats


def apply_new_roles(decisions: list, role_defs: list) -> dict:
    stats = defaultdict(int)

    # Build definition lookup by title
    def_by_title = {d['normalized_title']: d for d in role_defs}

    # Create missing roles
    new_role_id_map: dict[str, int] = {}
    for title, defn in def_by_title.items():
        existing = Role.query.filter_by(normalized_title=title).first()
        if existing:
            new_role_id_map[title] = existing.id
            print(f'  Role already exists: "{title}" (id={existing.id})')
        else:
            role = Role(
                normalized_title=title,
                category=defn.get('category'),
                job_family=defn.get('job_family'),
                seniority_level=defn.get('seniority_level'),
                total_active_jobs=0,
            )
            if APPLY:
                db.session.add(role)
                db.session.flush()  # get id before commit
                new_role_id_map[title] = role.id
                print(f'  Created new role: "{title}" (id={role.id})')
            else:
                new_role_id_map[title] = None
                print(f'  [dry] Would create role: "{title}"')
            stats['roles_created'] += 1

    if APPLY:
        db.session.commit()

    # Apply mappings for each new-role decision
    for i, dec in enumerate(decisions):
        nr_title = dec['new_role_title']
        raw_title = dec['title']
        jobs = dec['jobs']
        rid = new_role_id_map.get(nr_title)
        if not rid:
            stats['missing_new_role'] += 1
            continue

        updated = db.session.query(Job).filter(Job.title == raw_title, Job.role_id.is_(None)
                                               ).update({'role_id': rid}, synchronize_session=False)
        stats['jobs_updated'] += updated

        action = _upsert_variation(rid, raw_title, jobs)
        stats[f'variation_{action}'] += 1

        _approve_unmatched(raw_title, rid)
        stats['candidates_approved'] += 1

        if APPLY and (i + 1) % BATCH == 0:
            db.session.commit()

    return stats


def apply_rejects(decisions: list) -> dict:
    stats = defaultdict(int)
    for dec in decisions:
        ut = UnmatchedTitle.query.filter_by(raw_title=dec['title']).first()
        if ut:
            ut.status = 'rejected'
            ut.rejected_reason = dec.get('reason', 'auto-rejected')
            stats['rejected'] += 1
    return stats


def refresh_role_counts(affected_ids: set):
    roles = Role.query.filter(Role.id.in_(affected_ids)).all()
    for role in roles:
        role.total_active_jobs = Job.query.filter_by(role_id=role.id, is_active=True).count()
    print(f'  Refreshed total_active_jobs for {len(roles)} roles')


def main():
    with open(DECISIONS_FILE) as f:
        data = json.load(f)

    meta = data['meta']
    print(f'Decisions file: {meta["total"]:,} total candidates')
    print(f'  map={meta["map"]:,}  new_role={meta["new_role"]:,}  '
          f'reject={meta["reject"]:,}  skip={meta["skip"]:,}')
    print(f'Mode: {"APPLY" if APPLY else "DRY RUN"}')
    print()

    app = create_app()
    with app.app_context():
        roles = db.session.execute(db.text('SELECT id FROM roles')).fetchall()
        roles_by_id = {r.id for r in roles}

        # ── 1. Map to existing roles ──────────────────────────────────────────
        print(f'Processing {len(data["map"]):,} map decisions …')
        map_stats = apply_map(data['map'], roles_by_id)

        # ── 2. Create new roles + map ─────────────────────────────────────────
        print(f'\nProcessing {len(data["new_role"]):,} new-role decisions …')
        nr_stats = apply_new_roles(data['new_role'], data.get('new_role_definitions', []))

        # ── 3. Reject noise ───────────────────────────────────────────────────
        print(f'\nProcessing {len(data["reject"]):,} reject decisions …')
        rej_stats = apply_rejects(data['reject'])

        # ── 4. Commit & refresh counts ────────────────────────────────────────
        if APPLY:
            db.session.commit()

            # Refresh counts for all touched roles
            affected_ids = set()
            for dec in data['map']:
                affected_ids.add(dec['role_id'])
            for dec in data['new_role']:
                ut = UnmatchedTitle.query.filter_by(raw_title=dec['title']).first()
                if ut and ut.mapped_role_id:
                    affected_ids.add(ut.mapped_role_id)
            refresh_role_counts(affected_ids)
            db.session.commit()
            print()

        # ── Summary ───────────────────────────────────────────────────────────
        print(f'\n{"=" * 50}')
        print(f'{"DRY RUN " if not APPLY else ""}Results:')
        print(f'  Map decisions:')
        print(f'    Jobs updated:          {map_stats["jobs_updated"]:,}')
        print(f'    Variations created:    {map_stats["variation_created"]:,}')
        print(f'    Variations updated:    {map_stats["variation_updated"]:,}')
        print(f'    Candidates approved:   {map_stats["candidates_approved"]:,}')
        if map_stats['missing_role']:
            print(f'    Missing roles:         {map_stats["missing_role"]:,}  ← role IDs not in DB')
        print(f'  New-role decisions:')
        print(f'    Roles created:         {nr_stats["roles_created"]:,}')
        print(f'    Jobs updated:          {nr_stats["jobs_updated"]:,}')
        print(f'    Candidates approved:   {nr_stats["candidates_approved"]:,}')
        print(f'  Reject decisions:')
        print(f'    Candidates rejected:   {rej_stats["rejected"]:,}')
        print()
        if not APPLY:
            print('Re-run with --apply to commit changes.')


if __name__ == '__main__':
    main()
