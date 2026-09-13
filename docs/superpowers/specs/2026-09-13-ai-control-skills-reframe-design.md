# Reframing WhatsInDemand around "control-AI" skills

**Date:** 2026-09-13
**Status:** Design — awaiting review
**Scope:** Architectural (new data grouping + landing reframe)

## 1. Thesis

Professionals are anxious about AI and their jobs. The site should meet that
worry head-on and answer it with hiring data, not hype. The data shows a clear,
specific signal worth featuring: employers increasingly expect people who can
**use and direct AI** (Cursor, Claude Code, Copilot, prompts, agents) and, more
quietly, **govern it** — while leaning harder on the human judgment skills AI
can't do.

The on-brand framing (matches the existing About page — *"will AI take my job? …
no hype, no doom, just what the data signals"*):

> **You're worried AI will replace your job. Here's what the hiring data actually
> says — the AI-fluency skills employers now expect, and the human skills rising
> alongside them.**

This is a **question → data answer**, never a substitution claim. See §3.

## 2. Evidence (prod, 111,274 active postings, 2026-09-13)

Full diagnostics: `scratchpad/ai_skill_specificity.py`, `ai_skill_context.py`,
`dump_boards.py` (read-only).

- **Postings are specific, not generic.** Of postings mentioning AI, ~100% also
  tag a *specific* skill/tool. 59 AI skills clear the board gate (≥50 postings,
  ≥8 companies). We feature named skills, not a generic "AI" banner.
- **The "control-AI" cluster is real and sizeable** (postings / companies):
  AI Fluency 2,093/674 · AI agents 2,282/634 · Cursor 1,301/415 ·
  Claude Code 1,165/445 · Prompt Engineering 1,161/487 · RAG 1,133/437 ·
  MCP 958/373 · AI-assisted development 908/409 · Microsoft Copilot 552/241 ·
  Function Calling 415/210 · AI Strategy 403/165 · AI Security 309/163.
- **Employers ask for judgment, not just usage** (verbatim from JDs):
  *"strong, evolving point of view on where AI creates real leverage — and where
  it falls short"* · *"sound judgment about where automation should and shouldn't
  act on its own"* · *"critically evaluate AI-generated code for correctness"* ·
  *"use AI tools well and honestly."*
- **Not just engineers.** AI Fluency's top titles are Product Managers; GPT
  appears for Graphic Designers and Marketing; AI Strategy for PMs and Counsel.
- **What's actually rising** (`rising_skill`, cohort-locked prevalence):
  Claude +17%, AI +8%, Debugging +11% — *and* human skills: Curiosity +11%,
  Adaptability +8.5%, Initiative, Communication. This is the honest twin story.

### Data-quality landmines found by reading raw JD text (must respect)

1. **`falling_skill` cannot be paired with an AI board.** Current contents:
   Product Design −36%, **AI-assisted development −30%**, React −15%, JS −10%.
   An AI skill sits in the *falling* board, and the React/JS decline is
   market-mix, not AI causation. Pairing = incoherent and off-brand. **Drop it
   from the AI narrative.**
2. **`is_required` ≠ "employer marked required."** It is `confidence ≥ 80`,
   i.e. the skill was **mentioned ≥2× in the JD** (`job_aggregator.py:474`,
   `skill_extractor.py:1066`). It signals *emphasis/centrality*, not a formal
   requirement. Label it "often central to the role" or omit — never "required."
3. **Boilerplate contamination.** *Human-in-the-Loop* (3% central) is mostly the
   legal disclaimer *"final decisions are made by human recruiters."*
   *AI safety* (686) is inflated by one company's careers boilerplate (Anthropic;
   ~50 companies, concentrated). **Both excluded from the featured grouping.**
   The compute-side concentration gate (§4b) also auto-drops single-company floods.
4. **Alias churn** can make a skill wobble (AI-assisted development is mid-churn
   from `split_ai_alias.py`). The board ranks by current *level*, which is robust
   to this; growth is shown only as a secondary badge.

## 3. Non-goals (v1)

- No "skills AI is replacing" / fading board, and no causal juxtaposition.
- No per-role "AI-readiness index/score" or dedicated per-role AI view (deferred
  "full surface" option).
- No re-alignment of the existing per-role `ai_exposure` metric
  (`roles.py:293`, keyed on `subcategory=='AI & Machine Learning'`) with the new
  grouping — noted as a follow-up, not in scope.
- No skill detail pages / skill click-through (see §4e).

## 4. Design

### 4a. The `ai_lens` grouping (the enabling change)

The control-AI skills are scattered across categories/subcategories
(AI Fluency = `soft/Personal Effectiveness`, AI Security = `technical/Security`,
AI Strategy = `domain/Business & Operations`, Cursor = `technical/AI & ML`), so
no existing column groups them. Add an orthogonal marker.

- **Migration** (Alembic, `backend/migrations/`): add nullable
  `Skill.ai_lens VARCHAR(20)` (values `'use'`, `'govern'`, `NULL`). Leaves
  category/subcategory untouched.
- **Seed script** `backend/scripts/seed_ai_lens.py` (dry-run default, `--apply`),
  assigning the curated set below. Re-runnable (idempotent upsert of the mapping).

**`ai_lens = 'use'` — Using & directing AI** (~18):
AI Fluency, Prompt Engineering, AI-assisted development, AI coding assistants,
Cursor, Claude Code, Claude, Microsoft Copilot, GPT, OpenAI, Gemini, AI agents,
RAG, MCP, Function Calling, LLM orchestration, LLM integration,
Agentic System Orchestration.

**`ai_lens = 'govern'` — Governing AI** (~4):
AI Security, AI Strategy, Responsible AI, AI Compliance.

**Deliberately excluded:** generic umbrella (Artificial Intelligence, Machine
Learning, LLMs, Generative AI, Deep Learning); build-infra (PyTorch, TensorFlow,
MLOps, Fine-tuning, Embeddings, SageMaker, Vector Databases, LLMOps, Model
Training, LangChain/LangGraph, …); boilerplate-contaminated (Human-in-the-Loop,
AI safety) — revisit once extraction is cleaned.

The exact membership is finalized by reviewing the seed script's dry-run output
against prod before `--apply`.

**Maintenance (decision, not footnote):** new AI skills arrive via the weekly
pipeline untagged and would silently drift out of the board. The
`review-skill-candidates` flow gains a step: when a promoted skill's name/aliases
look AI-related, prompt to set `ai_lens` (`use` / `govern` / skip). The seed
script stays the re-runnable backstop.

### 4b. The board (compute)

Add `compute_ai_skills(global_cohort)` to `compute_market_insights.py`, reusing
the existing cohort + prevalence + concentration helpers
(`global_cohort_ids`, `_skill_stock_counts`, `_skill_concentration`,
`month_bounds`, `full_series`).

- **Candidate set:** `Skill.is_verified AND ai_lens IS NOT NULL`.
- **Rank by current LEVEL** (latest full-month prevalence share on the cohort),
  **not growth** — new tools (Cursor, Claude Code, MCP) have ~0 baseline and a
  growth board would silently drop them.
- **Carry per row:** `label`, `lens` (`use`/`govern`), `to_share`, `to` (count),
  `companies`, `trend` (3-pt), `growth` (nullable badge).
- **Breadth/concentration gate** (reuse `_skill_concentration`): keep only skills
  with `companies ≥ SKILL_MIN_COMPANIES` (8) and top-employer share
  `≤ SKILL_MAX_CONCENTRATION` (0.5) in the latest full month. This auto-drops
  single-company boilerplate (AI-safety-style).
- **Emit** board kind `ai_skill`, `scope='overall'`, ranked by `to_share` desc,
  `TOP_N` per lens (rows tagged with `lens` so the frontend groups them).
- Wire into the script's board loop + the weekly cron summary + the
  idempotent per-week delete/rewrite (`kind` list ~line 405).

### 4c. API

No new endpoint. `ai_skill` flows through the existing `/market/insights`
response (`market.py` returns all kinds for a scope) and the existing stale
guard. Frontend reads `insights.ai_skill`, grouping rows by `lens`.

### 4d. Frontend — landing reframe (`frontend/src/App.js`, `LandingScreen`)

Tone: name the worry, answer with data. No fading/AI pairing.

1. **Hero — unchanged (decided 2026-09-13).** Keep the existing
   *"See hiring trends for [rotating role]"* headline, sub-hero, and role search
   bar as-is. The AI reframe is **additive below the hero**, not a headline
   rewrite. (The §1 framing informs the AI section's copy, not the hero.)
2. **New AI section, directly under the hero — "The AI skills employers now expect."** Two
   sub-lens columns from `insights.ai_skill`:
   - **Using & directing AI** (`lens='use'`) — the ~10-row list: name,
     `to_share` as "% of postings", `companies`, optional growth badge.
   - **Governing AI** (`lens='govern'`) — shorter column (~4 rows), intentionally
     secondary.
   Caption uses verified employer language (§2). If a skill is central in many
   postings, an honest "often central to the role" tag (from the emphasis metric,
   §2.2) — never "required."
3. ~~**"Rising alongside — the human skills" strip**~~ — **DROPPED in v1
   (as-built).** The `rising_skill` snapshot payload carries no `category`, so it
   can't be filtered to soft skills on the frontend without adding another
   backend board. Deferred to keep scope tight; the section still lands the
   non-doom framing on its own.
4. **Role trend boards move below** (existing rising/declining/in-demand role
   panels — unchanged).
5. Reuse the existing `data.stale` guard (hide AI/skill boards when the weekly
   snapshot is stale, as today).

Copy is data-safe: nothing asserts AI *caused* any decline.

### 4e. Click-through (decided)

There is no standalone skill page (`SkillsTab` lives inside the dashboard and
needs a role context). For v1, **AI-board skill rows are non-clickable
descriptive text** (name + share + companies). A future enhancement can route a
skill into a filtered view; not now.

## 5. Testing & validation

- **Seed dry-run** against prod: confirm each curated skill resolves to a real
  verified `Skill` id; review membership; then `--apply`.
- **Board dry-run:** run `compute_market_insights.py` (no `--apply`) and confirm
  `ai_skill` is populated, both lenses present, no single-company skill survives
  the concentration gate, counts match the §2 evidence order.
- **Frontend:** boards render both lenses; empty-lens and `stale` states handled;
  no console errors; mobile layout (existing `md:grid-cols-2`).
- **Regression:** existing role boards + market summary unchanged; `/market/
  insights` shape is additive only.

## 6. Rollout (order matters)

1. Migration (add `ai_lens`) → deploy backend (Railway auto-deploy on `main`).
2. `seed_ai_lens.py --apply` against prod.
3. `compute_market_insights.py --apply` against prod (populate `ai_skill` for the
   current week) — or wait for the Friday cron if timing allows.
4. Frontend landing reframe → deploy (Vercel auto-deploy on `main`).
5. Add the `ai_lens` step to `review-skill-candidates` (can land in parallel).

## 7. Open decisions — all resolved

| Decision | Resolution |
|---|---|
| Grouping mechanism | New `Skill.ai_lens` column (orthogonal to category) |
| Board ranking | Current prevalence level (not growth) |
| Two sub-lenses | `use` (long) + `govern` (short secondary column) |
| Include tool names | Yes (Cursor/Claude Code/Copilot/GPT…) |
| Fading-skills board | Dropped — off-brand + self-contradictory |
| "% required" | Relabel as emphasis/"often central"; never "required" |
| HITL / AI safety | Excluded (boilerplate); concentration gate backstops |
| Skill click-through | Non-clickable text (no skill page exists) |
| `ai_lens` upkeep | Step in `review-skill-candidates` + re-runnable seed |
