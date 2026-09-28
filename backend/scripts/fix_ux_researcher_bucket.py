"""Re-classify the contaminated "UX Researcher" role bucket (role_id 3436).

Root cause: aliases.yaml had a bare `"research associate": ux_researcher`
fallback, so role_normalizer_v2 mapped every lab / clinical / equity
"Research Associate" title to UX Researcher. Fixed in aliases.yaml +
canonical_roles.yaml. This script re-runs the FIXED normalizer over every
job currently tagged UX Researcher and re-assigns Job.role_id to the role
the normalizer now produces, so the DB converges with future scrapes.

Also repoints the stale role_title_variations rows under role 3436 and
rebuilds total_active_jobs for every affected role.

Dry-run by default; pass --apply to write. Read-only DB access otherwise.

    cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python \
        scripts/fix_ux_researcher_bucket.py [--apply]
"""
import sys
from collections import defaultdict

from app import create_app
from app.models import db, Job, Role, RoleTitleVariation
from app.utils.role_normalizer_v2 import normalize_title

UX_ROLE_ID = 3436

# Titles the normalizer still mis-handles (edge cases not worth an alias).
# Route to the unmatched queue (role_id = NULL) instead of a wrong bucket.
FORCE_UNMATCHED = {
    "scientific linux researcher",
}

# Data-only corrections for a handful of dash/slash-form titles the normalizer
# de-levels in a way that bypasses the finance/clinical aliases. Keyed by
# lowercased-stripped raw title -> exact target Role.normalized_title. These are
# rare (<5 jobs); future scrapes of these exact odd forms may still drift, which
# is acceptable at this volume.
TITLE_OVERRIDES = {
    "capital markets - research associate": "Financial Analyst",
    "research associate, commodities data engineer": "Financial Analyst",
    "research associate, equities data engineer": "Financial Analyst",
    "senior/clinical research associate": "Clinical Research Associate",
}


def resolve_role(title):
    """Return (role_or_None, reason). None => send to unmatched (NULL)."""
    key = title.strip().lower()
    if key in FORCE_UNMATCHED:
        return None, "forced-unmatched"
    if key in TITLE_OVERRIDES:
        role = Role.query.filter_by(normalized_title=TITLE_OVERRIDES[key]).first()
        if role:
            return role, "override"
    info = normalize_title(title)
    nt = info.get("normalized_title")
    if not nt or nt == "Unknown":
        return None, "normalizer-unknown"
    role = Role.query.filter_by(normalized_title=nt).first()
    if role is None:
        return None, f"no-db-role:{nt}"
    return role, "ok"


def main():
    apply = "--apply" in sys.argv
    app = create_app()
    with app.app_context():
        jobs = Job.query.filter(Job.role_id == UX_ROLE_ID).all()
        active_total = sum(1 for j in jobs if j.is_active)
        print(f"Jobs under role {UX_ROLE_ID} (UX Researcher): "
              f"{len(jobs)} total, {active_total} active\n")

        # Group jobs by title -> destination
        by_dest = defaultdict(lambda: {"active": 0, "total": 0, "titles": set()})
        moves = []  # (job, dest_role_id_or_None)
        for j in jobs:
            role, reason = resolve_role(j.title)
            dest_id = role.id if role else None
            dest_name = role.normalized_title if role else f"<UNMATCHED: {reason}>"
            key = (dest_id, dest_name)
            by_dest[key]["active"] += 1 if j.is_active else 0
            by_dest[key]["total"] += 1
            by_dest[key]["titles"].add(j.title)
            if dest_id != UX_ROLE_ID:
                moves.append((j, dest_id))

        print("DESTINATION SUMMARY (active / total jobs):")
        print("=" * 70)
        for (dest_id, dest_name), agg in sorted(
                by_dest.items(), key=lambda kv: -kv[1]["active"]):
            tag = "  [KEEP]" if dest_id == UX_ROLE_ID else ""
            print(f"  {agg['active']:4d} / {agg['total']:4d}  -> "
                  f"{dest_name} (role {dest_id}){tag}")
        print("=" * 70)

        # Full title-by-title table for the non-UX moves (the eyeball list)
        print("\nTITLE -> DESTINATION (jobs being moved OUT of UX Researcher):")
        print("-" * 70)
        rows = []
        for (dest_id, dest_name), agg in by_dest.items():
            if dest_id == UX_ROLE_ID:
                continue
            for t in sorted(agg["titles"]):
                n = sum(1 for j in jobs if j.title == t and j.is_active)
                rows.append((dest_name, t, n))
        for dest_name, t, n in sorted(rows):
            print(f"  [{n:2d}] {t!r:60s} -> {dest_name}")

        kept = active_total - sum(1 for j, d in moves if j.is_active)
        print("-" * 70)
        print(f"\nGenuine UX Researcher jobs kept (active): {kept}")
        print(f"Jobs moved (active+inactive): {len(moves)}")

        # Stale variation rows under UX Researcher that are no longer UX
        vars_ = RoleTitleVariation.query.filter_by(role_id=UX_ROLE_ID).all()
        var_moves = []
        for v in vars_:
            role, _ = resolve_role(v.original_title)
            dest_id = role.id if role else None
            if dest_id != UX_ROLE_ID:
                var_moves.append((v, dest_id))
        print(f"role_title_variations under {UX_ROLE_ID}: {len(vars_)} total, "
              f"{len(var_moves)} to repoint/delete")

        affected = {UX_ROLE_ID} | {d for _, d in moves if d} | {d for _, d in var_moves if d}

        if not apply:
            print("\n[DRY RUN] No changes written. Re-run with --apply to commit.")
            return

        print("\n[APPLY] Writing changes...")
        for j, dest_id in moves:
            j.role_id = dest_id
        for v, dest_id in var_moves:
            if dest_id is None:
                db.session.delete(v)
            else:
                v.role_id = dest_id
        db.session.flush()

        # Rebuild total_active_jobs for every affected role
        for rid in affected:
            role = db.session.get(Role, rid)
            if role is None:
                continue
            cnt = Job.query.filter_by(role_id=rid, is_active=True).count()
            role.total_active_jobs = cnt
            print(f"  role {rid} {role.normalized_title!r}: total_active_jobs={cnt}")

        db.session.commit()
        print("\nDone.")


if __name__ == "__main__":
    main()
