# WhatsInDemand

Job market intelligence platform — tracks skills demand and job trends across ~3,300 companies. Live at [whatsindemand.com](https://whatsindemand.com).

## Stack

- **Frontend:** React 19 + Tailwind CSS — deployed on Vercel
- **Backend:** Flask + SQLAlchemy (Python 3.13) — deployed on Railway
- **Database:** PostgreSQL on Railway

## Project structure

```
WhatsInDemand/
├── frontend/         # React app (src/, public/)
├── backend/
│   ├── app/
│   │   ├── routes/   # API endpoints
│   │   ├── scrapers/ # ATS-specific scrapers (Greenhouse, Lever, Ashby, ...)
│   │   ├── services/ # skill_extractor, etc.
│   │   ├── models.py
│   │   └── config.py
│   ├── scripts/      # weekly_scrape, discover_new_skills, extract_skills, ...
│   └── migrations/   # Alembic
├── CLAUDE.md         # Dev guide for working in this repo
└── README.md
```

## Pipeline

Jobs flow through four stages, orchestrated by `backend/scripts/weekly_scrape.py`:

1. **Scrape** — pull current job postings from each company's ATS
2. **Discover** — surface new skill candidates from JD requirements sections
3. **Review** — approve/reject candidates into the verified `Skill` taxonomy
4. **Extract** — tag jobs against the taxonomy → `job_skills`

Railway runs a weekly cron (`agent_run.py`) for Step 1. Steps 2–4 are run manually for now.

## Local development

### Prerequisites
- Python 3.13+
- Node.js 18+
- PostgreSQL (local) or access to the Railway prod DB

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env       # set DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY
flask db upgrade
python run.py              # http://localhost:5001
```

### Frontend

```bash
cd frontend
npm install
npm start                  # http://localhost:3000
```

## Environment variables

**Backend (.env):** `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`, `FRONTEND_URL`, `BACKEND_URL`. See `ENVIRONMENT_VARIABLES.md` for full list including Stripe and Google OAuth keys.

**Frontend:** `REACT_APP_API_URL` (set in Vercel project settings for prod; defaults to localhost in dev).

## Deployment

- **Backend:** push to `main` → Railway auto-deploys (`Procfile`: `gunicorn run:app`)
- **Frontend:** push to `main` → Vercel auto-deploys

## Contributing / working in this repo

See [`CLAUDE.md`](./CLAUDE.md) for repo conventions, the `DATABASE_URL` gotcha when running scripts against prod, the script catalogue, and how the skill taxonomy is structured.

## License

MIT
