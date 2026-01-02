# backend/scripts/assign_roles.py

from app import create_app
from app.models import db, Job, Role, RoleTitleVariation
from app.utils.role_normalizer import normalize_title

app = create_app()

def get_or_create_role(normalized_data: dict) -> Role:
    """Get existing role or create new one."""
    role = Role.query.filter_by(
        normalized_title=normalized_data['normalized_title']
    ).first()
    
    if not role:
        role = Role(
            normalized_title=normalized_data['normalized_title'],
            category=normalized_data['category'],
            seniority_level=normalized_data['seniority_level'],
            job_family=normalized_data['job_family'],
            total_active_jobs=0
        )
        db.session.add(role)
        db.session.flush()  # Get the ID
    
    return role


def track_title_variation(role: Role, original_title: str):
    """Track the original title as a variation."""
    existing = RoleTitleVariation.query.filter_by(
        original_title=original_title
    ).first()
    
    if existing:
        existing.frequency += 1
    else:
        variation = RoleTitleVariation(
            role_id=role.id,
            original_title=original_title,
            frequency=1
        )
        db.session.add(variation)


def assign_all_roles():
    """Assign roles to all jobs."""
    with app.app_context():
        jobs = Job.query.all()
        total = len(jobs)
        
        print(f"🚀 Processing {total} jobs...")
        print("-" * 50)
        
        stats = {
            'assigned': 0,
            'roles_created': 0,
        }
        
        existing_roles_before = Role.query.count()
        
        for i, job in enumerate(jobs, 1):
            # Normalize the title
            normalized = normalize_title(job.title)
            
            # Get or create the role
            role = get_or_create_role(normalized)
            
            # Track the variation
            track_title_variation(role, job.title)
            
            # Assign to job
            job.role_id = role.id
            role.total_active_jobs += 1
            
            stats['assigned'] += 1
            
            # Progress update every 100 jobs
            if i % 100 == 0:
                print(f"  Processed {i}/{total} jobs...")
                db.session.commit()
        
        # Final commit
        db.session.commit()
        
        existing_roles_after = Role.query.count()
        stats['roles_created'] = existing_roles_after - existing_roles_before
        
        # Print results
        print("\n" + "=" * 50)
        print("✅ COMPLETE!")
        print("=" * 50)
        print(f"  Jobs processed: {stats['assigned']}")
        print(f"  Roles created: {stats['roles_created']}")
        print(f"  Total roles now: {existing_roles_after}")
        
        # Show role distribution
        print("\n📊 TOP ROLES BY JOB COUNT:")
        print("-" * 50)
        top_roles = Role.query.order_by(Role.total_active_jobs.desc()).limit(15).all()
        for role in top_roles:
            print(f"  {role.normalized_title}: {role.total_active_jobs} jobs ({role.category})")
        
        # Show unmapped (should be 0 or minimal)
        unmapped = Job.query.filter(Job.role_id.is_(None)).count()
        mapped = Job.query.filter(Job.role_id.isnot(None)).count()
        pct = mapped * 100 // total if total else 0
        print(f"\n📈 MAPPING RATE: {mapped}/{total} ({pct}%)")
        
        if unmapped > 0:
            print(f"\n⚠️  {unmapped} jobs still unmapped. Sample titles:")
            for job in Job.query.filter(Job.role_id.is_(None)).limit(5).all():
                print(f"    '{job.title}'")


if __name__ == '__main__':
    assign_all_roles()