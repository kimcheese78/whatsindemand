# backend/scripts/export_job_titles.py

"""
Export all job titles to CSV for review.
Usage: python scripts/export_job_titles.py
"""

import sys
import os
import csv
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import Job, Role, Company


def export_job_titles():
    app = create_app()
    
    with app.app_context():
        # Query all jobs with their roles and companies
        jobs = Job.query.filter_by(is_active=True).all()
        
        # Create filename with timestamp
        filename = f"job_titles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'original_title',
                'normalized_title',
                'category',
                'job_family',
                'seniority_level',
                'company',
                'job_id'
            ])
            
            # Data
            for job in jobs:
                writer.writerow([
                    job.title,
                    job.role.normalized_title if job.role else 'NO ROLE',
                    job.role.category if job.role else '',
                    job.role.job_family if job.role else '',
                    job.seniority_level or '',
                    job.company.name if job.company else '',
                    job.id
                ])
        
        print(f"✅ Exported {len(jobs)} jobs to {filename}")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Total jobs: {len(jobs)}")
        
        no_role = sum(1 for j in jobs if not j.role)
        print(f"   Jobs without role: {no_role}")
        
        other_category = sum(1 for j in jobs if j.role and j.role.category == 'Other')
        print(f"   Jobs in 'Other' category: {other_category}")


if __name__ == "__main__":
    export_job_titles()