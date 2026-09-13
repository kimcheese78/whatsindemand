"""Seed Skill.ai_lens for the curated 'control-AI' skill grouping.

Groups the scattered skills that mean "working with / directing AI" ('use') and
"overseeing / governing AI" ('govern') so the market-wide AI-skills board can
query them as a set. Orthogonal to category/subcategory (those are untouched).

Non-destructive & idempotent: sets the lens on the listed skills only. Skills
tagged elsewhere (e.g. via the skill-review flow) but not listed here are
reported as drift, never cleared.

Run:
  cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/seed_ai_lens.py
  cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/seed_ai_lens.py --apply
"""
import os
import sys

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set (prod DSN). See CLAUDE.md.')

from app import create_app
from app.models import db, Skill

APPLY = '--apply' in sys.argv

# Using & directing AI — using AI tools day-to-day, and building/orchestrating on
# top of models. Excludes generic umbrella terms (Artificial Intelligence, ML,
# LLMs, Generative AI) and build-infra (PyTorch, MLOps, fine-tuning, …).
USE = [
    'AI Fluency', 'Prompt Engineering', 'AI-assisted development', 'AI coding assistants',
    'Cursor', 'Claude Code', 'Claude', 'Microsoft Copilot', 'GPT', 'OpenAI', 'Gemini',
    'AI agents', 'RAG', 'MCP', 'Function Calling', 'LLM orchestration', 'LLM integration',
    'Agentic System Orchestration',
]
# Governing AI — oversight, security, strategy, compliance. Excludes
# Human-in-the-Loop and AI safety (boilerplate-contaminated; see design spec).
GOVERN = [
    'AI Security', 'AI Strategy', 'Responsible AI', 'AI Compliance',
]

DESIRED = {name: 'use' for name in USE}
DESIRED.update({name: 'govern' for name in GOVERN})


def main():
    app = create_app()
    with app.app_context():
        print(f'=== Seeding ai_lens ({len(DESIRED)} skills) ===\n')
        set_count = missing = 0
        for name, lens in DESIRED.items():
            s = Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first()
            if not s:
                print(f'  MISSING: {name!r} — no matching skill')
                missing += 1
                continue
            if s.ai_lens == lens:
                print(f'  ok      [{s.id}] {s.name}: already {lens!r}')
                continue
            print(f'  SET     [{s.id}] {s.name}: {s.ai_lens!r} -> {lens!r}')
            if APPLY:
                s.ai_lens = lens
            set_count += 1

        # Drift report — tagged elsewhere but not in this list (never cleared).
        desired_lower = {n.lower() for n in DESIRED}
        drift = [s for s in Skill.query.filter(Skill.ai_lens.isnot(None)).all()
                 if s.name.lower() not in desired_lower]
        if drift:
            print('\n  Tagged but not in this seed list (left as-is):')
            for s in drift:
                print(f'    [{s.id}] {s.name}: ai_lens={s.ai_lens!r}')

        print(f'\n  {set_count} to set, {missing} missing.')
        if APPLY:
            db.session.commit()
            print('  ✓ Committed.')
        else:
            print('  Dry-run. Pass --apply to write.')


if __name__ == '__main__':
    main()
