# Design: "Will AI replace [role]?" content system

**Date:** 2026-09-17
**Status:** Draft — awaiting review
**Author:** Henry + Claude

## Goal

Rank on (or be cited from) Google page one for the "Will AI replace ___" query
family, by turning WhatsInDemand's live hiring data into the definitive
*evidence-based* answer for each role.

## Non-goals

- Beating Forbes / universities for head-term **blue links** in the short term
  (multi-year authority play; not promised here).
- Live volume-trend verdicts in v1 (cohort-locked trend math is deliberately
  excluded from these fast pages; see Role-Growth Leaderboard constraints).
- Any AI-written prose at scale (scaled-content-abuse risk + brand risk).

## SERP reality (why this design)

Live SERP checks (2026-09-17) for "will AI replace software engineers" and
"...accountants" show these results are **authority-dominated and evidence-led**:
universities (Stevens, ASU), big brands (Forbes, Intuit, Xero, Coursera, Becker),
and community/opinion (Substack, LinkedIn, HN). The winning content leans on
*data*: BLS employment projections, a Stanford study, "AI replaces tasks not roles."

Where WhatsInDemand can win:

- **AI Overviews / AI-answer citations** — high value, very winnable. Google's AI
  Overview (and ChatGPT/Perplexity) wants a *fresh, specific statistic* to cite;
  no competitor has one. WhatsInDemand does: "X% of {role} postings now require AI
  skills." This is the single most citable sentence on the topic.
- **Long-tail role variants** ("will AI replace [UX researcher / solutions
  architect / ...]") — weak competition, and we have ~250 roles.
- **Head terms via blue link** — hard; pursued only via the 3 flagship pages, as a
  long game.

## Scope

Hybrid, per approved brainstorm:
- **Programmatic baseline**: one page per indexable role (~250, ≥ 30 postings).
- **3 flagship deep-dives**: Software Engineer, Data Scientist, Accountant
  (hand-crafted depth on top of the same template).

Evidence base: **live hiring data + BLS Employment Projections**, phased so the
BLS mapping never blocks the programmatic rollout.

## URL structure & routing

- `/ai/will-ai-replace-<slug>` — one page per role. `<slug>` reuses
  `_slugify(role.normalized_title)` (singular, consistent with `/r/`); title & H1
  use natural plural ("software engineers").
- `/ai/` — hub index listing every indexable page (crawl depth + interlinking).
- New Flask blueprint `backend/app/routes/ai_outlook.py`, registered in
  `app/__init__.py`. Keeps `public.py` focused. Reuses `_web.py` helpers
  (`WEB_URL`, `CACHE_HEADER`, `_esc`, `_slugify`) and, from `public.py`,
  `_find_role_by_slug`, `_role_page_data`, `MIN_JOBS_FOR_PAGE`, `_PAGE_CSS`
  (extract the shared helpers into `_web.py` if cleaner than cross-importing).
- **Canonical-slug 301** guard, same as `/r/` (redirect `/ai/will-ai-replace-<x>`
  to the canonical slug when they differ).
- **Vercel rewrite**: add `{ "source": "/ai/:path*", "destination":
  "https://whatsindemand-production.up.railway.app/ai/:path*" }` to
  `frontend/vercel.json` (place ABOVE the SPA catch-all `/(.*)` rule).
- **Cross-linking**: each `/r/<role>` links to its `/ai/` counterpart and back.

## Page anatomy (programmatic template)

Server-rendered, no-JS, inline CSS — same shell as `/r/`. Sections:

1. **Verdict box (above the fold)** — honest one-sentence answer + the signals it
   rests on. The AI-Overview citation target.
2. **What the live hiring data shows** — active postings, `ai_pct`, remote %,
   company count (all from `_role_page_data`).
3. **The official outlook (BLS)** — 10-yr projection %, period, source link.
   *Progressive: rendered only when the role is SOC-mapped.*
4. **What AI is actually changing** — the role's top skills split by
   `subcategory == 'AI & Machine Learning'` vs. not, framed as "tasks AI now
   assists with" vs. "human-judgment work still hired for." Per-role unique.
5. **Employers still hiring now** — top companies (demand is real, not theoretical).
6. **Related** — link to the full `/r/<role>` data page + neighboring roles'
   `/ai/` pages (reuse `_related_roles`).
7. **CTA** to the live dashboard.

Meta: data-driven `<title>` / description embedding the verdict + key stat;
self-referencing canonical; OG + Twitter; `noindex` when `total < MIN_JOBS_FOR_PAGE`.

Title pattern: `Will AI replace {role}s? What the hiring data says, {Month Year} — WhatsInDemand`

## Verdict logic (deterministic, honest, never a naked "No")

Computed from up to three signals; degrades gracefully:

- **BLS projection** (authority) — when mapped.
- **AI-skill adoption %** (`ai_pct`) — always available.
- **Hiring-volume trend** — *deferred to a later phase* (not computed on these
  pages; unreliable until ~3 full months of coverage).

v1 tiers (illustrative; finalize thresholds in the plan):

| BLS 10-yr projection | Verdict lead |
|---|---|
| ≥ +5% (growing) | "No — demand is projected to grow; AI is reshaping which tasks get done, not eliminating the role." |
| −2% to +5% (flat) | "Unlikely soon — demand is roughly stable while AI absorbs specific tasks." |
| < −2% (declining) | "Under pressure — projections point down; here's exactly which tasks AI is taking and which remain human." |
| BLS unmapped | Lead with the adoption read only: "Employers aren't cutting {role}s — {ai_pct}% of postings now require AI fluency." |

Every verdict is paired with the live `ai_pct` and is non-absolute + sourced.

### Handling signal divergence

The two signals measure different things, so most apparent contradictions
dissolve once the axes are separated:

- **BLS** = 10-year headcount projection for a US occupation (structural, ~yearly
  vintage).
- **`ai_pct`** = share of current postings asking for AI skills (task/skill mix,
  not headcount).

"BLS growing **and** high AI adoption" is therefore not a contradiction — it is the
augmentation thesis (the job is growing *and* changing), and is the best-case page.
The only genuine contradiction is on the **demand axis**: BLS projecting decline vs.
our live hiring being strong (or vice versa). Because live volume-trend is deferred,
v1 rarely hits a hard contradiction.

When the signals genuinely diverge (beyond a threshold set in the plan), three rules:

1. **Never hide a signal to force one verdict.** The verdict box switches from the
   single-line answer to a **two-horizon framing** that shows both signals and names
   the tension plainly — e.g. "Right now, demand is strong across the high-growth
   companies we track; but BLS projects this occupation to shrink N% by 2034. Both
   can be true — near-term demand vs. long-term structural shift." An honestly
   explained divergence is more citable and more trustworthy than a fake-confident
   "No", and it protects the data-credibility brand.
2. **Always label our lens; never overclaim it.** Our number is "across the ~3,300
   high-growth companies we track", never "the labor market". Much apparent
   divergence is sample skew (we index tech/startup ATS boards; BLS covers all US
   employment). Saying so defuses most of it.
3. **A large divergence is a suspected mapping bug, not a finding.** It most likely
   means a wrong SOC map; it is flagged for human review before publish (see mapping
   script below), not published as a verdict.

Implementation: the verdict logic has an explicit **divergence branch**. When the
signals disagree beyond the threshold, it renders the two-horizon template instead
of a single tier. Deterministic and honest.

## BLS data plumbing

- **Static JSON** `backend/app/data/bls_projections.json`: `SOC code → { pct,
  period, employment_base }`. BLS Employment Projections update ~yearly; no live
  API needed. Source: BLS Employment Projections program.
- **New nullable `Role` columns** (Alembic migration in `backend/migrations/`):
  `bls_soc_code` (String), `bls_projection_pct` (Float), `bls_projection_period`
  (String, e.g. "2024–2034").
- **One-time mapping script** `backend/scripts/map_roles_to_bls.py`
  (dry-run default, `--apply`): auto-maps role titles → SOC (roles collapse to far
  fewer occupations), writes a review file flagging low-confidence rows — and any
  role whose BLS projection sharply contradicts its live hiring signal (a likely bad
  SOC map) — for manual eyeball, then persists columns. Follows the repo `--apply`
  convention.
- **Pipeline**: near-zero change — pages render on-demand from current data like
  `/r/`. Only the sitemap gains new URLs.

## Sitemap & discovery

Extend `sitemap()` (now in `public.py`; the `/ai/` routes can register their own
url contributor or the sitemap can import from `ai_outlook`): add `/ai/` and each
`/ai/will-ai-replace-<slug>` for roles with `total_active_jobs >=
MIN_JOBS_FOR_PAGE`. Thin roles stay `noindex` and out of the sitemap, same guard
as `/r/`.

## Flagship deep-dives (3)

Software Engineer (17,151 postings), Data Scientist (820), Accountant (472).
Same template + hand-written editorial depth (original angle, more context, one
chart), BLS hand-verified, longer form. These carry the head-term ambition. PM
(1,981) is the fallback if a pick is swapped.

## Schema / AEO

`BreadcrumbList` + **`Article`** (author = Organization; `datePublished` /
`dateModified`; `about` = the role), verdict as the lead claim. **No `FAQPage`** —
Google retired FAQ rich results May 2026; it buys nothing now.

## Quality gates & risk

- **Scaled-content-abuse (Mar 2024)** → mitigated by real per-role data + BLS +
  `noindex` under 30 postings + naturally-worded templating (like `/r/` intros) +
  **zero AI-written prose**.
- **YMYL (careers)** → sourced, non-absolute, methodology-linked verdicts.
- **Voice** → data-first, human, tasteful (see content-voice brand guide). Write
  the way a sharp person actually talks: plain, direct sentences; no jargon, no
  buzzwords, no invented or coined terms; explain any figure in words a reader
  without a stats background understands. This applies to all rendered copy — verdict
  lines, section intros, and the flagship long-form. It is a hard requirement, not a
  preference.

## Build phases

1. Programmatic pages on the live-data spine + `/ai/` hub + sitemap + Vercel
   rewrite + `/r/`↔`/ai/` cross-links.
2. BLS: migration + static JSON + mapping script → section 3 lights up.
3. Three flagship deep-dives.

## Success metrics

- **Leading**: `/ai/` pages indexed (GSC Coverage); impressions on "will ai
  replace *" queries (GSC Performance); appearance in AI Overviews for head roles.
- **Lagging**: page-one blue-link rankings for long-tail role variants; referral
  traffic from AI answer engines.

## Open questions (settle during planning)

- Exact verdict thresholds and copy per tier.
- Whether to extract shared `public.py` helpers into `_web.py` vs. cross-import.
- Chart approach for flagships (inline SVG, no JS — matches the no-JS SSR pages).
