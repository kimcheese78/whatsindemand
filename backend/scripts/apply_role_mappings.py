"""
Apply 45 confirmed role title → canonical role mappings.

For each mapping:
  1. Look up Role by normalized_title
  2. Update jobs with that raw title to set role_id
  3. Upsert RoleTitleVariation
  4. Mark role_candidate as 'approved'

Run: PYTHONPATH=. venv/bin/python scripts/apply_role_mappings.py [--dry-run]
"""
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.getcwd())

DRY_RUN = '--dry-run' in sys.argv

MAPPINGS = [
    ("Program Coordinator, Leads",                                          "Program Manager"),
    ("Industry Solutions Lead, Media & Creatives",                          "Solutions Consultant"),
    ("Third Party Information Security Assessment Lead Assessor",           "Security Operations Analyst"),
    ("Staff Security Analyst, Threat Intelligence",                         "Information Security Engineer"),
    ("Creative Projects Lead, International",                               "Project Manager"),
    ("Primary Care Provider - Sign On Bonus Available",                     "Physician"),
    ("Lead Product Operations",                                             "Product Operations Manager"),
    ("Senior Content Strategist, Global Events",                            "Content Marketing Manager"),
    ("EMEA AE Lead, Beneficial Deployments",                                "Enterprise Account Executive"),
    ("Lead Full Stack Developer, Business Applications",                    "Software Engineer"),
    ("Interim Global Head of Deal Desk",                                    "Revenue Operations Manager"),
    ("Senior Design Technologist - Design Systems",                         "Product Designer"),
    ("Ownership Advisor, Sales",                                            "Account Executive"),
    ("Internal Audit Intern",                                               "Internal Auditor"),
    ("Financial Representative, Travel & Operations",                       "Financial Analyst"),
    ("Channel Manager, DACH [German Fluency]",                              "Partner Manager"),
    ("Deputy Manager, Analytics & Insights",                                "Analytics Engineer"),
    ("Director of TPM, Security",                                           "Technical Program Manager"),
    ("Allbound SDR",                                                        "Sales Development Representative"),
    ("Quality Specialist, Intelligence Systems",                            "QA Engineer"),
    ("Quality Specialist, Intelligence Systems (Secret Clearance)",         "QA Engineer"),
    ("Delivery Excellence Manager, Central",                                "Program Manager"),
    ("Delivery Excellence Manager, East",                                   "Program Manager"),
    ("Lead Data Science Analyst, GTM Strategic Analytics and Insights",     "Data Scientist"),
    ("Buyer II - Fasteners",                                                "Senior Buyer"),
    ("Enterprise Sales Leader",                                             "Sales Manager"),
    ("Recruiting Manager, SDC Operations",                                  "Recruiter"),
    ("Senior Performance Manager, Paid Search",                             "Paid Media Specialist"),
    ("Principal Scientist, TechBio Discovery",                              "Research Scientist"),
    ("Consultant, Developer Platform",                                      "Solutions Consultant"),
    ("International Specialist, Sales",                                     "Account Executive"),
    ("Information Systems Security Officer, AD&S",                          "Information Security Engineer"),
    ("Director of Quality",                                                 "QA Engineer"),
    ("Multinational Digital Infrastructure - Full Stack SW Eng. (US)",      "Software Engineer"),
    ("Member of People Operations",                                         "People Operations Specialist"),
    ("Strategic Sales Operations Lead, Armory",                             "Sales Operations Manager"),
    ("Senior, Cost Accounting",                                             "Accountant"),
    ("Director of Emerging Enterprise, General Business, New Business",     "Sales Manager"),
    ("Director of Data Science & Analytics, User Growth",                   "Data Science Manager"),
    ("Business Operations",                                                 "Business Analyst"),
    ("Customer Support Advocate, Employees",                                "Support Specialist"),
    ("Trust & Safety Senior Associate, Information Security Ops",           "Security Operations Analyst"),
    ("IT Services Team Lead, Deel IT | LATAM",                              "IT Support Engineer"),
    ("HR Generalist",                                                       "HR Business Partner"),
    ("Training Facilitator, Trust & Risk",                                  "People Operations Specialist"),
]


def main():
    from app import create_app
    from app.models import db, Job, Role, RoleTitleVariation, UnmatchedTitle

    app = create_app()
    with app.app_context():
        stats = defaultdict(int)
        missing_roles = []

        for raw_title, canonical in MAPPINGS:
            role = Role.query.filter_by(normalized_title=canonical).first()
            if not role:
                print(f"  ❌ Role not found: '{canonical}'  (for '{raw_title}')")
                missing_roles.append(canonical)
                stats['missing_role'] += 1
                continue

            # 1. Update jobs
            jobs = Job.query.filter_by(title=raw_title).all()
            for job in jobs:
                if not DRY_RUN:
                    job.role_id = role.id
            stats['jobs_updated'] += len(jobs)

            # 2. Upsert RoleTitleVariation
            existing_var = RoleTitleVariation.query.filter_by(original_title=raw_title).first()
            if existing_var:
                if not DRY_RUN:
                    existing_var.role_id = role.id
                    existing_var.frequency += 1
                stats['variations_updated'] += 1
            else:
                if not DRY_RUN:
                    db.session.add(RoleTitleVariation(
                        role_id=role.id,
                        original_title=raw_title,
                        frequency=max(1, len(jobs)),
                    ))
                stats['variations_created'] += 1

            # 3. Mark role_candidate approved
            candidate = UnmatchedTitle.query.filter_by(raw_title=raw_title).first()
            if candidate:
                if not DRY_RUN:
                    candidate.status = 'approved'
                    candidate.mapped_role_id = role.id
                stats['candidates_approved'] += 1
            else:
                stats['candidates_not_found'] += 1

            action = "would map" if DRY_RUN else "mapped"
            print(f"  ✅ {action} '{raw_title}' → '{canonical}' ({len(jobs)} jobs)")

        if not DRY_RUN:
            db.session.commit()

            # Refresh role job counts for affected roles
            affected_role_names = {canonical for _, canonical in MAPPINGS}
            affected_roles = Role.query.filter(Role.normalized_title.in_(affected_role_names)).all()
            for role in affected_roles:
                role.total_active_jobs = Job.query.filter_by(role_id=role.id, is_active=True).count()
            db.session.commit()
            print(f"\n  📊 Updated job counts for {len(affected_roles)} roles")

        print(f"\n{'DRY RUN ' if DRY_RUN else ''}Results:")
        print(f"  Jobs updated:          {stats['jobs_updated']}")
        print(f"  Variations created:    {stats['variations_created']}")
        print(f"  Variations updated:    {stats['variations_updated']}")
        print(f"  Candidates approved:   {stats['candidates_approved']}")
        print(f"  Candidates not found:  {stats['candidates_not_found']}")
        if missing_roles:
            print(f"  Missing roles ({stats['missing_role']}): {missing_roles}")


if __name__ == '__main__':
    main()
