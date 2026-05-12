"""
Map pending unmatched_titles to the 4 newly created roles.

Run: PYTHONPATH=. venv/bin/python scripts/apply_new_role_mappings.py [--dry-run]
"""
import sys, os
sys.path.insert(0, os.getcwd())

DRY_RUN = '--dry-run' in sys.argv

# (substring_in_title_lower, canonical_role_name)
RULES = [
    ('developer relations',         'Developer Relations Engineer'),
    ('developer educator',          'Developer Relations Engineer'),
    ('devrel',                      'Developer Relations Engineer'),
    ('developer advocate',          'Developer Relations Engineer'),
    ('learning & development',      'Learning & Development Manager'),
    ('learning and development',    'Learning & Development Manager'),
    ('learning design',             'Learning & Development Manager'),
    ('curriculum developer',        'Learning & Development Manager'),
    ('curriculum design',           'Learning & Development Manager'),
    ('instructional design',        'Learning & Development Manager'),
    ('game designer',               'Game Designer'),
    ('ui artist',                   'Game Designer'),
    ('level designer',              'Game Designer'),
    ('otc trader',                  'Trader'),
    ('execution trader',            'Trader'),
    ('crypto trader',               'Trader'),
]


def match_rule(title: str):
    t = title.lower()
    for substring, canonical in RULES:
        if substring in t:
            return canonical
    # Also match " trader" (space-prefixed to avoid "day trader program" etc.)
    if ' trader' in t or t.startswith('trader'):
        return 'Trader'
    return None


def main():
    from app import create_app
    from app.models import db, Job, Role, RoleTitleVariation, UnmatchedTitle
    from collections import defaultdict

    app = create_app()
    with app.app_context():
        pending = UnmatchedTitle.query.filter_by(status='pending').all()

        matched = defaultdict(list)   # canonical → [candidate]
        for c in pending:
            canon = match_rule(c.raw_title)
            if canon:
                matched[canon].append(c)

        if not matched:
            print("No matches found.")
            return

        stats = {'jobs': 0, 'variations': 0, 'candidates': 0}

        for canon, candidates in matched.items():
            role = Role.query.filter_by(normalized_title=canon).first()
            if not role:
                print(f"  ❌ Role not found: {canon}")
                continue

            for c in candidates:
                jobs = Job.query.filter_by(title=c.raw_title).all()
                action = "would map" if DRY_RUN else "mapped"
                print(f"  ✅ {action} '{c.raw_title}' → '{canon}' ({len(jobs)} jobs)")

                if not DRY_RUN:
                    for job in jobs:
                        job.role_id = role.id
                    stats['jobs'] += len(jobs)

                    var = RoleTitleVariation.query.filter_by(original_title=c.raw_title).first()
                    if var:
                        var.role_id = role.id
                    else:
                        db.session.add(RoleTitleVariation(
                            role_id=role.id,
                            original_title=c.raw_title,
                            frequency=max(1, c.job_count),
                        ))
                    stats['variations'] += 1

                    c.status = 'approved'
                    c.mapped_role_id = role.id
                    stats['candidates'] += 1

        if not DRY_RUN:
            db.session.commit()

            # Refresh job counts
            from app.models import Job as J
            for canon in matched:
                role = Role.query.filter_by(normalized_title=canon).first()
                if role:
                    role.total_active_jobs = J.query.filter_by(role_id=role.id, is_active=True).count()
            db.session.commit()

        prefix = "DRY RUN " if DRY_RUN else ""
        print(f"\n{prefix}Results:")
        if not DRY_RUN:
            print(f"  Jobs updated:      {stats['jobs']}")
            print(f"  Variations added:  {stats['variations']}")
            print(f"  Candidates approved: {stats['candidates']}")


if __name__ == '__main__':
    main()
