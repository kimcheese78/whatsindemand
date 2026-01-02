# scripts/list_jobs.py
"""
Query jobs from the database.

Run with:
  cd backend
  python scripts/list_jobs.py
"""

import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Job


def list_entry_pm_jobs():
    """List entry-level Product Manager jobs in the United States."""
    
    print("=" * 70)
    print("ENTRY-LEVEL PRODUCT MANAGER JOBS - UNITED STATES")
    print("=" * 70)
    print()
    
    # Query for entry-level PM jobs in US
    jobs = Job.query.filter(
        Job.title.ilike('%product manager%'),
        Job.seniority_level.ilike('%entry%'),
        db.or_(
            Job.location_country.ilike('%united states%'),
            Job.location_country.ilike('%usa%'),
            Job.location_country.ilike('%us%'),
            Job.location_raw.ilike('%united states%'),
            Job.location_raw.ilike('%, us%'),
            Job.location_is_remote == True,  # Remote jobs often US-based
        )
    ).order_by(Job.posted_at.desc()).all()
    
    if not jobs:
        print("No entry-level Product Manager jobs found in the US.")
        print("\nLet's check what we have in the database...")
        
        # Debug: Show what jobs exist
        all_pm_jobs = Job.query.filter(Job.title.ilike('%product manager%')).limit(10).all()
        if all_pm_jobs:
            print(f"\nFound {len(all_pm_jobs)} PM jobs (any seniority/location):")
            for job in all_pm_jobs:
                print(f"  - {job.title}")
                print(f"    Seniority: {job.seniority_level}")
                print(f"    Location: {job.location_country} / {job.location_raw}")
                print()
        
        # Show distinct seniority levels
        seniorities = db.session.query(Job.seniority_level).distinct().all()
        print(f"Available seniority levels: {[s[0] for s in seniorities]}")
        
        # Show distinct countries
        countries = db.session.query(Job.location_country).distinct().limit(20).all()
        print(f"Available countries: {[c[0] for c in countries if c[0]]}")
        
        return
    
    print(f"Found {len(jobs)} jobs:\n")
    print("-" * 70)
    
    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job.title}")
        print(f"   Company:   {job.company.name if job.company else 'N/A'}")
        print(f"   Location:  {job.location_city or ''}, {job.location_state or ''}, {job.location_country or ''}")
        if job.location_is_remote:
            print(f"              (Remote)")
        print(f"   Seniority: {job.seniority_level}")
        if job.salary_min and job.salary_max:
            print(f"   Salary:    ${job.salary_min:,} - ${job.salary_max:,} {job.salary_currency}")
        if job.source_url:
            print(f"   URL:       {job.source_url}")
        print(f"   Posted:    {job.posted_at.strftime('%Y-%m-%d') if job.posted_at else 'N/A'}")
        print(f"   ID:        {job.id}")
        print("-" * 70)
    
    print(f"\nTotal: {len(jobs)} entry-level PM jobs in the US")


if __name__ == '__main__':
    app = create_app('development')
    
    with app.app_context():
        list_entry_pm_jobs()