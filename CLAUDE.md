# WhatsInDemand

Job market intelligence platform. Scrapes ATS-listed jobs from ~3,300 companies, extracts skills/roles/salaries, surfaces demand trends at whatsindemand.com.

## Stack
- **Backend:** Flask + SQLAlchemy, Postgres (Railway), gunicorn (`Procfile`)
- **Frontend:** React 19 + Tailwind, deployed on Vercel (`frontend/vercel.json`)
- **DB:** prod on Railway only (local DB exists but is not used)

## Repo layout
```
backend/
  app/
    config.py         # loads .env at import time
    models.py         # Skill, Job, Company, JobSkill, Role, DiscoveryRun, ...
    routes/           # API
    scrapers/         # ATS-specific scrapers (Greenhouse, Lever, Ashby, ...)
    services/
      skill_extractor.py    # parse_jd_sections, extract_requirements_text
  scripts/
    weekly_scrape.py        # full pipeline: scrape → discover → extract
    agent_run.py            # Railway weekly cron (scrape only — missing steps 2/3)
    discover_new_skills.py  # find candidate skills from JD requirements sections
    review_skill_candidates.py
    extract_skills.py       # one-pass extraction on new jobs
    reextract_all_skills.py # full re-extraction across all jobs
    backfill_skills.py      # retro-tag jobs for new skill IDs
    update_ai_taxonomy.py   # most recent taxonomy edit (template for similar scripts)
    enrich_companies.py     # enriches Company rows with location, founded_year, type, valuation, website, logo_url via Claude API
    _archive/               # one-shots (gitignored)
frontend/src/
  App.js                    # SkillsTab, RolesTab, dashboard
```

## Database

**Prod DSN** — get from Railway dashboard (Variables → DATABASE_URL). Do not commit credentials.

**Local DSN** is in `backend/.env` (loaded by `config.py` at import time).

### The DATABASE_URL gotcha
`config.py` calls `load_dotenv()` at import. If you import `app.create_app` without overriding `DATABASE_URL` first, the script will hit your **local** DB, not prod. Pattern that works:

```python
import os
PROD_DSN = 'postgresql://postgres:...@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)  # MUST come before app imports
from app import create_app
```

Or invoke with env in shell:
```bash
DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/foo.py
```

`config.py` rewrites `postgresql://` → `postgresql+psycopg://` for psycopg3 compatibility — pass DSNs in plain `postgresql://` form.

## Pipeline (fully automated)

One weekly Railway cron (`agent_run.py`, weekly-scrape service, Fridays) runs the entire pipeline end to end:

1. **Scrape** all `scrape_enabled=true` companies
2. **Discover** new skill candidates from JD requirements sections
3. **Triage skill candidates** via Anthropic API (`ai_triage_skills.py`, claude-sonnet-5) — promotes keeps, rejects drops
4. **Map unmatched titles** via Anthropic API (`ai_map_roles.py::run_pipeline`) — writes `role_title_variations`; the scraper consults that table before queueing unmatched titles, so mappings persist without repo write-back
5. **Extract** skills for all dirty jobs, then **backfill** skills promoted in the past 7 days across historical jobs, then rebuild `total_job_count`
6. **Email report** via Resend to ALERT_EMAIL (full stats for every step)

Needs on the weekly-scrape service: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `ALERT_EMAIL`. API cost ~$2-3/month.

History: review used to run in a claude.ai cloud routine (`trig_01JAW9jj5w3hQi9asFSAQQaL`, now disabled) to avoid API credits, but the cloud environment's egress policy blocks both the DB (raw TCP) and any non-allowlisted HTTPS domain, and it broke silently twice — consolidated 2026-07-16.

## Skill taxonomy

- `Skill.category` ∈ {`technical`, `domain`, `soft`} (plus NULL for legacy)
- `Skill.is_verified` controls whether extraction considers it (False = ignored)
- `Skill.aliases` is `ARRAY(String)` — extraction matches case-insensitively against name + aliases
- Industries (Healthcare, Manufacturing, Construction, etc.) live under `domain` — they're context, not learnable skills
- `total_job_count` is denormalized; rebuild via re-extraction, not manual UPDATEs

## Deploy

- **Backend:** push to `main` → Railway auto-deploys. Watch logs in Railway dashboard.
- **Frontend:** push to `main` → Vercel auto-deploys. If Vercel doesn't pick up a commit, push an empty commit: `git commit --allow-empty -m "trigger vercel redeploy"`.

## Commands

```bash
# Backend dev
cd backend && source venv/bin/activate && python run.py        # localhost:5001

# Frontend dev
cd frontend && npm start                                       # localhost:3000

# Run a script against prod
cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/<name>.py [--apply]
```

Most maintenance scripts follow the `--apply` convention: dry-run by default, `--apply` to commit.

## Conventions
- Maintenance scripts: dry-run default, `--apply` to write
- Migrations live in `backend/migrations/` (Alembic via Flask-Migrate)
- DB writes go through SQLAlchemy ORM, not raw SQL, except in one-shot scripts where ORM overhead matters
- New scripts go in `backend/scripts/`; one-shots get archived to `_archive/` once consumed
