# backend/scripts/scrape_new_company.py

from app import create_app
from app.models import db, Job, Role, RoleTitleVariation, Company
from app.services.job_aggregator import JobAggregator

app = create_app()

with app.app_context():
    # Before stats
    print("📊 BEFORE SCRAPING:")
    print(f"  Jobs: {Job.query.count()}")
    print(f"  Roles: {Role.query.count()}")
    print(f"  Companies: {Company.query.count()}")
    
    # Scrape a new company
    # Pick one from: https://github.com/sudheerj/companies-using-greenhouse
    # Some smaller ones to test with:
    #   - "figma" (~50-100 jobs)
    #   - "notion" (~50-100 jobs)
    #   - "linear" (~20-50 jobs)
    #   - "vercel" (~30-50 jobs)
    
    aggregator = JobAggregator()
    
    company_name = "Figma"
    company_slug = "figma"  # This is the Greenhouse board ID
    
    print(f"\n🚀 Scraping {company_name}...")
    saved_count = aggregator.scrape_company_jobs(company_name, company_slug)
    
    # After stats
    print(f"\n📊 AFTER SCRAPING:")
    print(f"  Jobs: {Job.query.count()}")
    print(f"  Roles: {Role.query.count()}")
    print(f"  Companies: {Company.query.count()}")
    print(f"  New jobs saved: {saved_count}")
    
    # Show new roles created
    print(f"\n📋 TOP ROLES (by job count):")
    top_roles = Role.query.order_by(Role.total_active_jobs.desc()).limit(10).all()
    for role in top_roles:
        print(f"  {role.normalized_title}: {role.total_active_jobs} jobs ({role.category})")
    
    # Check mapping rate
    total = Job.query.count()
    mapped = Job.query.filter(Job.role_id.isnot(None)).count()
    print(f"\n📈 MAPPING RATE: {mapped}/{total} ({mapped*100//total}%)")