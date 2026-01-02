# backend/scripts/link_jobs_to_roles.py

"""
Link existing jobs to normalized roles
Run after creating the roles table
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Job, Role, RoleTitleVariation
from app.utils.role_normalizer import RoleNormalizer

def link_existing_jobs():
    """Process all existing jobs and link them to roles"""
    app = create_app()
    
    with app.app_context():
        print("🔗 Linking existing jobs to normalized roles...")
        print("=" * 60)
        
        normalizer = RoleNormalizer()
        
        # Get all jobs
        jobs = Job.query.filter_by(is_active=True).all()
        total_jobs = len(jobs)
        
        print(f"\n📊 Found {total_jobs} active jobs to process")
        print()
        
        processed = 0
        linked = 0
        errors = 0
        
        for i, job in enumerate(jobs, 1):
            if i % 50 == 0:
                print(f"   Progress: {i}/{total_jobs} ({int(i/total_jobs*100)}%)")
                db.session.commit()  # Commit in batches
            
            try:
                # Get or create role
                role = normalizer.normalize_and_get_role(job.title)
                
                if role:
                    job.role_id = role.id
                    linked += 1
                
                processed += 1
                
            except Exception as e:
                print(f"   ⚠️  Error processing job {job.id} '{job.title}': {e}")
                errors += 1
                continue
        
        # Final commit
        db.session.commit()
        
        print("\n" + "=" * 60)
        print("✅ Job linking completed!")
        print("=" * 60)
        print(f"   Total Jobs: {total_jobs}")
        print(f"   Processed: {processed}")
        print(f"   Linked: {linked}")
        print(f"   Errors: {errors}")
        print(f"   Success Rate: {int(linked/total_jobs*100) if total_jobs > 0 else 0}%")
        
        # Show role stats
        print(f"\n📈 Role Statistics:")
        print("=" * 60)
        roles = Role.query.all()
        print(f"   Total Unique Roles: {len(roles)}")
        print(f"   Total Title Variations: {RoleTitleVariation.query.count()}")
        
        # Top 10 roles
        print(f"\n🔝 Top 10 Roles:")
        top_roles = db.session.query(
            Role.normalized_title,
            Role.category,
            Role.seniority_level,
            db.func.count(Job.id).label('job_count')
        ).join(Job).group_by(Role.id).order_by(db.func.count(Job.id).desc()).limit(10).all()
        
        for idx, (title, category, seniority, count) in enumerate(top_roles, 1):
            print(f"   {idx}. {title} ({category}, {seniority}): {count} jobs")

if __name__ == '__main__':
    link_existing_jobs()