# backend/scripts/scrape_single.py

"""
Scrape a single company from Greenhouse.
Usage: python scripts/scrape_single.py <company_slug>

Examples:
    python scripts/scrape_single.py airbnb
    python scripts/scrape_single.py notion
    python scripts/scrape_single.py discord
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db, Company, Job, JobSkill, Role, Skill, ScraperLog
from app.scrapers.greenhouse.scraper import GreenhouseScraper
from app.services.skill_extractor import SkillExtractor
from datetime import datetime


def scrape_company(company_slug: str, company_name: str = None):
    """Scrape a single Greenhouse company and save to database"""
    
    app = create_app()
    
    with app.app_context():
        print(f"\n{'='*60}")
        print(f"🚀 Scraping: {company_slug}")
        print(f"{'='*60}\n")
        
        scraper = GreenhouseScraper()
        skill_extractor = SkillExtractor()
        
        # Step 1: Fetch jobs from API
        print("📡 Fetching jobs from Greenhouse API...")
        jobs = scraper.get_company_jobs(company_slug)
        
        if not jobs:
            print("❌ No jobs found. Check if the company slug is correct.")
            print(f"   Try: https://boards.greenhouse.io/{company_slug}")
            return
        
        print(f"✅ Found {len(jobs)} jobs\n")
        
        # Step 2: Get or create company
        company = Company.query.filter_by(greenhouse_slug=company_slug).first()
        
        if not company:
            company = Company(
                name=company_name or company_slug.replace("-", " ").title(),
                ats_type="greenhouse",
                greenhouse_slug=company_slug,
                is_active=True,
                scrape_enabled=True
            )
            db.session.add(company)
            db.session.flush()
            print(f"📝 Created new company: {company.name}")
        else:
            print(f"📋 Found existing company: {company.name}")
        
        # Step 3: Process jobs
        started_at = datetime.utcnow()
        stats = {
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "skills_extracted": 0
        }
        
        print(f"\n{'─'*60}")
        print("Processing jobs...")
        print(f"{'─'*60}\n")
        
        for i, job_data in enumerate(jobs, 1):
            try:
                result = save_job(job_data, company, skill_extractor)
                stats[result["status"]] += 1
                stats["skills_extracted"] += result.get("skills", 0)
                
                # Progress indicator
                if i % 10 == 0 or i == len(jobs):
                    print(f"  Processed {i}/{len(jobs)} jobs...")
                    
            except Exception as e:
                print(f"  ⚠ Error on job {job_data.get('title', 'Unknown')}: {e}")
                continue
        
        # Step 4: Update company stats
        company.last_scraped_at = datetime.utcnow()
        company.total_jobs_scraped = Job.query.filter_by(
            company_id=company.id,
            is_active=True
        ).count()
        
        # Step 5: Log the scrape
        duration = (datetime.utcnow() - started_at).total_seconds()
        log = ScraperLog(
            company_id=company.id,
            scrape_type="full",
            status="success",
            jobs_found=len(jobs),
            jobs_new=stats["new"],
            jobs_updated=stats["updated"],
            started_at=started_at,
            completed_at=datetime.utcnow(),
            duration_seconds=duration
        )
        db.session.add(log)
        
        db.session.commit()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"✅ SCRAPE COMPLETE: {company.name}")
        print(f"{'='*60}")
        print(f"  Jobs found:      {len(jobs)}")
        print(f"  New jobs:        {stats['new']}")
        print(f"  Updated:         {stats['updated']}")
        print(f"  Unchanged:       {stats['unchanged']}")
        print(f"  Skills linked:   {stats['skills_extracted']}")
        print(f"  Duration:        {duration:.1f}s")
        print(f"{'='*60}\n")
        
        # Show total stats
        total_jobs = Job.query.filter_by(is_active=True).count()
        total_companies = Company.query.count()
        total_skills = JobSkill.query.count()
        
        print(f"📊 Database totals:")
        print(f"   {total_jobs} jobs | {total_companies} companies | {total_skills} job-skill links\n")


def save_job(job_data: dict, company, skill_extractor) -> dict:
    """Save a single job to the database"""
    
    result = {"status": "unchanged", "skills": 0}
    
    # Check for existing
    existing = Job.query.filter_by(
        source_ats="greenhouse",
        source_job_id=job_data["source_job_id"]
    ).first()
    
    if existing:
        # Check if description changed
        old_len = len(existing.description_text or "")
        new_len = len(job_data.get("description_text") or "")
        
        if abs(old_len - new_len) > 100:
            existing.description = job_data.get("description")
            existing.description_text = job_data.get("description_text")
            existing.title = job_data.get("title")
            existing.scraped_at = datetime.utcnow()
            result["status"] = "updated"
        
        return result
    
    # Get or create normalized role
    role = None
    normalized_title = job_data.get("role_normalized_title")
    
    if normalized_title:
        role = Role.query.filter_by(normalized_title=normalized_title).first()
        
        if not role:
            role = Role(
                normalized_title=normalized_title,
                category=job_data.get("role_category"),
                job_family=job_data.get("role_job_family"),
                seniority_level=job_data.get("seniority_level"),
                total_active_jobs=0
            )
            db.session.add(role)
            db.session.flush()
    
    # Create job
    job = Job(
        company_id=company.id,
        role_id=role.id if role else None,
        source_ats="greenhouse",
        source_job_id=job_data["source_job_id"],
        source_url=job_data.get("source_url"),
        title=job_data.get("title"),
        location_raw=job_data.get("location_raw"),
        location_city=job_data.get("location_city"),
        location_state=job_data.get("location_state"),
        location_country=job_data.get("location_country"),
        location_is_remote=job_data.get("location_is_remote", False),
        department=job_data.get("department"),
        seniority_level=job_data.get("seniority_level"),
        description=job_data.get("description"),
        description_text=job_data.get("description_text"),
        posted_at=job_data.get("posted_at"),
        scraped_at=datetime.utcnow(),
        is_active=True
    )
    db.session.add(job)
    db.session.flush()
    
    # Extract skills
    if job_data.get("description_text"):
        extracted = skill_extractor.extract_skills(
            job_data["description_text"],
            company_name=company.name
        )
        
        for skill_data in extracted:
            job_skill = JobSkill(
                job_id=job.id,
                skill_id=skill_data["skill_id"],
                is_required=(skill_data["confidence"] >= 80)
            )
            db.session.add(job_skill)
            result["skills"] += 1
            
            # Update skill count
            skill = Skill.query.get(skill_data["skill_id"])
            if skill:
                skill.total_job_count = (skill.total_job_count or 0) + 1
    
    # Update role count
    if role:
        role.total_active_jobs = (role.total_active_jobs or 0) + 1
    
    result["status"] = "new"
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n❌ Please provide a company slug")
        print("\nUsage: python scripts/scrape_single.py <company_slug> [company_name]")
        print("\nExamples:")
        print("  python scripts/scrape_single.py airbnb")
        print("  python scripts/scrape_single.py airbnb Airbnb")
        print("  python scripts/scrape_single.py notion Notion")
        print("  python scripts/scrape_single.py discord Discord")
        print("\nPopular Greenhouse companies:")
        print("  airbnb, notion, discord, coinbase, dropbox, spotify,")
        print("  doordash, instacart, plaid, robinhood, gusto, brex")
        sys.exit(1)
    
    slug = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else None
    
    scrape_company(slug, name)