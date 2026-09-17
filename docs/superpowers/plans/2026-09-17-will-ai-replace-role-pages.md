# "Will AI replace [role]?" Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship server-rendered "Will AI replace [role]?" pages — one per indexable role plus 3 hand-written flagships — that answer the question from WhatsInDemand's live hiring data (and, when mapped, official BLS projections), to win AI-answer citations and long-tail rankings for the "Will AI replace ___" query family.

**Architecture:** New Flask blueprint `routes/ai_outlook.py` serves `/ai/` and `/ai/will-ai-replace-<slug>`, mirroring the existing `/r/` SSR pages. All decision logic (the verdict, BLS lookup, divergence detection) and all HTML building live as **pure functions** in `services/ai_verdict.py` and `services/ai_render.py` — unit-tested with no DB, exactly like `services/data_quality.py`. The route is a thin composer: fetch aggregates via the existing `_role_page_data` (DB), call the pure functions, return HTML. BLS data is a static JSON keyed by occupation code; a one-time script maps roles to codes.

**Tech Stack:** Python 3.13, Flask, SQLAlchemy, Alembic (Flask-Migrate), pytest 8.3.3. Frontend routing via Vercel rewrites. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-17-will-ai-replace-role-pages-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **Thin-content gate:** `MIN_JOBS_FOR_PAGE = 30` (from `app/routes/public.py`). Roles with fewer active postings render with `<meta name="robots" content="noindex">` and are excluded from the sitemap.
- **Canonical host:** `WEB_URL = 'https://www.whatsindemand.com'` (from `app/routes/_web.py`). One canonical URL per page.
- **Cache header:** reuse `CACHE_HEADER` from `_web.py` on all responses.
- **Data lens (verbatim in copy):** always describe our data as "the roughly 3,300 fast-growing companies we track", NEVER as "the labor market" or "all jobs".
- **Voice (hard requirement):** plain, human sentences a middle-schooler reads easily. No jargon. No buzzwords. No invented or coined words. Explain every number in words (e.g. "up 15% by 2034", not "+15% CAGR"). Applies to every rendered string — verdict lines, section intros, flagship prose. Read it aloud; if you would not say it, cut it.
- **Schema:** `BreadcrumbList` + `Article` JSON-LD only. Do NOT add `FAQPage` (Google retired FAQ rich results May 2026).
- **Verdicts are never absolute:** always sourced, always paired with the live number, never a bare "No".
- **Scripts:** dry-run by default, `--apply` to write (repo convention).
- **DB access:** through SQLAlchemy ORM (these are read-only aggregate queries).

---

## Task 0: Feature branch

**Files:** none (git only)

- [ ] **Step 1: Create and switch to a feature branch**

Run:
```bash
cd /Users/henry_c/WhatsInDemand
git checkout -b feat/will-ai-replace-pages
```
Expected: "Switched to a new branch 'feat/will-ai-replace-pages'".

- [ ] **Step 2: Commit the spec and this plan (they are currently untracked)**

```bash
git add docs/superpowers/specs/2026-09-17-will-ai-replace-role-pages-design.md \
        docs/superpowers/plans/2026-09-17-will-ai-replace-role-pages.md
git commit -m "docs: spec + plan for Will-AI-replace pages"
```

---

## Task 1: Verdict logic (pure, TDD)

The heart of the feature: given a role's numbers, decide the honest answer. No DB, no Flask. Unit-tested like `tests/market/test_data_quality.py`.

**Files:**
- Create: `backend/app/services/ai_verdict.py`
- Test: `backend/tests/ai_outlook/__init__.py` (empty), `backend/tests/ai_outlook/test_verdict.py`

**Interfaces:**
- Produces:
  - `LENS_PHRASE: str` = `"the roughly 3,300 fast-growing companies we track"`
  - `GROW_FLOOR = 5.0`, `FLAT_FLOOR = -2.0` (BLS % thresholds)
  - `decide_verdict(*, role_plural: str, ai_pct: int, total: int, bls_pct: float | None, bls_period: str | None = None) -> dict` returning keys:
    `stance` (`"no"|"unlikely"|"contested"|"adoption_only"`), `diverges` (bool),
    `headline` (str), `detail` (str).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/ai_outlook/__init__.py` (empty file), then `backend/tests/ai_outlook/test_verdict.py`:

```python
from app.services.ai_verdict import decide_verdict, LENS_PHRASE


def test_growing_when_bls_strongly_positive():
    v = decide_verdict(role_plural="software engineers", ai_pct=34,
                       total=17151, bls_pct=15.0, bls_period="2024 to 2034")
    assert v["stance"] == "no"
    assert v["diverges"] is False
    assert "aren't being replaced" in v["headline"].lower() or "not being replaced" in v["headline"].lower()
    assert "15%" in v["detail"]
    assert "34%" in v["detail"]
    assert LENS_PHRASE in v["detail"]


def test_flat_when_bls_near_zero():
    v = decide_verdict(role_plural="accountants", ai_pct=20,
                       total=472, bls_pct=1.0, bls_period="2024 to 2034")
    assert v["stance"] == "unlikely"
    assert v["diverges"] is False
    assert "20%" in v["detail"]


def test_contested_when_bls_declines_but_still_hiring():
    v = decide_verdict(role_plural="paralegals", ai_pct=12,
                       total=310, bls_pct=-8.0, bls_period="2024 to 2034")
    assert v["stance"] == "contested"
    assert v["diverges"] is True
    # Two-horizon: names both the decline and the live openings, plainly.
    assert "8%" in v["detail"]
    assert "310" in v["detail"]
    assert "both be true" in v["detail"].lower()


def test_adoption_only_when_bls_unmapped():
    v = decide_verdict(role_plural="prompt engineers", ai_pct=61,
                       total=140, bls_pct=None)
    assert v["stance"] == "adoption_only"
    assert v["diverges"] is False
    assert "61%" in v["detail"]
    assert LENS_PHRASE in v["detail"]
    # No fabricated projection when we don't have one.
    assert "project" not in v["headline"].lower()


def test_numbers_are_plain_no_jargon():
    v = decide_verdict(role_plural="data scientists", ai_pct=45,
                       total=820, bls_pct=36.0, bls_period="2024 to 2034")
    for text in (v["headline"], v["detail"]):
        low = text.lower()
        for banned in ("cagr", "augmentation", "leverage", "synerg", "utilize"):
            assert banned not in low
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && venv/bin/python -m pytest tests/ai_outlook/test_verdict.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ai_verdict'`.

- [ ] **Step 3: Write the minimal implementation**

Create `backend/app/services/ai_verdict.py`:

```python
"""Pure decision logic for the 'Will AI replace [role]?' pages.

No Flask, no DB — given a role's numbers, return an honest, plain-language
verdict. Unit-tested in tests/ai_outlook/test_verdict.py.
"""

LENS_PHRASE = "the roughly 3,300 fast-growing companies we track"

GROW_FLOOR = 5.0   # BLS 10-yr % change at/above this => job is growing
FLAT_FLOOR = -2.0  # between FLAT_FLOOR and GROW_FLOOR => roughly steady


def _ai_clause(role_plural: str, ai_pct: int) -> str:
    """One plain sentence about how many current openings ask for AI skills."""
    if ai_pct <= 0:
        return (f"Across {LENS_PHRASE}, almost no current {role_plural} openings "
                f"ask for AI skills yet.")
    return (f"Across {LENS_PHRASE}, {ai_pct}% of current {role_plural} openings "
            f"now ask for AI skills.")


def decide_verdict(*, role_plural, ai_pct, total, bls_pct, bls_period=None):
    role_plural = role_plural.strip()

    if bls_pct is None:
        return {
            "stance": "adoption_only",
            "diverges": False,
            "headline": (f"Not yet — employers aren't cutting {role_plural}. "
                         f"They're asking them to use AI."),
            "detail": (f"There are {total:,} live {role_plural} openings right now. "
                       + _ai_clause(role_plural, ai_pct)
                       + " The work is changing, not going away."),
        }

    if bls_pct >= GROW_FLOOR:
        return {
            "stance": "no",
            "diverges": False,
            "headline": (f"No — {role_plural} aren't being replaced. The government "
                         f"expects this job to grow, and companies are still hiring."),
            "detail": (f"Official projections put {role_plural} employment up "
                       f"{bls_pct:.0f}% by {_period_tail(bls_period)}. "
                       + _ai_clause(role_plural, ai_pct)
                       + " The work is changing, not disappearing."),
        }

    if bls_pct >= FLAT_FLOOR:
        return {
            "stance": "unlikely",
            "diverges": False,
            "headline": (f"Probably not soon. The number of {role_plural} looks "
                         f"steady, but AI is taking over some of the day-to-day tasks."),
            "detail": (f"Official projections expect {role_plural} employment to stay "
                       f"about the same through {_period_tail(bls_period)}. "
                       + _ai_clause(role_plural, ai_pct)),
        }

    # bls_pct < FLAT_FLOOR: official decline, but the role is still being hired now.
    return {
        "stance": "contested",
        "diverges": True,
        "headline": (f"It's mixed. Official forecasts point down, but right now "
                     f"companies are still hiring {role_plural}."),
        "detail": (f"The government projects {role_plural} employment to fall "
                   f"{abs(bls_pct):.0f}% by {_period_tail(bls_period)}. Yet there are "
                   f"{total:,} live {role_plural} openings across {LENS_PHRASE}. "
                   + _ai_clause(role_plural, ai_pct)
                   + " Strong demand today and a long-term squeeze can both be true."),
    }


def _period_tail(bls_period):
    """Turn '2024 to 2034' into '2034'; fall back to the raw value."""
    if not bls_period:
        return "the next ten years"
    return bls_period.split()[-1]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && venv/bin/python -m pytest tests/ai_outlook/test_verdict.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_verdict.py backend/tests/ai_outlook/
git commit -m "feat: pure verdict logic for Will-AI-replace pages"
```

---

## Task 2: BLS projection table (static JSON + pure lookup, TDD)

BLS Employment Projections change ~yearly, so we bundle them as static data keyed by occupation code (SOC). This task builds the lookup; Task 5 fills real numbers.

**Files:**
- Create: `backend/app/data/bls_projections.json`
- Modify: `backend/app/services/ai_verdict.py` (add `bls_for`)
- Test: `backend/tests/ai_outlook/test_bls.py`

**Interfaces:**
- Produces: `bls_for(soc_code: str | None, table: dict | None = None) -> dict | None` returning `{"pct": float, "period": str, "employment_base": int}` or `None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai_outlook/test_bls.py`:

```python
from app.services.ai_verdict import bls_for


SAMPLE = {
    "15-1252": {"pct": 15.0, "period": "2024 to 2034", "employment_base": 1692100},
}


def test_returns_record_for_known_code():
    rec = bls_for("15-1252", table=SAMPLE)
    assert rec["pct"] == 15.0
    assert rec["period"] == "2024 to 2034"


def test_returns_none_for_unknown_code():
    assert bls_for("99-9999", table=SAMPLE) is None


def test_returns_none_for_missing_code():
    assert bls_for(None, table=SAMPLE) is None


def test_default_table_loads_from_json():
    # Should not raise; the shipped JSON must be valid and a dict.
    result = bls_for("does-not-exist")
    assert result is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/ai_outlook/test_bls.py -v`
Expected: FAIL — `ImportError: cannot import name 'bls_for'`.

- [ ] **Step 3: Create the JSON and implement the lookup**

Create `backend/app/data/bls_projections.json` (seed with the 3 flagship occupations; Task 5 adds the rest):

```json
{
  "15-1252": {"pct": 15.0, "period": "2024 to 2034", "employment_base": 1692100},
  "15-2051": {"pct": 34.0, "period": "2024 to 2034", "employment_base": 202900},
  "13-2011": {"pct": 5.0, "period": "2024 to 2034", "employment_base": 1616500}
}
```

> Note: these three are Software Developers (15-1252), Data Scientists (15-2051), Accountants and Auditors (13-2011). Verify the exact percentages against the current BLS Employment Projections release in Task 5 before relying on them; they are seeded here so the pipeline works end to end.

Add to `backend/app/services/ai_verdict.py`:

```python
import json
import os

_BLS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bls_projections.json")
_BLS_TABLE = None


def _load_bls_table():
    global _BLS_TABLE
    if _BLS_TABLE is None:
        with open(_BLS_PATH, encoding="utf-8") as f:
            _BLS_TABLE = json.load(f)
    return _BLS_TABLE


def bls_for(soc_code, table=None):
    if not soc_code:
        return None
    if table is None:
        table = _load_bls_table()
    return table.get(soc_code)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/ai_outlook/ -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_verdict.py backend/app/data/bls_projections.json backend/tests/ai_outlook/test_bls.py
git commit -m "feat: static BLS projection table + lookup"
```

---

## Task 3: Page HTML rendering (pure, TDD)

All HTML building is pure — takes plain dicts, returns a string. Unit-tested for the things that matter (noindex gate, canonical, verdict text, schema, lens phrase). Mirrors `tests/blog/test_web.py`.

**Files:**
- Create: `backend/app/services/ai_render.py`
- Test: `backend/tests/ai_outlook/test_render.py`

**Interfaces:**
- Consumes: `decide_verdict` output; `_role_page_data` output shape (`total`, `company_count`, `skills` [{name, subcategory, pct}], `companies` [{name, count}], `ai_pct`, `remote_pct`).
- Produces:
  - `render_role_outlook_page(*, role_singular, role_plural, slug, month, data, verdict, bls, related, min_jobs, flagship_html=None) -> str`
  - `render_outlook_index(*, items) -> str` where `items` is a list of `(role_plural, slug, total)`
  - `ai_sitemap_urls(rows, today) -> list[str]` where `rows` is a list of `(slug,)` or objects with `.slug`; keep it a list of `(slug, lastmod)` tuples — see signature in code.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/ai_outlook/test_render.py`:

```python
from app.services.ai_verdict import decide_verdict, LENS_PHRASE
from app.services.ai_render import (
    render_role_outlook_page, render_outlook_index, ai_sitemap_urls,
)

DATA = {
    "total": 17151, "company_count": 1200, "ai_pct": 34, "remote_pct": 28,
    "skills": [
        {"name": "Python", "subcategory": "Programming Languages", "pct": 61},
        {"name": "LLMs", "subcategory": "AI & Machine Learning", "pct": 22},
    ],
    "companies": [{"name": "Stripe", "count": 40}, {"name": "Datadog", "count": 33}],
}


def _page(total=17151, bls=None, flagship=None):
    data = dict(DATA, total=total)
    verdict = decide_verdict(role_plural="software engineers", ai_pct=data["ai_pct"],
                             total=total, bls_pct=(bls or {}).get("pct"),
                             bls_period=(bls or {}).get("period"))
    return render_role_outlook_page(
        role_singular="Software Engineer", role_plural="software engineers",
        slug="software-engineer", month="September 2026", data=data,
        verdict=verdict, bls=bls, related=[("Data Scientist", "data-scientist")],
        min_jobs=30, flagship_html=flagship,
    )


def test_page_has_h1_and_canonical():
    html = _page()
    assert "<h1>Will AI replace software engineers?</h1>" in html
    assert '<link rel="canonical" href="https://www.whatsindemand.com/ai/will-ai-replace-software-engineer">' in html


def test_page_shows_verdict_and_lens():
    html = _page()
    assert "aren't cutting" in html.lower() or "not yet" in html.lower()
    assert LENS_PHRASE in html


def test_page_noindex_below_threshold():
    assert '<meta name="robots" content="noindex">' in _page(total=12)
    assert '<meta name="robots" content="noindex">' not in _page(total=200)


def test_page_has_breadcrumb_and_article_schema_no_faq():
    html = _page()
    assert '"@type": "BreadcrumbList"' in html
    assert '"@type": "Article"' in html
    assert "FAQPage" not in html


def test_page_renders_bls_section_only_when_present():
    assert "government" not in _page(bls=None).lower()
    withbls = _page(bls={"pct": 15.0, "period": "2024 to 2034"})
    assert "15%" in withbls


def test_flagship_html_injected_when_given():
    html = _page(flagship="<p id='flag'>hand written</p>")
    assert "<p id='flag'>hand written</p>" in html


def test_index_lists_items_and_links():
    html = render_outlook_index(items=[("software engineers", "software-engineer", 17151)])
    assert "/ai/will-ai-replace-software-engineer" in html
    assert "17,151" in html


def test_sitemap_urls_shape():
    urls = ai_sitemap_urls([("software-engineer", "2026-09-17")], today="2026-09-17")
    assert urls[0].startswith("<url><loc>https://www.whatsindemand.com/ai/</loc>")
    assert any("/ai/will-ai-replace-software-engineer</loc>" in u for u in urls)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/ai_outlook/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ai_render'`.

- [ ] **Step 3: Implement**

Create `backend/app/services/ai_render.py`:

```python
"""Pure HTML builders for the 'Will AI replace [role]?' pages.

No Flask, no DB. Takes plain dicts, returns strings. The route layer
(app/routes/ai_outlook.py) fetches data and calls these.
"""
import json

from app.routes._web import WEB_URL, _esc, _slugify  # pure helpers, safe to import
from app.services.ai_verdict import LENS_PHRASE

_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
background:#0a0a0a;color:#f0f0f0;margin:0;padding:0;line-height:1.6}
main{max-width:720px;margin:0 auto;padding:48px 24px}
a{color:#7dd3fc;text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:2.1rem;margin:0 0 8px;letter-spacing:-0.02em}
h2{font-size:1.05rem;margin:36px 0 12px;color:#aaa;text-transform:uppercase;letter-spacing:0.08em}
.sub{color:#888;margin:0 0 24px}
.verdict{font-size:1.25rem;color:#fff;background:#141414;border:1px solid #2a2a2a;
padding:20px 22px;margin:24px 0;border-left:3px solid #7dd3fc}
.verdict p{margin:10px 0 0;font-size:1rem;color:#ccc}
.stat-row{display:flex;gap:32px;flex-wrap:wrap;margin:24px 0;padding:20px;background:#141414;border:1px solid #2a2a2a}
.stat b{display:block;font-size:1.6rem}.stat span{font-size:0.8rem;color:#888}
table{width:100%;border-collapse:collapse}
td,th{padding:8px 4px;border-bottom:1px solid #222;text-align:left;font-size:0.95rem}
th{color:#888;font-weight:500;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em}
.cta{display:inline-block;margin:32px 0;padding:14px 24px;background:#fff;color:#000;font-weight:600}
.cta:hover{text-decoration:none;opacity:.9}
footer{color:#666;font-size:0.8rem;margin-top:48px;border-top:1px solid #222;padding-top:16px}
.num{font-variant-numeric:tabular-nums}
.related{list-style:none;padding:0;margin:12px 0 0}.related li{margin:5px 0}
"""


def _canonical(slug):
    return f"{WEB_URL}/ai/will-ai-replace-{slug}"


def render_role_outlook_page(*, role_singular, role_plural, slug, month, data,
                             verdict, bls, related, min_jobs, flagship_html=None):
    canonical = _canonical(slug)
    noindex = data["total"] < min_jobs
    title = (f"Will AI replace {role_plural}? What the hiring data says, "
             f"{month} — WhatsInDemand")
    description = f"{verdict['headline']} {_esc(verdict['detail'])[:140]}"

    breadcrumb_ld = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "WhatsInDemand", "item": f"{WEB_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Will AI replace…", "item": f"{WEB_URL}/ai/"},
            {"@type": "ListItem", "position": 3, "name": f"Will AI replace {role_plural}?", "item": canonical},
        ],
    })
    article_ld = json.dumps({
        "@context": "https://schema.org", "@type": "Article",
        "headline": f"Will AI replace {role_plural}?",
        "about": role_singular, "url": canonical,
        "dateModified": None,  # filled by route via string replace? No — pass month.
        "author": {"@type": "Organization", "name": "WhatsInDemand", "url": f"{WEB_URL}/"},
        "publisher": {"@type": "Organization", "name": "WhatsInDemand", "url": f"{WEB_URL}/"},
        "isAccessibleForFree": True,
    })

    # BLS section (only when present)
    bls_html = ""
    if bls:
        bls_html = (
            f"<h2>The official outlook</h2>"
            f"<p>The U.S. Bureau of Labor Statistics expects {role_plural} employment "
            f"to change {bls['pct']:+.0f}% over {bls['period']}. "
            f"<a href='https://www.bls.gov/emp/' rel='nofollow'>Source: BLS Employment Projections</a>.</p>"
        )

    # Skills split: AI/ML tasks vs the rest
    ai_skills = [s for s in data["skills"] if s["subcategory"] == "AI & Machine Learning"]
    other_skills = [s for s in data["skills"] if s["subcategory"] != "AI & Machine Learning"][:6]
    changing = ""
    if ai_skills:
        names = ", ".join(_esc(s["name"]) for s in ai_skills[:4])
        changing = (f"<p>AI shows up directly in these openings: {names}. "
                    f"That is the part of the job changing fastest.</p>")
    still_human = ""
    if other_skills:
        names = ", ".join(_esc(s["name"]) for s in other_skills)
        still_human = (f"<p>Employers still ask most for: {names} — "
                       f"the parts of the work people are hired to own.</p>")

    companies_html = "".join(
        f"<tr><td>{_esc(c['name'])}</td><td class='num'>{c['count']}</td></tr>"
        for c in data["companies"]
    )
    related_html = "".join(
        f"<li><a href='/ai/will-ai-replace-{_slugify(name)}'>Will AI replace {_esc(name)}s?</a></li>"
        for name, _ in related
    )

    flagship_block = flagship_html or ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="{_esc(description)}">
<link rel="canonical" href="{canonical}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:title" content="{_esc('Will AI replace ' + role_plural + '?')}">
<meta property="og:description" content="{_esc(verdict['headline'])}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{WEB_URL}/og-image.png?v=3">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{breadcrumb_ld}</script>
<script type="application/ld+json">{article_ld}</script>
<style>{_CSS}</style>
</head>
<body>
<main>
  <p class="sub"><a href="{WEB_URL}">WhatsInDemand</a> / <a href="{WEB_URL}/ai/">will AI replace…</a></p>
  <h1>Will AI replace {_esc(role_plural)}?</h1>
  <p class="sub">Based on live job postings — updated {month}</p>

  <div class="verdict">{_esc(verdict['headline'])}
    <p>{_esc(verdict['detail'])}</p>
  </div>

  <div class="stat-row">
    <div class="stat"><b class="num">{data['total']:,}</b><span>live openings</span></div>
    <div class="stat"><b class="num">{data['ai_pct']}%</b><span>ask for AI skills</span></div>
    <div class="stat"><b class="num">{data['remote_pct']}%</b><span>remote</span></div>
    <div class="stat"><b class="num">{data['company_count']:,}</b><span>companies hiring</span></div>
  </div>

  {bls_html}

  <h2>What AI is actually changing</h2>
  {changing}
  {still_human}

  {flagship_block}

  <h2>Who's hiring right now</h2>
  <table><tr><th>Company</th><th>Open roles</th></tr>{companies_html}</table>

  <p style="margin-top:28px"><a href="{WEB_URL}/r/{slug}">See the full {_esc(role_singular)} data page →</a></p>

  <h2>Related</h2>
  <ul class="related">{related_html}</ul>

  <a class="cta" href="{WEB_URL}">See the live dashboard — free →</a>

  <footer>
    Numbers come from live job postings at {LENS_PHRASE}, refreshed weekly.
    Official projections are from the U.S. Bureau of Labor Statistics.
    <br>© WhatsInDemand
  </footer>
</main>
</body></html>"""


def render_outlook_index(*, items):
    lis = "".join(
        f"<li><a href='/ai/will-ai-replace-{slug}'>Will AI replace {_esc(role_plural)}?</a> "
        f"<span class='num' style='color:#888'>({total:,} openings)</span></li>"
        for role_plural, slug, total in items
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Will AI replace your job? — WhatsInDemand</title>
<meta name="description" content="Honest, data-backed answers to 'Will AI replace [job]?' for {len(items)} roles, from live job postings.">
<link rel="canonical" href="{WEB_URL}/ai/">
<style>{_CSS}li{{margin:6px 0}}</style></head>
<body><main>
<p class="sub"><a href="{WEB_URL}">WhatsInDemand</a></p>
<h1>Will AI replace your job?</h1>
<p class="sub">Straight answers from live hiring data — updated weekly</p>
<ul>{lis}</ul>
</main></body></html>"""


def ai_sitemap_urls(rows, today):
    """rows: list of (slug, lastmod). Returns list of <url> strings incl. the hub."""
    out = [f"<url><loc>{WEB_URL}/ai/</loc><lastmod>{today}</lastmod></url>"]
    out += [
        f"<url><loc>{WEB_URL}/ai/will-ai-replace-{slug}</loc>"
        f"<lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq></url>"
        for slug, lastmod in rows
    ]
    return out
```

> Note on the `Article` schema `dateModified`: leave it out rather than emit `null`. Change the `article_ld` dict to include `"dateModified": month_iso` and add a `month_iso` parameter, OR drop the key. For simplicity, DROP the `dateModified` key entirely in Step 3 (remove that line) — a valid Article without it is fine. Update the test only if you keep it; the provided test does not assert on `dateModified`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/ai_outlook/ -v`
Expected: PASS (all). Fix the `dateModified` line per the note if JSON serialization complains (it won't — `None` serializes to `null` — but remove it anyway for clean output).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_render.py backend/tests/ai_outlook/test_render.py
git commit -m "feat: pure HTML renderers for Will-AI-replace pages"
```

---

## Task 4: Role model BLS columns + migration

**Files:**
- Modify: `backend/app/models.py` (Role class, ~line 337)
- Create: `backend/migrations/versions/<generated>_add_bls_columns_to_roles.py`

**Interfaces:**
- Produces: `Role.bls_soc_code` (String(10), nullable), `Role.bls_projection_pct` (Float, nullable), `Role.bls_projection_period` (String(30), nullable).

- [ ] **Step 1: Add columns to the model**

In `backend/app/models.py`, inside `class Role`, after the `avg_salary_max` column, add:

```python
    # BLS Employment Projections (populated by scripts/map_roles_to_bls.py)
    bls_soc_code = db.Column(db.String(10), index=True)       # e.g. "15-1252"
    bls_projection_pct = db.Column(db.Float)                  # 10-yr % change
    bls_projection_period = db.Column(db.String(30))          # e.g. "2024 to 2034"
```

- [ ] **Step 2: Generate the migration**

Run:
```bash
cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python -m flask --app run:app db migrate -m "add bls columns to roles"
```
> Use the same invocation the repo uses for Flask-Migrate. If `flask db` is not wired to `run:app`, check `backend/README` / existing migration commands and match them. Inspect the generated file: it must `add_column` three nullable columns on `roles` and nothing else. Remove any unrelated autogenerated drift.

- [ ] **Step 3: Review the generated migration by reading it**

Open the new file in `backend/migrations/versions/`. Confirm `upgrade()` adds exactly the three columns and `downgrade()` drops them. Delete any spurious operations autogenerate added from model/DB drift.

- [ ] **Step 4: Apply to prod**

Run:
```bash
cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python -m flask --app run:app db upgrade
```
Expected: "Running upgrade … add bls columns to roles". Verify: a quick query shows the columns exist and are NULL.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/migrations/versions/
git commit -m "feat: add BLS projection columns to Role"
```

---

## Task 5: Role→SOC mapping script (+ real BLS numbers)

Maps our ~250 roles to BLS occupation codes, fills real projection numbers into `bls_projections.json`, flags rows a human must check.

**Files:**
- Create: `backend/scripts/map_roles_to_bls.py`
- Modify: `backend/app/data/bls_projections.json` (add real records for mapped SOCs)

**Interfaces:**
- Consumes: `Role` rows; `bls_for` for divergence sanity check; `decide_verdict` thresholds.
- Produces: writes `Role.bls_soc_code/pct/period`; writes a review file `backend/scripts/_out/bls_mapping_review.csv`.

- [ ] **Step 1: Write the script (dry-run default)**

Create `backend/scripts/map_roles_to_bls.py`. It must:
1. Load a curated title→SOC seed dict (start with the common occupations; the maintainer extends it). Include at least:
```python
SEED = {
    "software engineer": "15-1252", "data scientist": "15-2051",
    "accountant": "13-2011", "product manager": "11-2021",  # verify SOC choice
    "marketing manager": "11-2021", "financial analyst": "13-2051",
    "graphic designer": "27-1024", "ux researcher": "19-3033",
    # ... maintainer extends; unmatched roles are reported, not guessed.
}
```
2. For each `Role` with `total_active_jobs >= 30`, match `normalized_title.lower()` against `SEED` (exact, then simple contains). Unmatched → reported, left NULL.
3. For each matched role, look up the SOC in `bls_projections.json` via `bls_for`. If the SOC is missing from the JSON, report it under "SOC needs BLS numbers".
4. Compute a divergence flag: matched role where `bls_pct < FLAT_FLOOR` (declining) — surface for human eyeball as "possible bad map or genuine decline".
5. Write everything to `scripts/_out/bls_mapping_review.csv` (columns: role, soc, bls_pct, active_jobs, ai_pct?optional, flag).
6. Only with `--apply`: write `bls_soc_code/pct/period` onto Role rows for confident matches.

Use the DATABASE_URL-gotcha pattern from CLAUDE.md (set env before importing `create_app`). Follow the dry-run/`--apply` convention. Mirror an existing script in `backend/scripts/` (e.g. `update_ai_taxonomy.py`) for app-context boilerplate.

- [ ] **Step 2: Source real BLS numbers for the mapped SOCs**

Download the current BLS Employment Projections "Occupational projections and worker characteristics" table from bls.gov/emp (the maintainer does this in a browser). For every distinct SOC the script mapped, add a real record to `backend/app/data/bls_projections.json`:
```json
"27-1024": {"pct": 2.0, "period": "2024 to 2034", "employment_base": 0}
```
Correct the three seeded flagship numbers against the real release while here.

- [ ] **Step 3: Dry-run and read the review file**

Run:
```bash
cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/map_roles_to_bls.py
```
Open `scripts/_out/bls_mapping_review.csv`. Manually resolve unmatched roles and divergence flags (extend `SEED`, fix SOCs). Re-run until the review file looks right.

- [ ] **Step 4: Apply**

Run:
```bash
cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/map_roles_to_bls.py --apply
```
Expected: prints how many roles were updated. Spot-check one role's columns in the DB.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/map_roles_to_bls.py backend/app/data/bls_projections.json
git commit -m "feat: map roles to BLS occupation codes + real projection data"
```

---

## Task 6: Route blueprint + registration

The thin composer: fetch via `_role_page_data`, call the pure functions, return HTML. Also wires the sitemap and cross-links. No DB unit test (consistent with `/r/`); correctness is covered by the pure-function tests plus a manual smoke test.

**Files:**
- Create: `backend/app/routes/ai_outlook.py`
- Modify: `backend/app/__init__.py` (register blueprint, ~line 104)
- Modify: `backend/app/routes/public.py` (sitemap + `/r/` cross-link)

**Interfaces:**
- Consumes: `_find_role_by_slug`, `_role_page_data`, `_related_roles`, `MIN_JOBS_FOR_PAGE` from `public.py`; `_slugify`, `WEB_URL`, `CACHE_HEADER` from `_web.py`; `decide_verdict`, `bls_for` from `ai_verdict`; `render_*`, `ai_sitemap_urls` from `ai_render`.
- Produces: `ai_outlook_bp` (Blueprint); `ai_sitemap_rows() -> list[(slug, lastmod)]` used by `public.sitemap`.

- [ ] **Step 1: Write the blueprint**

Create `backend/app/routes/ai_outlook.py`:

```python
"""Server-rendered 'Will AI replace [role]?' pages. Thin composer over
pure logic in app/services/ai_verdict.py and app/services/ai_render.py.
Served via Vercel rewrite at /ai/*."""
from datetime import datetime

from flask import Blueprint, Response

from app.models import Role
from app.routes._web import WEB_URL, CACHE_HEADER, _slugify
from app.routes.public import (
    _find_role_by_slug, _role_page_data, _related_roles, MIN_JOBS_FOR_PAGE,
)
from app.services.ai_verdict import decide_verdict, bls_for
from app.services.ai_render import (
    render_role_outlook_page, render_outlook_index,
)
from app.services.ai_flagship import flagship_html_for  # Task 7

ai_outlook_bp = Blueprint("ai_outlook", __name__)


def _plural(name):
    """Rough plural for display copy: 'Data Scientist' -> 'data scientists'."""
    n = name.lower()
    if n.endswith(("s", "x", "z", "ch", "sh")):
        return n + "es"
    if n.endswith("y") and n[-2:-1] not in "aeiou":
        return n[:-1] + "ies"
    return n + "s"


@ai_outlook_bp.route("/ai/will-ai-replace-<role_slug>", methods=["GET"])
def ai_role_page(role_slug):
    # strip our fixed prefix if the matcher passed the full tail
    role = _find_role_by_slug(role_slug)
    if not role:
        return Response("<h1>Role not found</h1>", mimetype="text/html", status=404)

    canonical_slug = _slugify(role.normalized_title)
    if role_slug != canonical_slug:
        return Response(status=301,
                        headers={"Location": f"/ai/will-ai-replace-{canonical_slug}"})

    data = _role_page_data(role)
    if not data:
        return Response("<h1>No active postings for this role</h1>",
                        mimetype="text/html", status=404)

    role_plural = _plural(role.normalized_title)
    bls_rec = bls_for(role.bls_soc_code)
    verdict = decide_verdict(
        role_plural=role_plural, ai_pct=data["ai_pct"], total=data["total"],
        bls_pct=(bls_rec or {}).get("pct"),
        bls_period=(bls_rec or {}).get("period"),
    )
    related = [(r.normalized_title, _slugify(r.normalized_title))
               for r in _related_roles(role)]

    html = render_role_outlook_page(
        role_singular=role.normalized_title, role_plural=role_plural,
        slug=canonical_slug, month=datetime.utcnow().strftime("%B %Y"),
        data=data, verdict=verdict, bls=bls_rec, related=related,
        min_jobs=MIN_JOBS_FOR_PAGE, flagship_html=flagship_html_for(canonical_slug),
    )
    return Response(html, mimetype="text/html", headers={"Cache-Control": CACHE_HEADER})


@ai_outlook_bp.route("/ai/", methods=["GET"])
def ai_index():
    roles = Role.query.filter(
        Role.total_active_jobs >= MIN_JOBS_FOR_PAGE
    ).order_by(Role.total_active_jobs.desc()).all()
    items = [(_plural(r.normalized_title), _slugify(r.normalized_title),
              r.total_active_jobs) for r in roles]
    return Response(render_outlook_index(items=items), mimetype="text/html",
                    headers={"Cache-Control": CACHE_HEADER})


def ai_sitemap_rows():
    """(slug, lastmod) for every indexable role — consumed by public.sitemap."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    roles = Role.query.filter(Role.total_active_jobs >= MIN_JOBS_FOR_PAGE).all()
    return [(_slugify(r.normalized_title), today) for r in roles]
```

- [ ] **Step 2: Register the blueprint**

In `backend/app/__init__.py`, after the `public_bp` registration (~line 105), add:

```python
    from app.routes.ai_outlook import ai_outlook_bp
    app.register_blueprint(ai_outlook_bp)
```

- [ ] **Step 3: Wire the sitemap (avoid circular import)**

In `backend/app/routes/public.py`, inside the `sitemap()` function, after the role/blog urls are built and before the XML is assembled, add a **function-local import** (prevents a circular import, since `ai_outlook` imports from `public`):

```python
    from app.routes.ai_outlook import ai_sitemap_rows
    from app.services.ai_render import ai_sitemap_urls
    urls += ai_sitemap_urls(ai_sitemap_rows(), today)
```
Place this right after the existing `urls += blog_sitemap_urls(...)` line.

- [ ] **Step 4: Cross-link the `/r/` page to its `/ai/` counterpart**

In `backend/app/routes/public.py`, in `public_role_page`, add a link in the page body. After the `intro_html` block is inserted into the template (find where `{intro_html}` appears in the `html` f-string), add below it a one-line callout. Concretely, change the CTA area to also include:

```html
  <p style="margin-top:18px"><a href="/ai/will-ai-replace-{canonical_slug}">Will AI replace {_esc(title)}s? →</a></p>
```
Insert it just before `<a class="cta"` in the role-page template.

- [ ] **Step 5: Smoke-test locally against prod data**

Run the app and curl the new routes:
```bash
cd backend && DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python run.py &
sleep 4
curl -s localhost:5001/ai/ | grep -o "<h1>[^<]*</h1>"
curl -s localhost:5001/ai/will-ai-replace-software-engineer | grep -o "<h1>[^<]*</h1>"
curl -s localhost:5001/ai/will-ai-replace-software-engineer | grep -c "canonical"
curl -s localhost:5001/sitemap.xml | grep -c "/ai/will-ai-replace-"
curl -s localhost:5001/r/software-engineer | grep -o "will-ai-replace-software-engineer"
kill %1
```
Expected: index and role `<h1>` render; canonical present; sitemap includes `/ai/` role URLs; `/r/` page links to `/ai/`. Also confirm the full pure-function test suite still passes:
```bash
venv/bin/python -m pytest tests/ai_outlook/ -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/ai_outlook.py backend/app/__init__.py backend/app/routes/public.py
git commit -m "feat: /ai/ route, sitemap wiring, and /r/ cross-links"
```

---

## Task 7: Flagship deep-dive mechanism + 3 essays

Flagship roles get an extra hand-written editorial block injected into the same page. The mechanism is code; the three essays are content that must pass the voice gate and get Henry's review.

**Files:**
- Create: `backend/app/services/ai_flagship.py`
- Create: `backend/app/content/ai_flagships/software-engineer.html`
- Create: `backend/app/content/ai_flagships/data-scientist.html`
- Create: `backend/app/content/ai_flagships/accountant.html`
- Test: `backend/tests/ai_outlook/test_flagship.py`

**Interfaces:**
- Produces: `flagship_html_for(slug: str) -> str | None` — returns the HTML partial for a flagship slug, else `None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai_outlook/test_flagship.py`:

```python
from app.services.ai_flagship import flagship_html_for


def test_returns_none_for_non_flagship():
    assert flagship_html_for("operations-manager") is None


def test_returns_html_for_flagship():
    html = flagship_html_for("software-engineer")
    assert html is not None
    assert "<" in html  # some markup
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/ai_outlook/test_flagship.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the loader**

Create `backend/app/services/ai_flagship.py`:

```python
"""Loads hand-written flagship essays injected into /ai/ pages."""
import os

_DIR = os.path.join(os.path.dirname(__file__), "..", "content", "ai_flagships")
_FLAGSHIPS = {"software-engineer", "data-scientist", "accountant"}


def flagship_html_for(slug):
    if slug not in _FLAGSHIPS:
        return None
    path = os.path.join(_DIR, f"{slug}.html")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()
```

- [ ] **Step 4: Write the three essays (content — voice gate applies)**

Create each HTML partial (no `<html>`/`<head>` — it is injected mid-page). Each ~200–350 words, under an `<h2>` heading. Follow the Global Constraints voice rules exactly: plain words, no jargon, no invented terms, explain numbers, label our data as `LENS_PHRASE`, never absolute. Structure per essay:
- One `<h2>` like `The longer answer for software engineers`
- 2–3 short paragraphs: what the data shows, what AI is genuinely taking over vs. not, the honest bottom line.
- No hype, no clickbait, no emoji.

Example shape for `software-engineer.html` (rewrite in Henry's voice, do not ship verbatim):

```html
<h2>The longer answer for software engineers</h2>
<p>Software engineering is not going away, but it is changing faster than most
jobs. The tools now write a lot of the routine code — the simple pages, the
boilerplate, the first draft of a test. That is real, and it is why the job feels
different than it did two years ago.</p>
<p>What the tools still cannot do is decide what to build, hold a messy system in
their head, or take responsibility when something breaks at 2am. Those are the
parts companies keep hiring for. Across the roughly 3,300 fast-growing companies
we track, most software engineer openings still ask first for judgment and
system skills, with AI skills listed as a growing extra.</p>
<p>So the honest read: fewer people needed for the simple parts, more value on the
hard parts. If you are an engineer, the move is to get good at the work the tools
are bad at.</p>
```

> These essays require Henry's review before deploy. Mark the task complete only after he has read all three.

- [ ] **Step 5: Run tests + smoke-test injection**

Run:
```bash
cd backend && venv/bin/python -m pytest tests/ai_outlook/ -v
DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python run.py &
sleep 4
curl -s localhost:5001/ai/will-ai-replace-software-engineer | grep -c "longer answer"
kill %1
```
Expected: tests pass; flagship block appears on the software-engineer page and NOT on a non-flagship page.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_flagship.py backend/app/content/ai_flagships/ backend/tests/ai_outlook/test_flagship.py
git commit -m "feat: flagship deep-dive essays for top AI-replacement roles"
```

---

## Task 8: Vercel rewrite

Route `/ai/*` from the Vercel front end to the Railway origin, like `/r/` and `/sitemap.xml`.

**Files:**
- Modify: `frontend/vercel.json`

- [ ] **Step 1: Add the rewrite**

In `frontend/vercel.json`, in the `rewrites` array, add this object BEFORE the SPA catch-all (`{ "source": "/(.*)", "destination": "/" }`):

```json
{ "source": "/ai/:path*", "destination": "https://whatsindemand-production.up.railway.app/ai/:path*" },
```
Add a bare `/ai` → origin rewrite too if the hub must resolve without a trailing slash:
```json
{ "source": "/ai", "destination": "https://whatsindemand-production.up.railway.app/ai/" },
```

- [ ] **Step 2: Verify JSON is valid**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('vercel.json','utf8')); console.log('valid')"`
Expected: `valid`.

- [ ] **Step 3: Commit**

```bash
git add frontend/vercel.json
git commit -m "feat: Vercel rewrite for /ai/ pages to Railway origin"
```

---

## Task 9: Ship + verify live

**Files:** none (deploy + verification)

- [ ] **Step 1: Merge to main (deploys Railway backend + Vercel frontend)**

After Henry approves the flagship essays:
```bash
git checkout main && git merge --no-ff feat/will-ai-replace-pages
git push origin main
```
> Confirm with Henry before pushing — push to `main` auto-deploys both services.

- [ ] **Step 2: Verify live once deploys finish**

```bash
curl -s https://www.whatsindemand.com/ai/ | grep -o "<h1>[^<]*</h1>"
curl -s https://www.whatsindemand.com/ai/will-ai-replace-software-engineer | grep -o "<h1>[^<]*</h1>"
curl -s https://www.whatsindemand.com/sitemap.xml | grep -c "/ai/will-ai-replace-"
```
Expected: pages render at the public host; sitemap lists the `/ai/` URLs.

- [ ] **Step 3: Submit for indexing**

In Google Search Console: URL-inspect + request indexing on `/ai/` and the 3 flagship URLs. The rest are discovered via the sitemap (already submitted).

- [ ] **Step 4: Set a follow-up to watch results**

Note in `project_pending_ops` memory (or a calendar reminder): check GSC Performance for impressions on "will ai replace *" queries in 2–4 weeks, and watch for AI-Overview appearances on the 3 flagship roles.

---

## Self-Review (completed during authoring)

- **Spec coverage:** URL structure (T6, T8), page anatomy (T3), verdict logic incl. divergence (T1), BLS plumbing incl. static JSON + columns + mapping script with divergence flag (T2, T4, T5), sitemap (T6), flagships (T7), schema/AEO Article+Breadcrumb no-FAQ (T3), quality gates noindex<30 (T3), cross-links (T6), Vercel (T8), voice constraints (Global Constraints + T7). All spec sections map to a task.
- **Placeholder scan:** no TBD/TODO in code steps; every code step has runnable code. The three flagship essays are intentionally content (voice-gated + human-reviewed), with a worked example given as the quality bar.
- **Type consistency:** `decide_verdict(role_plural=, ai_pct=, total=, bls_pct=, bls_period=)` and its return keys (`stance/diverges/headline/detail`) are used identically in T3 and T6. `bls_for(soc_code, table=None)` consistent in T2/T6. `render_role_outlook_page(...)` params match its call in T6. `flagship_html_for(slug)` consistent T6/T7.
