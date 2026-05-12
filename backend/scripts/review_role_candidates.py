"""Interactive CLI to review unmatched role candidates.

For each pending raw title you can:
  y  — approve: pick or create a canonical role to map it to, adds alias to RoleTitleVariation
  n  — reject: mark as rejected (won't queue again)
  s  — skip: leave pending for later
  q  — quit

Usage:
    PYTHONPATH=. venv/bin/python scripts/review_unmatched_titles.py
    PYTHONPATH=. venv/bin/python scripts/review_unmatched_titles.py --min-count 3
"""
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Role, UnmatchedTitle, RoleTitleVariation

app = create_app()

_RESET  = '\033[0m'
_BOLD   = '\033[1m'
_GREEN  = '\033[32m'
_RED    = '\033[31m'
_YELLOW = '\033[33m'
_CYAN   = '\033[36m'
_DIM    = '\033[2m'

def _c(text, *codes):
    return ''.join(codes) + str(text) + _RESET


def _print_candidate(idx, total, c):
    print()
    print(_c('─' * 60, _DIM))
    print(_c(f'[{idx}/{total}]', _DIM) + '  ' + _c(c.raw_title, _BOLD) +
          f'   seen: {_c(c.job_count, _CYAN)} times')
    if c.first_seen or c.last_seen:
        print(_c(f'  first: {c.first_seen}   last: {c.last_seen}', _DIM))
    print()
    print(_c('  y', _GREEN) + ' approve   ' + _c('n', _RED) + ' reject   ' +
          _c('s', _DIM) + ' skip   ' + _c('q', _YELLOW) + ' quit')


def _pick_or_create_role(raw_title: str) -> Role | None:
    """Prompt user to pick an existing role or create a new canonical one."""
    print()
    print('  Map to which role? Type part of a role title to search, or')
    print('  type  ' + _c('new: <Title>', _CYAN) + '  to create a new canonical role.')
    print('  Leave blank to cancel.')
    print()

    while True:
        try:
            inp = input('  > ').strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if not inp:
            return None

        if inp.lower().startswith('new:'):
            new_title = inp[4:].strip()
            if not new_title:
                print('  Please provide a title after "new:"')
                continue
            category = input(f'  Category for "{new_title}" (Engineering/Product/Design/Sales/Marketing/Operations/Finance/Legal/HR/Other): ').strip() or 'Other'
            job_family = input(f'  Job family (e.g. "Software Engineering"): ').strip() or new_title
            role = Role(
                normalized_title=new_title,
                category=category,
                job_family=job_family,
                total_active_jobs=0,
            )
            db.session.add(role)
            db.session.flush()
            print(_c(f'  Created new role: {new_title}', _GREEN))
            return role

        # Search existing roles
        results = Role.query.filter(
            Role.normalized_title.ilike(f'%{inp}%')
        ).order_by(Role.normalized_title).limit(10).all()

        if not results:
            print('  No roles found. Try a different search or use "new: <Title>"')
            continue

        print()
        for i, r in enumerate(results, 1):
            print(f'  {_c(i, _CYAN)}.  {r.normalized_title}  {_c(f"({r.category})", _DIM)}')
        print()

        try:
            choice = input('  Pick number (or blank to search again): ').strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if not choice:
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                return results[idx]
        except ValueError:
            pass
        print('  Invalid choice.')


def _run(min_count: int):
    candidates = UnmatchedTitle.query.filter_by(status='pending').filter(
        UnmatchedTitle.job_count >= min_count
    ).order_by(UnmatchedTitle.job_count.desc()).all()

    if not candidates:
        print(f'No pending role candidates with count >= {min_count}.')
        return

    total = len(candidates)
    print(f'\n{_c(total, _BOLD)} pending role candidates (min_count={min_count})')

    approved = rejected = skipped = 0

    for idx, candidate in enumerate(candidates, 1):
        _print_candidate(idx, total, candidate)

        while True:
            try:
                key = input('  > ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                key = 'q'

            if key == 'y':
                role = _pick_or_create_role(candidate.raw_title)
                if role is None:
                    print('  Cancelled — leaving as pending.')
                    skipped += 1
                    break

                # Add to RoleTitleVariation so normalizer picks it up going forward
                existing_var = RoleTitleVariation.query.filter_by(
                    original_title=candidate.raw_title
                ).first()
                if existing_var:
                    existing_var.role_id = role.id
                else:
                    db.session.add(RoleTitleVariation(
                        role_id=role.id,
                        original_title=candidate.raw_title,
                        frequency=candidate.job_count,
                    ))

                candidate.status = 'approved'
                candidate.mapped_role_id = role.id
                db.session.commit()
                print(_c(f'  ✓ Mapped "{candidate.raw_title}" → {role.normalized_title}', _GREEN))
                approved += 1
                break

            elif key == 'n':
                reason = input('  Reject reason (optional): ').strip() or 'manual_review'
                candidate.status = 'rejected'
                candidate.rejected_reason = reason
                db.session.commit()
                print(_c(f'  ✗ Rejected', _RED))
                rejected += 1
                break

            elif key == 's':
                skipped += 1
                break

            elif key == 'q':
                print(f'\nStopped. Approved: {approved}  Rejected: {rejected}  Skipped: {skipped}')
                return

            else:
                print('  Invalid key. Use y / n / s / q')

    print(f'\nDone. Approved: {_c(approved, _GREEN)}  Rejected: {_c(rejected, _RED)}  Skipped: {_c(skipped, _DIM)}')


def main():
    parser = argparse.ArgumentParser(description='Review unmatched role candidates')
    parser.add_argument('--min-count', type=int, default=1, help='Min job_count to show (default: 1)')
    args = parser.parse_args()

    with app.app_context():
        _run(min_count=args.min_count)


if __name__ == '__main__':
    main()
