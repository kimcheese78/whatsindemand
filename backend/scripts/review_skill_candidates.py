"""Interactive CLI to review pending skill candidates and promote or reject them.

Usage:
    PYTHONPATH=. venv/bin/python scripts/review_skill_candidates.py
    PYTHONPATH=. venv/bin/python scripts/review_skill_candidates.py --min-jobs 5
    PYTHONPATH=. venv/bin/python scripts/review_skill_candidates.py --llm   # advisory LLM hints

Keys:
    y  — approve (promote to skills table + backfill job_skills)
    n  — reject (mark rejected, skip in future discovery runs)
    s  — skip (leave pending, review later)
    q  — quit (save all decisions so far)
"""
import os
import sys
import argparse
from datetime import datetime

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Skill, SkillCandidate

app = create_app()

# Re-use helpers from discover_new_skills without re-importing the whole module at top-level
# (they reference app-context models, so import inside app context)


# ---------------------------------------------------------------------------
# LLM advisory (optional)
# ---------------------------------------------------------------------------
def _llm_hint(names: list[str]) -> dict[str, bool]:
    """Return {name: bool} — True means LLM thinks it's a legit skill."""
    import anthropic

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY not set')

    client = anthropic.Anthropic(api_key=api_key)
    name_list = '\n'.join(f'- {n}' for n in names)
    prompt = (
        'You are evaluating whether phrases extracted from job descriptions are real, '
        'discrete technical or professional skills worth adding to a skills taxonomy.\n\n'
        'For each phrase, reply with exactly "YES" or "NO".\n\n'
        f'Phrases:\n{name_list}\n\n'
        'Reply format — one line per phrase, same order:\n'
        '<phrase>: YES|NO'
    )
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=512,
        messages=[{'role': 'user', 'content': prompt}],
    )
    result = {}
    for line in msg.content[0].text.strip().splitlines():
        if ':' not in line:
            continue
        phrase, verdict = line.rsplit(':', 1)
        result[phrase.strip().strip('-').strip()] = verdict.strip().upper() == 'YES'
    return result


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
_RESET  = '\033[0m'
_BOLD   = '\033[1m'
_GREEN  = '\033[32m'
_RED    = '\033[31m'
_YELLOW = '\033[33m'
_CYAN   = '\033[36m'
_DIM    = '\033[2m'


def _c(text, *codes):
    return ''.join(codes) + str(text) + _RESET


def _print_candidate(idx: int, total: int, candidate, llm_hints: dict | None):
    print()
    print(_c('─' * 60, _DIM))
    print(
        _c(f'[{idx}/{total}]', _DIM) + '  ' +
        _c(candidate.name, _BOLD) +
        f'   jobs: {_c(candidate.job_count, _CYAN)}  companies: {_c(candidate.company_count, _CYAN)}'
    )

    if candidate.first_seen or candidate.last_seen:
        print(_c(f'  first seen: {candidate.first_seen}   last seen: {candidate.last_seen}', _DIM))

    if candidate.methods:
        print(_c(f'  methods: {", ".join(candidate.methods)}', _DIM))

    if candidate.example_contexts:
        print(_c('  examples:', _DIM))
        for ctx in candidate.example_contexts:
            print(_c(f'    • {ctx}', _DIM))

    if llm_hints is not None:
        verdict = llm_hints.get(candidate.name)
        if verdict is True:
            print(_c('  LLM hint: ✓ looks like a real skill', _GREEN))
        elif verdict is False:
            print(_c('  LLM hint: ✗ probably not a skill', _RED))
        else:
            print(_c('  LLM hint: ? (not evaluated)', _DIM))

    print()
    print(_c('  y', _GREEN) + ' approve   ' + _c('n', _RED) + ' reject   ' + _c('s', _DIM) + ' skip   ' + _c('q', _YELLOW) + ' quit')


# ---------------------------------------------------------------------------
# Core review loop
# ---------------------------------------------------------------------------
def _build_taxonomy_set() -> set:
    skills = Skill.query.all()
    s = set()
    for sk in skills:
        s.add(sk.name.lower())
        for alias in sk.aliases or []:
            s.add(alias.lower())
    return s


def _run(min_jobs: int, min_companies: int, use_llm: bool, batch_size: int):
    # Import promote helper from discover_new_skills
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from discover_new_skills import _promote_candidate

    # Get pending candidates sorted by signal strength
    rows = db.session.execute(db.text(
        """
        SELECT sc.id
        FROM skill_candidates sc
        WHERE sc.status = 'pending'
          AND sc.job_count >= :min_jobs
          AND sc.company_count >= :min_cos
        ORDER BY sc.job_count DESC, sc.company_count DESC
        """
    ), {'min_jobs': min_jobs, 'min_cos': min_companies}).fetchall()

    if not rows:
        print(f'No pending candidates with job_count >= {min_jobs} and company_count >= {min_companies}.')
        return

    candidate_ids = [r[0] for r in rows]
    total = len(candidate_ids)
    print(f'\n{_c(total, _BOLD)} pending candidates to review (min_jobs={min_jobs}, min_companies={min_companies})')

    # Optional: fetch LLM hints for the whole batch upfront
    llm_hints: dict | None = None
    if use_llm:
        candidates_for_llm = SkillCandidate.query.filter(
            SkillCandidate.id.in_(candidate_ids[:batch_size])
        ).all()
        names = [c.name for c in candidates_for_llm]
        print(f'Fetching LLM hints for {len(names)} candidates...')
        try:
            llm_hints = _llm_hint(names)
            print(_c(f'Got hints for {len(llm_hints)} candidates', _DIM))
        except RuntimeError as e:
            print(_c(f'LLM unavailable ({e}) — continuing without hints', _YELLOW))
            llm_hints = None

    taxonomy_set = _build_taxonomy_set()

    approved = rejected = skipped = 0

    for idx, cid in enumerate(candidate_ids, 1):
        candidate = SkillCandidate.query.get(cid)
        if not candidate or candidate.status != 'pending':
            continue

        _print_candidate(idx, total, candidate, llm_hints)

        while True:
            try:
                key = input('  > ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                key = 'q'

            if key == 'y':
                if _promote_candidate(candidate, taxonomy_set):
                    db.session.commit()
                    print(_c(f'  ✓ Promoted "{candidate.name}"', _GREEN))
                    approved += 1
                else:
                    print(_c(f'  Already in taxonomy — marked rejected', _YELLOW))
                    db.session.commit()
                    rejected += 1
                break
            elif key == 'n':
                reason = input('  Reject reason (optional): ').strip() or 'manual_review'
                candidate.status = 'rejected'
                candidate.rejected_reason = reason
                db.session.commit()
                print(_c(f'  ✗ Rejected "{candidate.name}"', _RED))
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Review pending skill candidates')
    parser.add_argument('--min-jobs',      type=int, default=3,  help='Minimum job_count to show (default: 3)')
    parser.add_argument('--min-companies', type=int, default=2,  help='Minimum company_count to show (default: 2)')
    parser.add_argument('--llm',           action='store_true',  help='Fetch advisory LLM hints before review')
    parser.add_argument('--batch',         type=int, default=50, help='Max candidates to fetch LLM hints for (default: 50)')
    args = parser.parse_args()

    with app.app_context():
        _run(
            min_jobs=args.min_jobs,
            min_companies=args.min_companies,
            use_llm=args.llm,
            batch_size=args.batch,
        )


if __name__ == '__main__':
    main()
