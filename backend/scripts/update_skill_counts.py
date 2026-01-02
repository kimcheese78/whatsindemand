# scripts/update_skill_counts.py

import sys
sys.path.insert(0, '.')

from app import create_app
from app.models import db, Skill, JobSkill
from sqlalchemy import func

app = create_app()

with app.app_context():
    print("🔄 Updating skill counts...")
    
    # Get counts for each skill
    skill_counts = db.session.query(
        JobSkill.skill_id,
        func.count(JobSkill.job_id).label('count')
    ).group_by(JobSkill.skill_id).all()
    
    count_dict = {skill_id: count for skill_id, count in skill_counts}
    
    # Update each skill's total_job_count
    skills = Skill.query.filter_by(is_verified=True).all()
    
    for skill in skills:
        skill.total_job_count = count_dict.get(skill.id, 0)
    
    db.session.commit()
    
    # Show top 20 skills
    top_skills = Skill.query.filter_by(is_verified=True).order_by(Skill.total_job_count.desc()).limit(20).all()
    
    print(f"\n✅ Updated counts for {len(skills)} skills")
    print(f"\n📊 Top 20 Skills by Job Count:")
    print("-" * 40)
    for i, skill in enumerate(top_skills, 1):
        print(f"{i:2}. {skill.name:<25} {skill.total_job_count:>5} jobs")