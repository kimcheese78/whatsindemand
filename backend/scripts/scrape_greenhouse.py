# scripts/scrape_greenhouse.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from datetime import datetime

from app import create_app, db
from app.models import Company, Job, Skill, JobSkill, Role, RoleTitleVariation
from app.scrapers.greenhouse.scraper import GreenhouseScraper
from app.scrapers.greenhouse.companies import GREENHOUSE_COMPANIES
from app.services.skill_extractor import SkillExtractor

# Create skill extractor instance
skill_extractor = SkillExtractor()


def get_existing_company_slugs():
    """Get slugs of companies already in database"""
    companies = Company.query.filter(Company.greenhouse_slug.isnot(None)).all()
    return {c.greenhouse_slug for c in companies}


def get_or_create_company(name: str, slug: str, industry: str):
    """Get existing company or create new one"""
    company = Company.query.filter(
        (Company.name == name) | (Company.greenhouse_slug == slug)
    ).first()
    
    if not company:
        company = Company(
            name=name,
            greenhouse_slug=slug,
            industry=industry,
            created_at=datetime.utcnow()
        )
        db.session.add(company)
        db.session.commit()
        print(f"  ✨ Created company: {name}")
    else:
        # Update missing fields
        if not company.greenhouse_slug:
            company.greenhouse_slug = slug
        if not company.industry and industry:
            company.industry = industry
        db.session.commit()
    
    return company


def get_or_create_role(job_data: dict):
    """Get or create a Role and return its ID"""
    normalized_title = job_data.get('role_normalized_title')
    
    if not normalized_title:
        return None
    
    # Check if role exists
    role = Role.query.filter_by(normalized_title=normalized_title).first()
    
    if not role:
        role = Role(
            normalized_title=normalized_title,
            category=job_data.get('role_category'),
            seniority_level=job_data.get('seniority_level'),
            job_family=job_data.get('role_job_family'),
        )
        db.session.add(role)
        db.session.flush()
    
    # Track the original title variation
    original_title = job_data.get('title')
    if original_title and original_title.lower() != normalized_title.lower():
        variation = RoleTitleVariation.query.filter_by(original_title=original_title).first()
        if not variation:
            variation = RoleTitleVariation(
                role_id=role.id,
                original_title=original_title,
                frequency=1
            )
            db.session.add(variation)
        else:
            variation.frequency += 1
    
    return role.id


def job_exists(source_job_id: str) -> bool:
    """Check if job already exists"""
    return Job.query.filter_by(
        source_ats='greenhouse',
        source_job_id=source_job_id
    ).first() is not None


def save_job(job_data: dict, company: Company) -> Job:
    """Save job to database"""
    
    # Get or create the normalized role
    role_id = get_or_create_role(job_data)
    
    job = Job(
        company_id=company.id,
        role_id=role_id,
        source_ats=job_data['source_ats'],
        source_job_id=job_data['source_job_id'],
        source_url=job_data['source_url'],
        title=job_data['title'],
        location_raw=job_data['location_raw'],
        location_city=job_data['location_city'],
        location_state=job_data['location_state'],
        location_country=job_data['location_country'],
        location_is_remote=job_data['location_is_remote'],
        department=job_data['department'],
        seniority_level=job_data['seniority_level'],
        description=job_data['description'],
        description_text=job_data['description_text'],
        posted_at=job_data['posted_at'],
        scraped_at=job_data['scraped_at'],
    )
    db.session.add(job)
    return job


def extract_and_save_skills(job: Job, description_text: str, company_name: str = None):
    """Extract skills and save to database"""
    try:
        extracted = skill_extractor.extract_skills(description_text, company_name)
        
        for skill_data in extracted:
            skill_id = skill_data.get('skill_id')
            
            if skill_id:
                exists = JobSkill.query.filter_by(job_id=job.id, skill_id=skill_id).first()
                if not exists:
                    db.session.add(JobSkill(job_id=job.id, skill_id=skill_id))
                    
    except Exception as e:
        print(f"    ⚠ Skill extraction error: {e}")


def scrape_company(scraper: GreenhouseScraper, company_info: dict) -> dict:
    """Scrape a single company and save to DB"""
    slug = company_info["slug"]
    name = company_info["name"]
    industry = company_info["industry"]
    
    print(f"\n{'='*60}")
    print(f"🏢 {name} ({slug})")
    print(f"   Industry: {industry}")
    print(f"{'='*60}")
    
    # Get or create company
    company = get_or_create_company(name, slug, industry)
    
    # Fetch jobs from Greenhouse
    jobs = scraper.get_company_jobs(slug)
    
    if not jobs:
        return {"company": name, "new": 0, "skipped": 0, "failed": 0}
    
    stats = {"company": name, "new": 0, "skipped": 0, "failed": 0}
    
    for job_data in jobs:
        try:
            # Skip if already exists
            if job_exists(job_data['source_job_id']):
                stats['skipped'] += 1
                continue
            
            # Save job
            job = save_job(job_data, company)
            db.session.flush()
            
            # Extract skills
            if job_data.get('description_text'):
                extract_and_save_skills(job, job_data['description_text'], name)
            
            stats['new'] += 1
            
        except Exception as e:
            print(f"    ❌ Error saving job: {e}")
            stats['failed'] += 1
            db.session.rollback()
    
    db.session.commit()
    
    # Update company stats
    company.last_scraped_at = datetime.utcnow()
    company.total_jobs_scraped = Job.query.filter_by(company_id=company.id).count()
    db.session.commit()
    
    print(f"  📊 {stats['new']} new, {stats['skipped']} skipped, {stats['failed']} failed")
    return stats


def main():
    parser = argparse.ArgumentParser(description='Scrape Greenhouse jobs')
    parser.add_argument('--company', '-c', help='Scrape specific company (slug)')
    parser.add_argument('--new-only', '-n', action='store_true', help='Only new companies')
    parser.add_argument('--all', '-a', action='store_true', help='Scrape all companies')
    parser.add_argument('--dry-run', '-d', action='store_true', help='Show what would be scraped')
    parser.add_argument('--limit', '-l', type=int, help='Limit number of companies')
    parser.add_argument('--list', action='store_true', help='List all companies')
    
    args = parser.parse_args()
    
    # List companies (no DB needed)
    if args.list:
        print(f"\n📋 {len(GREENHOUSE_COMPANIES)} companies available:\n")
        for c in GREENHOUSE_COMPANIES:
            print(f"  • {c['slug']}: {c['name']} ({c['industry']})")
        return
    
    # Need an action
    if not (args.company or args.new_only or args.all):
        parser.print_help()
        return
    
    # Start Flask app context
    app = create_app()
    
    with app.app_context():
        scraper = GreenhouseScraper()
        
        # Determine companies to scrape
        if args.company:
            company_info = next(
                (c for c in GREENHOUSE_COMPANIES if c["slug"] == args.company),
                None
            )
            if not company_info:
                print(f"❌ Unknown slug: {args.company}")
                print("   Use --list to see available companies")
                return
            companies_to_scrape = [company_info]
        else:
            companies_to_scrape = GREENHOUSE_COMPANIES.copy()
        
        # Filter to new only
        if args.new_only or args.all:
            existing = get_existing_company_slugs()
            before = len(companies_to_scrape)
            companies_to_scrape = [c for c in companies_to_scrape if c["slug"] not in existing]
            print(f"📋 {len(companies_to_scrape)} new companies (skipping {before - len(companies_to_scrape)} existing)")
        
        # Apply limit
        if args.limit:
            companies_to_scrape = companies_to_scrape[:args.limit]
        
        # Dry run
        if args.dry_run:
            print(f"\n🔍 Would scrape {len(companies_to_scrape)} companies:\n")
            for c in companies_to_scrape:
                print(f"  • {c['name']} ({c['slug']})")
            return
        
        # Scrape!
        print(f"\n🚀 Scraping {len(companies_to_scrape)} companies...\n")
        
        all_stats = []
        for company_info in companies_to_scrape:
            try:
                stats = scrape_company(scraper, company_info)
                all_stats.append(stats)
                time.sleep(2)
            except Exception as e:
                print(f"❌ Error with {company_info['name']}: {e}")
                all_stats.append({"company": company_info["name"], "new": 0, "skipped": 0, "failed": 1})
        
        # Summary
        print(f"\n{'='*60}")
        print("📈 SUMMARY")
        print(f"{'='*60}")
        print(f"Companies: {len(all_stats)}")
        print(f"New jobs: {sum(s['new'] for s in all_stats):,}")
        print(f"Skipped: {sum(s['skipped'] for s in all_stats):,}")
        print(f"Failed: {sum(s['failed'] for s in all_stats):,}")


if __name__ == "__main__":
    main()