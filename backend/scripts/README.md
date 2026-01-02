# Scripts Directory

This directory contains utility scripts for maintaining and operating the WhatsInDemand platform.

## Production Scripts

**Essential for deployment:**

- **`weekly_scrape.py`** - Scheduled job scraping (runs via cron)
  - Usage: `python scripts/weekly_scrape.py`
  - Scrapes all companies and updates job database
  - **This is the main production script for keeping data fresh**

## Data Migration Scripts

**One-time use scripts (kept for reference):**

- **`convert_salaries_to_usd.py`** - Convert salaries to USD
  - Usage: `python scripts/convert_salaries_to_usd.py`
  - One-time migration script (already run)
  - Kept in case salary conversion needs to be re-run

- **`extract_salaries.py`** - Extract salaries from job descriptions
  - Usage: `python scripts/extract_salaries.py`
  - One-time migration script (already run)
  - Kept in case salary extraction needs to be re-run

## Archived Scripts

All other scripts (maintenance, debugging, testing, one-time migrations) have been moved to `_archive/` directory:

- Debug/test scripts
- One-time migration scripts
- Maintenance utilities (can be restored if needed)
- Diagnostic tools

The archive is excluded from git (see `.gitignore`) but kept locally for reference.

## Notes

- Only essential production scripts remain in the main directory
- Archive contains 58+ scripts that were used during development
- If you need a specific script from the archive, you can restore it

