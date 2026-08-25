"""
One-shot: execute the 2026-08-26 role merge/split review on prod.

The forward-facing fixes already live in data/aliases.yaml + app/utils/role_normalizer_v2.py
(so NEW scrapes route correctly). This script repoints the EXISTING jobs + title-variation
rows that were mis-bucketed under the old engine, since _get_or_create_role only consults the
variation table for Unknown titles — mis-mapped historical rows are otherwise pinned.

Tier A merges (source role emptied to 0 jobs, NOT deleted — SkillDemand has no delete cascade):
  - Commercial Account Executive      -> Mid-Market Account Executive
  - People Business Partner           -> HR Business Partner
  - People Partner                    -> HR Business Partner   (except 'compensation'* -> Compensation Analyst)
  - Director of Design                -> Design Director        (fixes duplicate 'design director' alias key)

Tier B de-pollution (this pass = the unambiguous BCBA slice only; strategist/producer/other
analyst families stay queued for a per-title classification pass):
  - Business Analyst: titles matching 'behavior analyst' / 'BCBA' -> Behavioral Specialist

Usage:
  DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/merge_split_roles_2026_08.py           # dry-run
  DATABASE_URL='<prod>' PYTHONPATH=. venv/bin/python scripts/merge_split_roles_2026_08.py --apply    # commit
"""
import os
import sys

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set (pass prod DSN). See CLAUDE.md.')

APPLY = '--apply' in sys.argv

from app import create_app, db
from app.models import Role

# Each op: (source_name, [(predicate_sql_or_None, dest_name), ...])
# Predicates are applied in order; a None predicate is the catch-all remainder.
# The predicate uses {col} so it works for both jobs.title and role_title_variations.original_title.
OPS = [
    ("Commercial Account Executive", [(None, "Mid-Market Account Executive")]),
    ("People Business Partner",       [(None, "HR Business Partner")]),
    ("People Partner", [
        ("{col} ILIKE '%compensation%'", "Compensation Analyst"),
        (None,                            "HR Business Partner"),
    ]),
    ("Director of Design",            [(None, "Design Director")]),
    # EXTRACT: remainder stays in Business Analyst (no None catch-all)
    ("Business Analyst", [
        ("({col} ILIKE '%behavior analyst%' OR {col} ILIKE '%bcba%')", "Behavioral Specialist"),
    ]),
]


def rid(name):
    r = Role.query.filter_by(normalized_title=name).first()
    if not r:
        raise SystemExit(f"ERROR: role not found: {name!r}")
    return r.id


def active_count(role_id):
    return db.session.execute(db.text(
        "SELECT COUNT(*) FROM jobs WHERE role_id=:i AND is_active=TRUE"), {'i': role_id}).scalar()


def move(src_id, pred, dest_id, col_table):
    col = 'title' if col_table == 'jobs' else 'original_title'
    where = f"role_id=:src" + (f" AND {pred.format(col=col)}" if pred else "")
    res = db.session.execute(db.text(
        f"UPDATE {col_table} SET role_id=:dest WHERE {where}"),
        {'src': src_id, 'dest': dest_id})
    return res.rowcount


def main():
    app = create_app()
    with app.app_context():
        # Resolve all role ids up front (fails loudly if any name is wrong)
        touched = set()
        resolved = []  # (src_id, src_name, [(pred, dest_id, dest_name)])
        for src_name, rules in OPS:
            src_id = rid(src_name)
            touched.add(src_id)
            rlist = []
            for pred, dest_name in rules:
                d = rid(dest_name)
                touched.add(d)
                rlist.append((pred, d, dest_name))
            resolved.append((src_id, src_name, rlist))

        before = {i: active_count(i) for i in touched}
        names = {i: Role.query.get(i).normalized_title for i in touched}

        print(f"{'MODE':6}: {'APPLY' if APPLY else 'DRY-RUN'}\n")
        print("Row moves (active-job counts shown; variation rows moved too):")
        for src_id, src_name, rlist in resolved:
            for pred, dest_id, dest_name in rlist:
                aj = db.session.execute(db.text(
                    "SELECT COUNT(*) FROM jobs WHERE role_id=:s AND is_active=TRUE" +
                    (f" AND {pred.format(col='title')}" if pred else "")), {'s': src_id}).scalar()
                j_moved = move(src_id, pred, dest_id, 'jobs')
                v_moved = move(src_id, pred, dest_id, 'role_title_variations')
                tag = 'ALL' if pred is None else pred.format(col='title')
                print(f"  [{src_name}] -> [{dest_name}]: {j_moved} jobs ({aj} active), {v_moved} variations   ({tag})")

        # Recompute denormalized counts for every touched role (mirrors job_aggregator._update_role_counts)
        db.session.execute(db.text("""
            UPDATE roles SET total_active_jobs = (
                SELECT COUNT(*) FROM jobs j WHERE j.role_id = roles.id AND j.is_active = TRUE
            ) WHERE id = ANY(:ids)
        """), {'ids': list(touched)})

        after = {i: active_count(i) for i in touched}
        print("\nPer-role active jobs (before -> after):")
        for i in sorted(touched, key=lambda x: -before[x]):
            arrow = '' if before[i] == after[i] else '   <-- CHANGED'
            print(f"  {names[i]:38s} (id {i:5}): {before[i]:5} -> {after[i]:5}{arrow}")

        if APPLY:
            db.session.commit()
            print("\n✅ COMMITTED to prod.")
        else:
            db.session.rollback()
            print("\n(dry-run — rolled back; re-run with --apply to commit)")


if __name__ == '__main__':
    main()
