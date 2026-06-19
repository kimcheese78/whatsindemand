---
name: map-and-verify-roles
description: Maps unmatched job titles to canonical roles. Claude does the classification directly — no API credits needed. Use whenever the user mentions role mapping, unmatched titles, job title classification, or the role queue — including casual phrasings like "what titles still need roles?", "check the role decisions", "any unmatched titles?", or "map and verify".
tools: Bash, Read
---

# map-and-verify-roles

Claude classifies unmatched titles directly — no Anthropic API call. The
output is written to the checkpoint file, then applied with `--apply`.

## Canonical roles reference

Pull the full canonical role list before classifying:

```bash
python3 - <<'EOF'
import os, json, sys
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway')
sys.path.insert(0, '.')
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    rows = db.session.execute(db.text(
        "SELECT id, normalized_title, category, job_family FROM roles ORDER BY category, normalized_title"
    )).fetchall()
    print(json.dumps([{'id':r[0],'title':r[1],'category':r[2],'job_family':r[3]} for r in rows]))
EOF
```

## Workflow

### Step 1 — Check queue

```bash
python3 - <<'EOF'
import os, sys
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway')
sys.path.insert(0, '.')
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    pending = db.session.execute(db.text(
        "SELECT COUNT(*) FROM unmatched_titles WHERE status='pending'"
    )).scalar()
    print(f"Pending unmatched titles: {pending:,}")
    rows = db.session.execute(db.text("""
        SELECT raw_title, job_count FROM unmatched_titles
        WHERE status='pending' ORDER BY job_count DESC LIMIT 10
    """)).fetchall()
    for r in rows:
        print(f"  {r[1]:>5}  {r[0]}")
EOF
```

If 0 pending: tell the user "Queue is empty — nothing to map." and stop.

### Step 2 — Pull titles for classification

Fetch in job_count order with JD snippets:

```bash
python3 - <<'EOF'
import os, json, sys
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway')
sys.path.insert(0, '.')
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    rows = db.session.execute(db.text("""
        SELECT ut.id, ut.raw_title, ut.job_count,
               LEFT(COALESCE(j.requirements_text, j.description_text, ''), 300) as jd,
               COALESCE(j.department, '') as dept
        FROM unmatched_titles ut
        LEFT JOIN LATERAL (
            SELECT requirements_text, description_text, department
            FROM jobs WHERE title = ut.raw_title
              AND description_text IS NOT NULL LIMIT 1
        ) j ON true
        WHERE ut.status = 'pending'
        ORDER BY ut.job_count DESC
        LIMIT 300
    """)).fetchall()
    out = [{'id':r[0],'raw_title':r[1],'job_count':r[2],'jd':r[3] or '','dept':r[4]} for r in rows]
    print(json.dumps(out))
EOF
```

### Step 3 — Classify

Work through every title. For each, look at the raw_title + jd + dept together.

**MAP** — assign to an existing canonical role:
- Use role's exact `normalized_title` as the `role` field
- Title is clearly a variant, level, or domain specialisation of that role
- Seniority modifiers (Senior/Lead/Principal/Director of) are fine — the
  normalizer strips them. "Director of Engineering" → Engineering Manager ✓
- Domain qualifiers are fine — "QA Engineer, Healthcare" → QA Engineer ✓

**NEW_ROLE** — flag as a new canonical role if:
- A real, distinct job function with consistent responsibilities
- Appears across multiple employers (job_count reflects this)
- Not a specialisation of an existing role that the normalizer already handles
- Set `suggested_title` (clean canonical form), `category`, `job_family`

**REJECT** — mark as noise if:
- Non-English title
- Intern, volunteer, apprentice, fellowship, program
- Open/general application, "don't see a role", talent pool
- Too vague or company-specific to be a canonical role
- Physical requirement, benefit, or JD boilerplate masquerading as a title

### Step 4 — Write decisions and report

Write all decisions to `backend/data/ai_role_decisions.json`:

```python
import json
decisions = [
    # MAP example:
    {"raw_title": "Senior Automation QA", "action": "map",
     "role": "QA Engineer", "job_count": 18, "jobs": 18},
    # NEW_ROLE example:
    {"raw_title": "Industrial Hygienist", "action": "new_role",
     "suggested_title": "Industrial Hygienist", "category": "Operations",
     "job_family": "EHS", "job_count": 27, "jobs": 27},
    # REJECT example:
    {"raw_title": "Repartidor de Tarjetas", "action": "reject",
     "reason": "non-english", "job_count": 36},
]
with open('backend/data/ai_role_decisions.json', 'w') as f:
    json.dump({"decisions": decisions}, f, indent=2)
```

Then report:

```
ROLE MAPPING SUMMARY
====================
Reviewed: N    Map: X    New role: Y    Reject: Z

FLAGGED — your call:
--------------------
"VP of Data Science" → Data Science Manager  [jobs=45]
  ⚠ VP seniority — leadership role but no VP-level canonical exists

NEW ROLES proposed:
-------------------
  "Revenue Operations Analyst"  [Sales / Sales Operations]  jobs=23

TOP MAPS (sample):
------------------
  "Director of FP&A"            → Finance Manager          jobs=14
  "DevSecOps"                   → DevOps Engineer          jobs=13
  ...

REJECTS (sample):
-----------------
  "Repartidor de Tarjetas"      non-english
  "Summer Associate 2027"       intern/program
```

Ask: any corrections to the flagged ones before applying?

### Step 5 — Apply

```bash
DATABASE_URL='postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway' \
  PYTHONPATH=. venv/bin/python scripts/ai_map_roles.py --apply 2>&1
```

After apply, also bulk-reject all remaining pending unmatched_titles that
weren't in the decisions (titles with very low job_count not worth mapping):

```bash
python3 - <<'EOF'
import os, sys
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway')
sys.path.insert(0, '.')
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    result = db.session.execute(db.text(
        "UPDATE unmatched_titles SET status='rejected', rejected_reason='ai_triage_dropped'"
        " WHERE status='pending'"
    ))
    db.session.commit()
    print(f"Rejected {result.rowcount:,} remaining pending titles")
EOF
```

Report: jobs updated, variations created, roles created, aliases written.
