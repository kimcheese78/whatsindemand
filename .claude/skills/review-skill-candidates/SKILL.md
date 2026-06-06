---
name: review-skill-candidates
description: Reviews pending skill candidates from the DB, classifies them (keep/drop + category/subcategory/aliases), verifies the decisions, and promotes approved skills. Use this whenever the user mentions reviewing skills, processing the skill queue, promoting new skills, triaging candidates, or running skill discovery — even casual phrasings like "what skills came up?", "anything new to add?", or "check the candidate queue". Replaces triage_skill_candidates.py + promote_shortlist.py with a single guided flow.
tools: Bash, Read
---

# review-skill-candidates

Classifies pending skill candidates directly — no manual JSON editing. Claude reasons through each candidate, self-verifies, shows you only the uncertain ones, then promotes on your confirm.

## Taxonomy

Subcategory must be one of these, matching the category:

```
technical:
  Programming Languages, Frontend & Web, Backend & APIs, Mobile,
  Databases & Data Engineering, Data Science & Analytics,
  AI & Machine Learning, Cloud & Infrastructure, DevOps & CI/CD,
  Security & Compliance, Hardware & Embedded, QA & Testing,
  Networking & Systems, Enterprise Tools & Platforms

domain:
  Industries, Business & Operations, Marketing & Growth,
  Sales & Customer Success, Finance & Accounting, People & HR,
  Legal & Compliance, Product & Design, Methodologies

soft:
  Communication, Leadership & Management, Collaboration & Teamwork,
  Problem Solving & Critical Thinking, Personal Effectiveness
```

## Workflow

### Step 1 — Pull candidates

```bash
cd backend && python3 - <<'EOF'
import os, json, sys
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway')
sys.path.insert(0, '.')
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    rows = db.session.execute(db.text("""
        SELECT id, name, job_count, company_count, example_contexts
        FROM skill_candidates
        WHERE status = 'pending' AND company_count >= 2
        ORDER BY company_count DESC, job_count DESC
        LIMIT 200
    """)).fetchall()
    out = [{'id': r[0], 'name': r[1], 'job_count': r[2],
            'company_count': r[3], 'contexts': list(r[4] or [])} for r in rows]
    print(json.dumps(out))
EOF
```

Also pull the verified taxonomy to spot near-duplicates:

```bash
cd backend && python3 - <<'EOF'
import os, json, sys
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway')
sys.path.insert(0, '.')
from app import create_app
from app.models import db, Skill
app = create_app()
with app.app_context():
    skills = db.session.execute(db.text("SELECT name, aliases FROM skills WHERE is_verified=true")).fetchall()
    names = []
    for s in skills:
        names.append(s[0])
        names.extend(s[1] or [])
    print(json.dumps(names))
EOF
```

If 0 pending candidates: tell the user "Nothing to review — run `discover_new_skills.py` first" and stop.

If the DB is unreachable, report the error and stop — don't guess at candidates.

### Step 2 — Classify

The goal is a taxonomy of concrete, learnable skills — things a recruiter could list in a job requirement and a candidate could claim on a resume. Anything that doesn't meet that bar should be dropped.

For each candidate, look at the **name** and **example_contexts** together:

**DROP** if any of these apply:
- Generic filler or adjective phrase ("best practices", "fast-paced environment", "strong background") — not learnable or measurable
- EEO / benefits language ("disability accommodation", "dental", "vacation") — these sneak in from JD boilerplate sections
- Verb phrase or sentence fragment ("building scalable systems", "working with data") — a skill should be a noun, not an activity
- Job title or level ("engineers", "data scientists", "senior") — describes a person, not a capability
- Company name used generically ("Google", "Salesforce") unless it's clearly a product or platform name
- Already covered by an existing taxonomy entry or alias — near-duplicates add noise, not signal
- Too vague to mean anything specific ("technology", "software", "systems")

**KEEP** and assign:
- `category`: technical / domain / soft
- `subcategory`: from the taxonomy above — must match the category
- `name`: clean canonical form ("React" not "using React.js or similar frameworks")
- `aliases`: only include genuinely common alternate forms — acronyms (Kubernetes → ["k8s"]), abbreviations (TypeScript → ["TS"]), or a widely-used variant name. Most candidates need 0–1 aliases. Don't pad to 3 for its own sake.

Work through all candidates. Produce just the decision list — no per-item narration needed.

### Step 3 — Self-verify

Before reporting, review your own decisions for these easy-to-make mistakes:
- Subcategory placed in the wrong category (e.g., "Leadership" filed under `technical`)
- Canonical name still has noise ("using" prefix, "or similar" suffix, trailing version numbers like "Python 3.x")
- Aliases that aren't genuine alternates (e.g., aliasing "Agile" to "Scrum" — related but distinct)
- KEEP decision where the example_contexts are boilerplate, not actual skill requirements
- Two candidates that are near-duplicates of each other — one should absorb the other as an alias

Flag anything uncertain as `FLAGGED: <one-line reason>`. Everything else is `CONFIRMED`.

### Step 4 — Report

Show this before touching the DB:

```
SKILL CANDIDATE REVIEW
======================
Reviewed: 147    Keeping: 89    Dropping: 51    Flagged: 7

FLAGGED — your call:
--------------------
"Operational Excellence"  [domain > Methodologies]  co=12 jobs=89
  ⚠ Very broad — could be noise or a real domain practice
    Example: "drive operational excellence across teams"

"LangGraph"  [technical > AI & Machine Learning]  co=4 jobs=11
  ⚠ Subset of LangChain ecosystem — add as alias to LangChain instead?

KEEPING (top 10 by company count):
------------------------------------
  Temporal           technical > Backend & APIs            co=34 jobs=201
  Databricks Unity   technical > Databases & Data Eng.     co=28 jobs=156
  SOAR               technical > Security & Compliance     co=21 jobs=98
  ...

DROPPING (sample):
------------------
  "tools like Burp Suite"   — name artifact, not a skill
  "fast-paced environment"  — adjective phrase
  ...
```

Ask: "Any changes to the flagged ones before I promote?"

### Step 5 — Apply

Once confirmed:

1. Write `backend/data/skill_shortlist.json`:

```json
{
  "meta": {"kept": N, "dropped": N, "failed": 0},
  "skills_by_category": {
    "technical": [
      {"candidate_id": 123, "name": "Temporal", "category": "technical",
       "subcategory": "Backend & APIs", "aliases": [], "company_count": 34, "job_count": 201}
    ],
    "domain": [...],
    "soft": [...]
  }
}
```

2. Promote to taxonomy and capture the first new skill ID:

```bash
cd backend && DATABASE_URL='postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway' \
  PYTHONPATH=. venv/bin/python scripts/promote_shortlist.py --apply 2>&1 | tee /tmp/promote_output.txt
grep "First new ID" /tmp/promote_output.txt
```

Parse the first new skill ID from the line `First new ID (for backfill): XXXX`. Store it as FIRST_ID.

If no "First new ID" line appears (0 skills were promoted), skip step 4 (backfill) — still run step 3 (extract).

3. Extract skills for new dirty jobs — covers all skills including newly promoted ones. Run extract BEFORE backfill because extract uses plain inserts with no conflict handling:

```bash
cd backend && DATABASE_URL='postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway' \
  PYTHONPATH=. venv/bin/python scripts/extract_skills.py 2>&1
```

4. Backfill newly promoted skills onto all historical jobs (uses ON CONFLICT DO NOTHING, safe to run after extract):

```bash
cd backend && DATABASE_URL='postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway' \
  PYTHONPATH=. venv/bin/python scripts/backfill_skills.py --min-id FIRST_ID 2>&1
```

Replace `FIRST_ID` with the actual ID parsed in step 2.

5. Mark dropped candidates rejected so they don't reappear in future runs:

```bash
cd backend && python3 - <<'EOF'
import os, sys, json
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway')
sys.path.insert(0, '.')
from app import create_app
from app.models import db
# Replace with the actual candidate IDs classified as DROP in Step 2
DROP_IDS = []  # e.g. [42, 107, 233, ...]
REASON = 'ai_triage_dropped'
app = create_app()
with app.app_context():
    if DROP_IDS:
        db.session.execute(db.text(
            "UPDATE skill_candidates SET status='rejected', rejected_reason=:r WHERE id = ANY(:ids)"
        ), {'r': REASON, 'ids': DROP_IDS})
        db.session.commit()
        print(f'Rejected {len(DROP_IDS)} candidates')
    else:
        print('No candidates to reject')
EOF
```

### Step 6 — Final report

```
Promoted:  89 skills to taxonomy (IDs XXXX–YYYY)
Rejected:  51 candidates (won't reappear in future runs)

By category:
  technical: 54  (Temporal, Databricks Unity Catalog, SOAR, ...)
  domain:    27  (Revenue Operations, Product-Led Growth, ...)
  soft:       8  (Conflict Resolution, ...)

Extraction: K dirty jobs tagged with updated taxonomy
Backfill:   M job_skills rows inserted for new skills on historical jobs

Next scrape candidates will appear after the Railway cron runs on Saturday.
```
