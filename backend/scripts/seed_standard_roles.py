# backend/scripts/seed_standard_roles.py

"""
Seed database with 50 standard roles based on market analysis
These roles cover 95%+ of tech company job postings
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Role

# 50 Standard Roles (based on your Stripe data + market research)
STANDARD_ROLES = [
    # ============================================
    # ENGINEERING (20 roles)
    # ============================================
    {
        "title": "Software Engineer",
        "category": "Engineering",
        "description": "General software development across all specializations"
    },
    {
        "title": "Backend Engineer",
        "category": "Engineering",
        "description": "Server-side and API development"
    },
    {
        "title": "Frontend Engineer",
        "category": "Engineering",
        "description": "Client-side and UI development"
    },
    {
        "title": "Full Stack Engineer",
        "category": "Engineering",
        "description": "Both frontend and backend development"
    },
    {
        "title": "Mobile Engineer",
        "category": "Engineering",
        "description": "iOS and Android development"
    },
    {
        "title": "DevOps Engineer",
        "category": "Engineering",
        "description": "Infrastructure, deployment, and operations"
    },
    {
        "title": "Data Engineer",
        "category": "Engineering",
        "description": "Data pipelines and infrastructure"
    },
    {
        "title": "Security Engineer",
        "category": "Engineering",
        "description": "Application and infrastructure security"
    },
    {
        "title": "QA Engineer",
        "category": "Engineering",
        "description": "Quality assurance and testing"
    },
    {
        "title": "Machine Learning Engineer",
        "category": "Engineering",
        "description": "ML models and AI systems"
    },
    {
        "title": "Solutions Architect",
        "category": "Engineering",
        "description": "Technical architecture and customer solutions"
    },
    {
        "title": "Engineering Manager",
        "category": "Engineering",
        "description": "Engineering team leadership"
    },
    {
        "title": "Solutions Engineer",
        "category": "Engineering",
        "description": "Technical pre-sales and customer engineering"
    },
    {
        "title": "Site Reliability Engineer",
        "category": "Engineering",
        "description": "Production systems reliability"
    },
    {
        "title": "Platform Engineer",
        "category": "Engineering",
        "description": "Internal platforms and developer tools"
    },
    {
        "title": "Integration Engineer",
        "category": "Engineering",
        "description": "System integrations and APIs"
    },
    {
        "title": "Embedded Engineer",
        "category": "Engineering",
        "description": "Embedded systems and firmware"
    },
    {
        "title": "Hardware Engineer",
        "category": "Engineering",
        "description": "Physical hardware design"
    },
    {
        "title": "Network Engineer",
        "category": "Engineering",
        "description": "Network infrastructure and connectivity"
    },
    {
        "title": "Technical Architect",
        "category": "Engineering",
        "description": "Enterprise technical architecture"
    },
    
    # ============================================
    # PRODUCT (4 roles)
    # ============================================
    {
        "title": "Product Manager",
        "category": "Product",
        "description": "Product strategy and roadmap"
    },
    {
        "title": "Program Manager",
        "category": "Product",
        "description": "Cross-functional program coordination"
    },
    {
        "title": "Technical Program Manager",
        "category": "Product",
        "description": "Technical program management"
    },
    {
        "title": "Product Operations",
        "category": "Product",
        "description": "Product operations and analytics"
    },
    
    # ============================================
    # DATA & AI (3 roles)
    # ============================================
    {
        "title": "Data Scientist",
        "category": "Data & AI",
        "description": "Data analysis and modeling"
    },
    {
        "title": "Data Analyst",
        "category": "Data & AI",
        "description": "Business intelligence and reporting"
    },
    {
        "title": "Business Intelligence Analyst",
        "category": "Data & AI",
        "description": "BI tools and dashboards"
    },
    
    # ============================================
    # DESIGN (3 roles)
    # ============================================
    {
        "title": "Product Designer",
        "category": "Design",
        "description": "UX/UI design"
    },
    {
        "title": "UX Researcher",
        "category": "Design",
        "description": "User research and testing"
    },
    {
        "title": "Design Manager",
        "category": "Design",
        "description": "Design team leadership"
    },
    
    # ============================================
    # SALES (6 roles)
    # ============================================
    {
        "title": "Account Executive",
        "category": "Sales",
        "description": "B2B sales"
    },
    {
        "title": "Sales Development Representative",
        "category": "Sales",
        "description": "Outbound sales development"
    },
    {
        "title": "Account Manager",
        "category": "Sales",
        "description": "Account management and growth"
    },
    {
        "title": "Customer Success Manager",
        "category": "Sales",
        "description": "Customer success and retention"
    },
    {
        "title": "Sales Manager",
        "category": "Sales",
        "description": "Sales team leadership"
    },
    {
        "title": "Sales Operations",
        "category": "Sales",
        "description": "Sales operations and enablement"
    },
    
    # ============================================
    # MARKETING (3 roles)
    # ============================================
    {
        "title": "Marketing Manager",
        "category": "Marketing",
        "description": "Marketing strategy and campaigns"
    },
    {
        "title": "Content Manager",
        "category": "Marketing",
        "description": "Content creation and strategy"
    },
    {
        "title": "Growth Manager",
        "category": "Marketing",
        "description": "Growth marketing and experimentation"
    },
    
    # ============================================
    # OPERATIONS (5 roles)
    # ============================================
    {
        "title": "Operations Manager",
        "category": "Operations",
        "description": "General operations management"
    },
    {
        "title": "Operations Associate",
        "category": "Operations",
        "description": "Operations support and execution"
    },
    {
        "title": "Partnership Manager",
        "category": "Operations",
        "description": "Strategic partnerships"
    },
    {
        "title": "Strategy Manager",
        "category": "Operations",
        "description": "Business strategy and planning"
    },
    {
        "title": "Operations Specialist",
        "category": "Operations",
        "description": "Specialized operations functions"
    },
    
    # ============================================
    # FINANCE (3 roles)
    # ============================================
    {
        "title": "Financial Analyst",
        "category": "Finance",
        "description": "Financial analysis and planning"
    },
    {
        "title": "Accountant",
        "category": "Finance",
        "description": "Accounting and bookkeeping"
    },
    {
        "title": "Accounting Manager",
        "category": "Finance",
        "description": "Accounting team leadership"
    },
    
    # ============================================
    # HR & RECRUITING (2 roles)
    # ============================================
    {
        "title": "Recruiter",
        "category": "HR & Recruiting",
        "description": "Talent acquisition"
    },
    {
        "title": "HR Specialist",
        "category": "HR & Recruiting",
        "description": "Human resources and people operations"
    },
    
    # ============================================
    # LEGAL (1 role)
    # ============================================
    {
        "title": "Legal Counsel",
        "category": "Legal",
        "description": "Legal support and compliance"
    },
]


def seed_roles():
    """Seed database with standard roles"""
    app = create_app()
    
    with app.app_context():
        print("🌱 Seeding standard roles...")
        print("=" * 60)
        
        added = 0
        skipped = 0
        
        for role_data in STANDARD_ROLES:
            # Check if role already exists
            existing = Role.query.filter_by(
                normalized_title=role_data['title']
            ).first()
            
            if existing:
                print(f"   ⏭️  Skipped: {role_data['title']} (already exists)")
                skipped += 1
            else:
                role = Role(
                    normalized_title=role_data['title'],
                    category=role_data['category'],
                    job_family=role_data['title'],
                    seniority_level=None,
                    is_standard=True
                )
                db.session.add(role)
                print(f"   ✅ Added: {role_data['title']}")
                added += 1
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print(f"✨ Seeding complete!")
        print(f"   Added: {added} roles")
        print(f"   Skipped: {skipped} roles (already existed)")
        print(f"   Total standard roles: {len(STANDARD_ROLES)}")
        
        # Show role breakdown by category
        print(f"\n📊 Roles by Category:")
        from collections import Counter
        categories = Counter(r['category'] for r in STANDARD_ROLES)
        for category, count in categories.most_common():
            print(f"   {category}: {count} roles")


if __name__ == '__main__':
    seed_roles()