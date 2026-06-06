# WhatsInDemand — Product Context for Feature Planning

**What it is**: A job market intelligence platform for professionals to explore career paths, understand skill demand, and identify skill gaps. Live at whatsindemand.com.

---

## Current Data (as of May 2026)
- **110,905 active job postings** from **3,341 companies**
- **4,624 skills** tracked (technical, soft, domain)
- **311 canonical roles** across 17 categories
- **2.87M job↔skill associations**
- ATS coverage: Greenhouse (3,248), Ashby (71), Lever (22)

---

## Core User Flow
1. User picks a target role (e.g. "Software Engineer")
2. Uploads resume or manually enters current skills
3. Sees: job count trends, salary ranges by seniority, top in-demand skills, companies hiring, and a **skill gap analysis** (what they're missing vs. what the role requires)

---

## What's Working Well
- Role taxonomy: 311 canonical roles, 88.5% of jobs matched to a role
- Skill extraction from job descriptions (2.87M associations)
- Salary data, seniority breakdowns, company profiles
- Resume parsing → skill extraction → gap analysis
- Role trend data (monthly job count growth %)

---

## Known Data Gaps / Limitations
- **Soft skills underrepresented**: Leadership, Mentoring, Communication etc. were never backfilled — currently running a fix (ETA ~4 hrs)
- **ATS coverage**: Only Greenhouse/Ashby/Lever. Workday, iCIMS, Rippling etc. not covered — limits company diversity
- **Company coverage**: 3,341 companies, mostly tech-forward (Greenhouse-heavy). Underrepresented: manufacturing, retail, healthcare, government
- **Skill matching**: Word-boundary regex — misses multi-word contextual skills, synonyms without aliases
- **No location filtering on skill demand**: Can't yet see "Python demand in NYC vs. Austin"
- **Real Estate category**: 5 roles, very few jobs — thin coverage

---

## Tech Stack
- **Frontend**: React 19 + Tailwind + Recharts (Vercel)
- **Backend**: Flask + SQLAlchemy (Railway)
- **Database**: PostgreSQL — 3.5GB
- **NLP**: spaCy + regex skill extraction, BeautifulSoup HTML parsing

---

## Current Feature Set
| Feature | Status |
|---|---|
| Role explorer (trends, salary, skills, companies) | ✅ Live |
| Skill gap analysis (resume vs. role) | ✅ Live |
| Company profiles | ✅ Live |
| Skills directory | ✅ Live |
| User accounts + resume storage | ✅ Live |
| Email verification + password reset | ✅ Live |
| Pro tier (Stripe) | ✅ Live |
| Location-based filtering | ⚠️ Partial |
| Mobile experience | ❓ Unknown |

---

## Architecture Notes
- Frontend is a **184KB single React component** (App.js) — split into pages/components is overdue
- No caching layer — all queries hit Postgres directly
- Scraping runs per-company on a schedule; no real-time updates

---

## Role Categories (311 total)
| Category | Roles |
|---|---|
| Engineering | 59 |
| Healthcare | 47 |
| Operations | 44 |
| Sales | 27 |
| Retail / Hospitality | 19 |
| Finance | 19 |
| People | 17 |
| Marketing | 15 |
| Legal | 12 |
| Customer Success | 12 |
| Design | 11 |
| Data Science | 7 |
| Product | 7 |
| Real Estate | 5 |
| IT | 5 |
| Partnerships | 3 |
| Education | 2 |
