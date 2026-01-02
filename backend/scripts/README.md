# Scripts Directory

This directory contains utility scripts for maintaining and operating the WhatsInDemand platform.

## Essential Production Scripts

These scripts are used in production or are essential for operations:

- **`weekly_scrape.py`** - Scheduled job scraping (runs via cron)
  - Usage: `python scripts/weekly_scrape.py`
  - Scrapes all companies and updates job database

- **`scrape_single.py`** - Scrape a single company
  - Usage: `python scripts/scrape_single.py <company_slug> [company_name]`
  - Example: `python scripts/scrape_single.py airbnb`

- **`scrape_new_company.py`** - Add a new company to scrape
  - Usage: `python scripts/scrape_new_company.py`
  - Interactive script to add new companies

- **`db_status.py`** - Database status and statistics
  - Usage: `python scripts/db_status.py`
  - Shows table counts, role breakdown, mapping status

## Maintenance Scripts

These scripts are useful for ongoing maintenance:

- **`assign_roles.py`** - Link jobs to roles
  - Usage: `python scripts/assign_roles.py`
  - Assigns role_id to jobs based on title matching

- **`link_jobs_to_roles.py`** - Alternative role linking script
  - Usage: `python scripts/link_jobs_to_roles.py`

- **`update_skill_counts.py`** - Update skill statistics
  - Usage: `python scripts/update_skill_counts.py`
  - Updates total_job_count and trending_score for skills

- **`validate_companies.py`** - Validate company data
  - Usage: `python scripts/validate_companies.py`

- **`validate_slugs.py`** - Validate company slugs
  - Usage: `python scripts/validate_slugs.py`

- **`scrape_all.py`** - Batch scrape all companies
  - Usage: `python scripts/scrape_all.py`

- **`batch_scrape.py`** - Alternative batch scraping
  - Usage: `python scripts/batch_scrape.py`

- **`scrape_greenhouse.py`** - Greenhouse-specific scraping utility
  - Usage: `python scripts/scrape_greenhouse.py`

- **`seed_standard_roles.py`** - Seed initial roles (if needed)
  - Usage: `python scripts/seed_standard_roles.py`

## Utility Scripts

- **`export_job_titles.py`** - Export job titles for analysis
- **`list_jobs.py`** - List jobs with filters
- **`list_roles.py`** - List roles with statistics
- **`discover_greenhouse.py`** - Discover new Greenhouse companies

## Notes

- All debug, test, and diagnostic scripts have been removed
- One-time migration scripts have been removed
- Keep this directory clean - only production/maintenance scripts should remain

