import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Role, Job
from sqlalchemy import func

app = create_app()

# Write to file
output_file = 'roles_report.txt'

with app.app_context():
    with open(output_file, 'w') as f:
        # All roles with 1-2 jobs (hidden from dropdown)
        hidden_roles = db.session.query(
            Role.normalized_title,
            Role.category,
            Role.job_family,
            func.count(Job.id).label('job_count')
        ).join(Job).filter(Job.is_active == True).group_by(Role.id).having(
            func.count(Job.id) < 3
        ).order_by(
            Role.normalized_title
        ).all()
        
        f.write("=" * 100 + "\n")
        f.write("ROLES WITH 1-2 JOBS (hidden from dropdown)\n")
        f.write("=" * 100 + "\n")
        f.write(f"{'Role':<55} {'Category':<15} {'Jobs'}\n")
        f.write("-" * 100 + "\n")
        
        total_hidden_jobs = 0
        other_count = 0
        
        for r in hidden_roles:
            total_hidden_jobs += r.job_count
            if r.category == 'Other':
                other_count += 1
            f.write(f"{r.normalized_title:<55} {r.category:<15} {r.job_count}\n")
        
        f.write("-" * 100 + "\n")
        f.write(f"Total hidden roles: {len(hidden_roles)}\n")
        f.write(f"Total jobs in hidden roles: {total_hidden_jobs}\n")
        f.write(f"Roles categorized as 'Other': {other_count}\n")
        
        # Summary stats
        f.write("\n" + "=" * 100 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 100 + "\n")
        
        total_roles = Role.query.count()
        total_jobs = Job.query.filter(Job.is_active == True).count()
        jobs_with_roles = Job.query.filter(Job.is_active == True, Job.role_id.isnot(None)).count()
        jobs_without_roles = Job.query.filter(Job.is_active == True, Job.role_id.is_(None)).count()
        
        f.write(f"Total roles in DB: {total_roles}\n")
        f.write(f"Total active jobs: {total_jobs}\n")
        f.write(f"Jobs with role assigned: {jobs_with_roles}\n")
        f.write(f"Jobs without role (role_id = NULL): {jobs_without_roles}\n")
        
        # Category breakdown for hidden roles
        f.write("\n" + "=" * 100 + "\n")
        f.write("HIDDEN ROLES BY CATEGORY\n")
        f.write("=" * 100 + "\n")
        
        category_counts = {}
        for r in hidden_roles:
            cat = r.category or 'None'
            if cat not in category_counts:
                category_counts[cat] = {'roles': 0, 'jobs': 0}
            category_counts[cat]['roles'] += 1
            category_counts[cat]['jobs'] += r.job_count
        
        for cat, data in sorted(category_counts.items(), key=lambda x: x[1]['jobs'], reverse=True):
            f.write(f"{cat:<20} {data['roles']} roles, {data['jobs']} jobs\n")

print(f"Report written to {output_file}")
print(f"View with: cat {output_file}")
print(f"Or open in editor: open {output_file}")