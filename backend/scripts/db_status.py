# backend/scripts/db_status.py

from app import create_app
from app.models import db, User, Job, Company, Role, RoleTitleVariation, Skill, JobSkill
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("=" * 60)
    print("DATABASE STATUS REPORT")
    print("=" * 60)
    
    # Table counts
    tables = [
        ("Users", User),
        ("Companies", Company),
        ("Jobs", Job),
        ("Roles", Role),
        ("RoleTitleVariations", RoleTitleVariation),
        ("Skills", Skill),
        ("JobSkills", JobSkill),
    ]
    
    print("\n📊 TABLE COUNTS:")
    print("-" * 40)
    for name, model in tables:
        count = model.query.count()
        print(f"  {name}: {count}")
    
    # Role breakdown by category
    print("\n📋 ROLES BY CATEGORY:")
    print("-" * 40)
    categories = db.session.query(
        Role.category, 
        db.func.count(Role.id)
    ).group_by(Role.category).order_by(db.func.count(Role.id).desc()).all()
    
    for category, count in categories:
        print(f"  {category or 'Uncategorized'}: {count} roles")
    
    # Job-to-Role mapping status
    print("\n🔗 JOB-TO-ROLE MAPPING:")
    print("-" * 40)
    total_jobs = Job.query.count()
    mapped_jobs = Job.query.filter(Job.role_id.isnot(None)).count()
    unmapped_jobs = Job.query.filter(Job.role_id.is_(None)).count()
    pct = mapped_jobs * 100 // total_jobs if total_jobs else 0
    print(f"  Total jobs: {total_jobs}")
    print(f"  Mapped to a role: {mapped_jobs} ({pct}%)")
    print(f"  Unmapped: {unmapped_jobs}")
    
    # Top roles by job count
    print("\n📝 TOP ROLES (by job count):")
    print("-" * 40)
    top_roles = Role.query.order_by(Role.total_active_jobs.desc()).limit(15).all()
    for r in top_roles:
        print(f"  {r.normalized_title}: {r.total_active_jobs} jobs ({r.category})")
    
    # Roles in "Other" category (might need normalizer updates)
    print("\n⚠️  ROLES IN 'OTHER' CATEGORY:")
    print("-" * 40)
    other_roles = Role.query.filter_by(category='Other').order_by(Role.total_active_jobs.desc()).limit(10).all()
    if other_roles:
        for r in other_roles:
            print(f"  {r.normalized_title}: {r.total_active_jobs} jobs")
    else:
        print("  None! All roles are categorized.")
    
    # Companies
    print("\n🏢 COMPANIES:")
    print("-" * 40)
    companies = Company.query.all()
    for c in companies:
        job_count = Job.query.filter_by(company_id=c.id).count()
        print(f"  {c.name}: {job_count} jobs")
    
    print("\n" + "=" * 60)