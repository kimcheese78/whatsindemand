# Native Blog — Design Spec

**Date:** 2026-08-07
**Status:** Approved for planning
**Branch:** `feat/native-blog`

## Context

WhatsInDemand has a marketing/app site at `whatsindemand.com` (React SPA on Vercel + Flask/Postgres on Railway) and *had* a separate `blog.whatsindemand.com` on Hostinger WordPress. That subdomain is being **deleted**; the blog is being rebuilt **natively inside `whatsindemand.com`**.

**Why:**
- **SEO consolidation.** A blog at `whatsindemand.com/blog` (subdirectory) builds authority for the whole domain — including the app and the programmatic role pages at `/r/<slug>` — instead of stranding it on a separate subdomain.
- **AdSense revenue** as a secondary goal, and — more importantly — **a top-of-funnel content channel** that pulls search traffic into the product (Pro subscription, B2B coach console).
- The site's public role pages (`backend/app/routes/public.py`) already prove the right pattern: **server-rendered, edge-cached HTML** that crawlers and AdSense can read. The React SPA itself is client-rendered and nearly invisible to crawlers, so the blog must NOT be built inside the SPA.

**Content strategy (guides the design, not built here):** a "focused SEO funnel" — a few high-quality posts a month, authored as markdown in git. Two content types: (1) **data-driven posts** from the role-trend engine (original research — defensible and AdSense-safe), and (2) a smaller number of **SEO/AEO keyword posts**. A future **writer-agent** (Phase 2, separate spec) will generate drafts; this platform is built to accommodate it but does not include it.

## Goals

- Server-rendered, edge-cached blog at `whatsindemand.com/blog`, cohesive with the existing `/r/` pages' delivery model but with its own **light, reading-optimized theme**.
- Markdown-file authoring (git is the source of truth for post content).
- SEO essentials: per-post title/description/canonical/OpenGraph, tag pages, RSS, and inclusion in the existing `/sitemap.xml`.
- Reserved AdSense slots + `ads.txt`, activatable once approved.
- Newsletter capture via the existing Resend integration.
- **Agent-ready:** a strict front-matter contract and a drafts/review workflow so a future agent can stage posts for human approval.

## Non-Goals (YAGNI)

- No database-backed post content; no in-browser CMS/admin editor.
- No WordPress, no reverse proxy.
- No comments, no author management, no multi-author bylines (single implicit author in v1).
- No newsletter list-management UI (query the table directly).
- The writer-agent itself (Phase 2).

## Architecture

New Flask blueprint `backend/app/routes/blog.py`, registered in `backend/app/__init__.py` alongside `public_bp`. It mirrors `public.py`:
- Server-rendered HTML, inline/served CSS, **no client JS required** for content.
- `Cache-Control: public, max-age=86400, stale-while-revalidate=604800` (reuse `public.CACHE_HEADER`) so Vercel's edge caches each page for a day. Markdown is rendered **at request time** — no build step — because the edge cache absorbs the cost.
- Served through **Vercel rewrites** (`frontend/vercel.json`), the same mechanism `/r/` and `/sitemap.xml` already use.

Shared helpers (`_esc`, `WEB_URL`, `CACHE_HEADER`) are currently private to `public.py`. Extract the small shared set into `backend/app/routes/_web.py` and import from both, rather than duplicating. Keep the blog's theme CSS separate (it is light; `/r/` is dark).

**Post loading:** a `backend/app/blog/loader.py` module reads `.md` files from `backend/app/blog/posts/`, parses front-matter (`python-frontmatter`) + body (`mistune`), and returns a `Post` dataclass. Posts are cached in-process and re-read on file mtime change (fast; the file set is small). This module is the single seam the future agent and the routes both depend on.

## Content model

Files: `backend/app/blog/posts/YYYY-MM-DD-<slug>.md`. Drafts live in `backend/app/blog/drafts/` (never routed in production).

Front-matter contract (validated by the loader; missing required field = post skipped + logged):

```yaml
---
title: The Highest-Paying Skills for Data Engineers in 2026   # required
description: A data-backed look at which skills command...     # required, ~155 chars, used for meta + OG
date: 2026-08-07              # required (publish date)
slug: highest-paying-data-engineer-skills   # optional; defaults to filename slug
tags: [salaries, data-engineering]           # optional
related_roles: [data-engineer, ml-engineer]  # optional; slugs → /r/<slug> cards
draft: false                                 # optional; true = excluded from index/routes
source: human | agent                        # optional; provenance for the future agent
---
Markdown body...
```

`related_roles` renders link cards to the existing `/r/<slug>` pages — the internal-linking funnel into the product.

## Routes (all under the blog blueprint)

| Route | Purpose |
|---|---|
| `GET /blog` | Index: published posts, newest first, tag filter chips |
| `GET /blog/<slug>` | A single post (canonical URL) |
| `GET /blog/tag/<tag>` | Posts for a tag (extra indexable pages) |
| `GET /blog/rss.xml` | RSS 2.0 feed of recent posts |
| `POST /blog/subscribe` | Newsletter signup (form post) |
| `GET /blog/unsubscribe/<token>` | One-click unsubscribe |

`draft: true` posts and future-dated posts are excluded from index, tag pages, RSS, and sitemap, and return 404 on direct access in production.

**Sitemap:** extend the existing `/sitemap.xml` generator in `public.py` to also emit blog index, post, and tag URLs (one sitemap, not two).

## Theme & AdSense

- A dedicated **light reading theme**: ~680px measure, large high-contrast headings, comfortable line-height, styled markdown (headings, lists, code, blockquotes, images with `max-width:100%`). Its own CSS, served (not duplicated per page); still lightweight.
- **Reserved ad slots**: top-of-article, one in-article, footer — plus the related-roles block. Rendered as empty containers until AdSense is live.
- **AdSense activation** is config-gated: an env var (e.g. `ADSENSE_CLIENT_ID`) controls whether the AdSense `<script>` (Auto Ads) and slot markup render. Nothing loads pre-approval.
- **`ads.txt`**: static file at `frontend/public/ads.txt` so Vercel serves it at `whatsindemand.com/ads.txt` (AdSense requires root). Content added when the publisher ID is known.
- Rollout sequence: build → publish 3–5 posts → apply to AdSense (needs live content) → set `ADSENSE_CLIENT_ID` + populate `ads.txt`.

## Newsletter (via existing Resend)

- New model `NewsletterSubscriber(id, email UNIQUE, token, created_at, unsubscribed_at NULL)` + an Alembic migration in `backend/migrations/`.
- `POST /blog/subscribe`: validate email, upsert subscriber, send a welcome email via the existing Resend setup, single opt-in. Return a simple success page/partial.
- `GET /blog/unsubscribe/<token>`: set `unsubscribed_at`, confirmation page. Mirrors the existing `auth.py` `digest-unsubscribe` token pattern.
- No double opt-in in v1; every email includes an unsubscribe link.

## Navigation / entry points

- Add a **"Blog"** link to the React app's header and/or footer (`frontend/src/App.js`) → `/blog`. Exact placement confirmed at implementation.
- Every post footer links back to the app and to relevant `/r/` role pages.

## Dependencies

Add to `backend/requirements.txt`: `mistune`, `python-frontmatter`. (Both pure-python, no system deps.)

## Testing

- Unit: front-matter parsing + validation (required fields, draft/future-date exclusion), slug/route resolution, markdown rendering, RSS well-formedness, sitemap includes blog URLs.
- Flow: subscribe → welcome-email call (mock Resend) → unsubscribe token flow.
- Manual: render a sample post locally through Flask (`python run.py`), view `/blog` and `/blog/<slug>`, validate the RSS in a reader, confirm meta/OG tags in page source.

## Phase 2 — Writer Agent (separate spec, not built here)

Recorded so the platform stays compatible; **its own brainstorm → spec → plan cycle**:
- Topic sourcing: SEO/AEO keyword targets + the role-trend analysis data.
- Drafting pipeline (Claude) → writes markdown to `backend/app/blog/drafts/` with `source: agent`.
- **Human-approval gate** before publish (move draft → `posts/`, set `draft: false`), at least until output is trusted.
- Value-density over raw volume — data-driven original-research posts are the crown jewel; generic high-volume AI posts risk Google "scaled content abuse" actions and AdSense rejection that could harm the whole domain.

The platform enables this via: the `loader.py` seam, the `drafts/` folder, and the `source`/`draft` front-matter fields.

## Open items (needed later, not blocking)

- AdSense **publisher ID** (`ca-pub-…`) — once approved.
- Final **nav placement** of the Blog link.
