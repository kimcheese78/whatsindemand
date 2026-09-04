# WhatsInDemand Content Engine — Design & Content Plan

**Date:** 2026-09-04
**Status:** Design (Phase 2 writer-agent from the native-blog spec, now specified)
**Author:** Design session

## Goal

Grow **organic search traffic** by turning proprietary job-market data into content
nobody else can produce. **Mostly automated** via a writer agent, human-reviewed
before publish.

Two hard constraints drive the whole design:

1. **Data validity** — never publish a number that is wrong *or wrong-looking*.
2. **Human voice** — no AI tells. Gary-Halbert directness, dialed to "data-credible"
   (his hooks and short-sentence punch; the numbers stay straight-faced).

## Why this works (the moat)

We scrape ~3,300 companies and extract skills/roles/salaries. That means we can write
**data-driven posts competitors can't** — the exact content Google and journalists
reward with rankings and links. Every post also **internal-links to the programmatic
`/r/<slug>` role pages**, passing authority to the pages that are now discoverable after
the 2026-09-04 sitemap fix. Generic "10 resume tips" content would waste this moat.

## Content pillars (post types), in build order

1. **Leaderboards** (FIRST — proven by the 2026-09-04 sample). "The fastest-growing /
   most in-demand roles/skills right now." Source: `/api/market/insights` snapshots.
   Best SEO + shareability, and the format is validated.
2. **Role / skill spotlights.** Deep dive on one riser or faller; internal-links to its
   `/r/<slug>` page. Reinforces the programmatic SEO surface.
3. **Head-to-head comparisons.** "React vs X: which one actually gets you hired."
   High long-tail volume; needs two clean datasets + an even-handed frame.
4. **Quarterly flagship report.** "The State of Hiring — Qx." Compiled for **backlinks**
   (still the #1 ranking factor); pitch to newsletters/journalists. One per quarter.

## Editorial cadence

The weekly insights recompute (existing Railway cron) produces **fresh material every
week for free**. Target **2–4 posts/month**. Leaderboards refresh ~monthly; spotlights
fill the gaps. **Consistency beats volume** — thin auto-spam gets penalized; a steady
drip of genuinely data-backed posts compounds.

## Constraint 1 — Data-validity pipeline ("numbers are sacred")

The naive version (let the LLM look at data and write) is where wrong numbers come from.
Rule: **the LLM never sees raw data and never produces a number.**

- **Deterministic fact-sheet.** A Python/SQL step computes a locked, structured fact
  sheet with provenance (reuse cohort-locked `get_trend_data` / the market-insights
  snapshots). The LLM receives only this.
- **Gating thresholds** (calibrated against the real 2026-08-31 snapshot):
  - `confidence >= 0.80`
  - `cohort >= 80` companies
  - `>= ~100` postings in the "to" period
  - reject implausible swings that smell like data artifacts (the greedy-normalizer /
    seniority-alias mis-mapping issue — a role going 0→400 is "true" and embarrassing).
  - **Worked example:** in the 2026-08-31 data the literal top riser was Communications
    Manager **+100%** — *dropped* (confidence 0.63, base 70→140). What survived
    (Maintenance Technician +17.5%, etc.) is less flashy but bulletproof.
- **Cohort-locked only** (same companies both periods) — kills the coverage-ramp confound.
- **Mechanical gate (numbers).** Extract every numeral **and every comparative/qualitative
  claim** from the draft; verify against the fact sheet. The voice uses qualitative
  claims ("almost nobody," "fastest-growing") and rounded paraphrase ("nearly 40%") that
  naive digit-matching misses — gate **qualitative claims and numeric paraphrase**, not
  just exact digits. Any unverified claim → blocked to the review queue. **This is
  necessary, not sufficient** (see Interpretation guard).
- **Interpretation guard (the "true but off" failure).** The mechanical gate proves every
  *number* is real; it cannot prove the *story* is. A thesis like "desk jobs are dying,
  industrial is rising, steer your career" is a **structural claim off a 3-point trend**
  in sectors (manufacturing, warehouse, retail shift-work, maintenance) that plausibly
  **ramp seasonally**. Guards:
  - **Mandatory window caveat** in every trend post: state the window explicitly ("over
    the 90 days ending <date>") and that it's a snapshot, not a forecast.
  - **No structural verbs off a short window.** Ban "dying / booming / the future of /
    permanent shift" unless the move persists across ≥2 comparable prior windows.
    Frame as "cooling / heating up right now," not "the death of X."
  - **Seasonality pressure-test.** Before a thesis becomes a template, check whether the
    same roles rose in the prior comparable window. If they always rise in fall, say so.
  - This guard is enforced by the LLM-judge + human review, not by digit-matching.
- **No manufactured novelty.** Many trends are already in the news (e.g. the blue-collar
  hiring resurgence). Do **not** frame a known trend as a secret nobody's talking about —
  it reads as naive and erodes credibility. Sell **specificity and currency** ("which
  roles, by how much, this month") not "nobody is looking at this." Ban openings that
  claim the reader/market doesn't already know the trend.
- **Reconstructable filter.** Whatever gate excluded a role must be **stated in the
  post** (e.g. "counting only roles hiring across 80+ companies"). Worked seam: Shift
  Supervisor grew +29.6% (confidence 0.81) but is excluded by the cohort≥80 rule (only
  43 companies). A skeptical journalist who spots the omission must be able to
  reconstruct why from the post itself.

## Constraint 2 — Voice / anti-AI-tell system

Two layers.

**Halbert style rules** (in the drafter prompt):
- Write to one person ("you"). Short sentences. Fragments for punch.
- Open with a hook or curiosity gap. Have a point of view. End with a P.S.
- Specific and concrete — real numbers do this work for us.
- Grade ~5 reading level. No hedging.

**Banned-tells list** (mechanical gate — necessary, not sufficient): "in today's…",
"fast-paced", "landscape", "moreover / furthermore / additionally", "it's worth noting",
"delve", "leverage" (as a verb), "robust", "navigate the", "when it comes to",
"that said", tidy rule-of-three tricolons, both-sides hedging, restate-the-obvious H2s,
em-dash overload, "not only… but also", "in conclusion". (Maintain in one file; extend
as new tells surface.)

**Why the wordlist isn't the voice gate.** A grep is trivially gamed — the drafter avoids
the exact words and still emits AI *cadence*: uniform paragraph blocks, the "It's not X,
it's Y" antithesis, tidy both-sides balance, summary-bow endings. That's structure, not
vocabulary, so no wordlist catches it. (The 2026-09-04 hand-written sample already leans
on stock formulas — "Something strange is happening… almost nobody is talking about it,"
"The takeaway is simple" — and a hand draft is the *ceiling*, not the floor, of what an
automated drafter produces.)

**LLM-judge (the real voice gate).** Score each draft against the **approved sample as a
few-shot exemplar** plus the Halbert rubric (rhythm variation, direct address, a real
POV, no formulaic scaffolding). Below threshold → back to the review queue with reasons.
Retire reliance on grep for constraint 2.

**Calibration:** "Halbert directness, data-credible" + high-confidence gating ("safe").
Not full hard-sell — hype fights data credibility.

## Writer-agent architecture

Each stage is a small, independently testable module (one clear purpose, well-defined
interface):

1. `topic_selector` — picks this week's angle from the insights snapshot (biggest
   *gated* movers, freshness, avoid recent repeats). **Uses the `scope` sectors already
   in the API response** (`overall`, `sector:Account Management`, `sector:Infrastructure`,
   …) so one weekly snapshot yields many distinct per-sector cuts — this is what actually
   backs "2–4 posts/month without thin repeats," rather than hand-waving topic exhaustion.
2. `fact_sheet_builder` — deterministic; returns locked structured facts + provenance.
   **Single seam** the drafter, mechanical gate, and judge all depend on.
3. `drafter` — Claude writes prose around the fact sheet + voice guide. Sees the fact
   sheet only, never the DB.
4. `mechanical_gate` — numeric + qualitative-claim check + banned-tells check. Pass/fail
   with reasons. **Necessary, not sufficient** — proves numbers are real, nothing more.
5. `judge` — LLM-judge for **voice** (vs. approved sample) and **interpretation/over-claim**
   (window caveat present? no structural verbs off a short window?). This is where
   constraints 1-substance and 2 are actually enforced.
6. `stager` — writes markdown to `backend/app/blog/drafts/` with front-matter
   (`source: agent`), per the existing native-blog contract.
7. **Human review — the final quality gate, an explicit checklist** (not "flip a flag"):
   - Voice reads human, not formulaic? (spot-check against the sample)
   - Thesis actually supported by the window — no seasonal blip sold as a structural shift?
   - Every number traceable to the fact sheet; the exclusion filter stated in-post?
   - Internal-links to the relevant `/r/<slug>` pages present?
   - Then edit, flip `draft: false`, commit → publishes (existing flow; auto-sitemap).

**Where it runs:** appended to the weekly Railway cron (`agent_run.py`) after the
insights recompute, so every fresh snapshot yields a staged draft. Cost ≈ cents/post.

## SEO specifics

- Titles target "demand"-intent queries and include the year.
- **Every post internal-links to the relevant `/r/<slug>` pages** — passes authority,
  reinforces programmatic SEO.
- Include the crawlable data **table** + a chart + a single clear H1.
- Posts auto-added to `/sitemap.xml` (existing).

## Success metrics

- **Leading:** posts published/month; % of drafts passing the validator first try.
- **Lagging (GSC, check 4–8 weeks out):** indexed pages, impressions, clicks on blog +
  `/r/` pages, average position for target queries.

## Phasing

- **Phase A (now): manual-assisted.** Use the fact-sheet + voice guide to hand-produce
  3–4 leaderboard/spotlight posts (agent drafts, human reviews). Proves editorial
  quality and seeds the freshly-fixed index while Google catches up.
- **Phase B: build the writer agent** (stages 1–5) into the cron.
- **Phase C: comparisons + the quarterly flagship report.**

## Open decisions (defaults chosen; override anytime)

- **Cadence:** 3 posts/month.
- **Drafting model:** `claude-sonnet-5` for routine posts (cost); `claude-opus-4-8` for
  the quarterly report.
- **Review:** git-based, via the existing `drafts/` → review → commit flow.

## Dependencies / notes

- Depends on the 2026-09-04 sitemap fix (Google now discovers `/r/` pages + blog).
- Reuses existing infra: `backend/app/blog/` loader/feed, native-blog front-matter
  contract, `/api/market/insights` snapshots, the weekly cron.
- No new external services. Adds Anthropic API cost (~cents/post) to the existing weekly
  pipeline.
- **Gotcha — date posts in server UTC, not local time.** The blog loader hides any post
  whose front-matter `date` is `> datetime.date.today()`, evaluated on the **UTC** Railway
  server, with **no error logged** (it's the future-scheduling guard). A post dated with a
  local date that's a day ahead of UTC will deploy successfully and then silently fail to
  appear. The `stager` must stamp `date` using the server's UTC `date.today()`. (Hit live
  on 2026-09-04: a Sept-4 post stayed invisible until re-dated Sept-3.)
