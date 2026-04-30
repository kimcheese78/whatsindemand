# Scripts Directory

Utility scripts for maintaining and operating the WhatsInDemand backend.
One-shot and historical scripts live under `_archive/` (gitignored).

## Production

- **`weekly_scrape.py`** — scheduled full scrape of all companies. Cron entrypoint.
- **`scrape_notifier.sh`** — companion notifier for the weekly scrape.

## Data pipeline — recurring

Run these when taxonomy/data changes or periodically.

- **`rebuild_roles.py`** — normalize and dedupe role titles across jobs.
- **`ingest_lightcast_skills.py`** — ingest Lightcast Open Skills taxonomy into `skills`. Additive; skiplists in-file. `--apply` to persist.
- **`cleanup_generic_skills.py`** — mark overly generic Lightcast skills `is_verified=False` (noise filter). Reversible via `--restore`.
- **`reextract_all_skills.py`** — re-run `SkillExtractor` across all active jobs. Use after any skill-table change.
- **`expand_coverage.py`** — probe + scrape candidate companies across ATSes. Reads `CANDIDATES_MODULE` env var (defaults to `scripts.expansion_candidates`).

## Analytics / validation

- **`demand_snapshot.py`** — 12-query labor-market demand snapshot (top roles, rising roles, skills, categories).
- **`test_extraction_sample.py`** — sample N random jobs and report skill-extraction quality + timing.

## Migrations (already applied, kept for reference)

- **`convert_salaries_to_usd.py`** — one-time salary-to-USD conversion.
- **`extract_salaries.py`** — one-time salary extraction from JDs.

## Archive

`_archive/` holds ~60 one-shot scripts (debug, diagnostics, historical migrations,
consumed candidate batches). Excluded from git; restore anything you need.
