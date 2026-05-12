"""
Handle the 177 job titles with role_id IS NULL that are not in unmatched_titles.

Three passes:
  1. Whitespace fix — titles with leading/trailing spaces that already have an
     approved role_candidate; just update the job rows.
  2. Skip — interns, non-English, placeholder/vague titles → mark rejected.
  3. Map — map to existing canonical roles and insert into unmatched_titles.

Run: PYTHONPATH=. venv/bin/python scripts/fix_not_in_queue.py [--dry-run]
"""
import sys, os
sys.path.insert(0, os.getcwd())

DRY_RUN = '--dry-run' in sys.argv

# ── 1. SKIP ────────────────────────────────────────────────────────────────────
SKIP_TITLES = {
    'Data Science Internship',
    'Ingénieur Plateforme - Infonuagique, LUS',
    'GRC Team Intern (Summer 2026)',
    'Cyber Incident Response/Customer Security Operations - SkillBridge Intern',
    'Geospatial Analysis Intern',
    'Impact Research Intern - Summer 2026',
    'People Analytics Intern',
    'Finance Intern',
    ' Data Science Internship',
    'Summer Trainee, Science',
    'Trainee, HW (Part-time, Fixed-term)',
    'Assistant CRM (H/F) - alternance',
    'Conseiller(ère) au Service (Service Advisor)',
    ' Ingénieur Logiciel Backend',
    '        Ingénieur Plateforme - Infonuagique, LUS',
    'Responsable de marché senior',
    'Operador SPEI -Queretaro',
    'AI Mentor (Independent Contractor) - Business Leader Programs',
    'Tech Talk: AI Fundamentals & Applied AI Mentor',
    'Part Time, The Venetian, Macao',
    'ANDON Tech',
    'Operations Exploratory',
    'Reporter, Axios Local (Phoenix)',        # journalism, out of scope
    'Commercial Agronomist - Crossroads',     # agriculture, niche
    'Animal Husbandry Specialist II, Aviculture',
    'HEDIS Measure Owner (Abstractor)',       # very niche healthcare
    'People Ops Generalist (8 Month Maternity Cover, London)',  # temp cover
    'Program Lead, Cloudflare for Students',  # student program
    'User Operations Generalist - Enterprise Billing & Product (Contract)',
    'Sourcer - Fixed Term',
}

# ── 2. MAP ─────────────────────────────────────────────────────────────────────
MAPPINGS = {
    # Whitespace variants — stripped title already has approved candidate
    # (handled separately below via strip+lookup)

    # Manufacturing / Hardware
    'Friction Stir Welding Technician I, First Shift':     'Manufacturing Technician',
    'Friction Stir Welding Technician II, First Shift':    'Manufacturing Technician',
    'Friction Stir Welding Technician I, Second Shift':    'Manufacturing Technician',
    'Friction Stir Welding Technician II, Second Shift':   'Manufacturing Technician',
    'Fabrication Technician-All Levels':                   'Manufacturing Technician',
    'Propulsion Assembly Technician II/III - B Shift':     'Manufacturing Technician',
    'Propulsion Test Technician III - B Shift':            'Field Service Technician',
    'Assembly Integration and Test Technician III / Senior - B Shift': 'Manufacturing Technician',
    '5 Axis Machinist':                                    'Manufacturing Technician',
    'UAV Operator, Bolt':                                  'Field Service Technician',
    'Vehicle Mechanic - Bronx, NY':                        'Field Service Technician',
    'Federal Materials Associate, FAR/DFAR (1st Shift)':   'Supply Chain Analyst',
    'Federal Materials Associate, FAR/DFAR (2nd Shift)':   'Supply Chain Analyst',
    'PCB Librarian':                                       'Electrical Engineer',
    'Senior PCB Librarian':                                'Electrical Engineer',
    'Senior Structural Analyst, Propulsion':               'Mechanical Engineer',
    'Staff Structural Analyst, Propulsion':                'Mechanical Engineer',
    'Staff Structures Analyst, Omen':                      'Mechanical Engineer',

    # Security / Threat
    'Abuse Investigator':                                  'Security Operations Analyst',
    'Technical CBRN-E  Threat Investigator':               'Security Operations Analyst',
    'Technical Cyber Threat Investigator':                 'Security Operations Analyst',
    'Field CISO, Pacific Northwest':                       'Security Operations Analyst',
    'Staff Security Analyst, Customer Assurance':          'Information Security Engineer',
    'Senior Cyber & IT Risk':                              'Risk Manager',
    'Senior Field Architect, Cyber Physical Assets':       'Security Engineer',
    'EDD Manager Compliance, London COE':                  'Compliance Specialist',
    'Financial Crime Senior Manager, Delivery':            'Security Operations Analyst',
    'Technical Policy Manager, Cyber Harms':               'Security Operations Analyst',

    # Engineering leadership
    'Frontend Infrastructure Team Leader':                 'Engineering Manager',
    'Frontend Team Leader':                                'Engineering Manager',
    'Senior Software Development Manager, Payments':       'Engineering Manager',
    ' Global Head of Technical Scale and Strategy (Field Engineering)': 'Director of Engineering',

    # Solutions / Architecture
    'Senior Observability Architect | PST | Remote':       'Solutions Architect',
    'Senior Observability Architect | Sweden | Remote':    'Solutions Architect',
    'Senior Observability Architect | USA CST| Remote':    'Solutions Architect',
    'Senior Observability Architect | USA EST| Remote':    'Solutions Architect',
    'Solution Architect, Enterprise - Eastern Time Zone':  'Solutions Architect',
    'Field CTO - US West':                                 'Solutions Architect',
    'Advanced Capabilities Analyst, Maritime':             'Solutions Architect',
    ' Global Head of Technical Scale and Strategy (Field Engineering)': 'Director of Engineering',
    'Staff Developer Success Advocate':                    'Developer Relations Engineer',

    # Data / Analytics
    'Lead, Advertising Measurement (London)':              'Analytics Engineer',
    'Lead FP&A Analyst, Consolidations':                   'Financial Analyst',
    'Sr. Finance Analyst, Product Development':            'Financial Analyst',
    'Senior Credit Analyst, Financial Health':             'Financial Analyst',
    'Commercial Senior Analyst, Transformation':           'Data Analyst',
    'Data Operations':                                     'Data Analyst',
    'Principal, Global Insights':                          'Data Analyst',
    'Sr. PLM BOM Analyst, Service':                        'Business Systems Analyst',
    'Lead/Senior Analyst Programmer':                      'Software Engineer',

    # Research / Science
    'Applied Research Lead, Generative Audio':             'Research Scientist',
    'Applied Research Lead, Language':                     'Research Scientist',
    'Applied Research Lead, Model Scaling':                'Research Scientist',
    'Applied Research Lead, Reinforcement Learning':       'Research Scientist',
    'Sr Scientist, Cell Biology':                          'Research Scientist',
    'Catastrophe Modeler':                                 'Research Scientist',

    # Product
    'Principal, Product Strategy':                        'Product Manager',
    ' Senior Product Growth':                             'Product Manager',
    'Senior Product Operations, Fraud':                   'Product Operations Manager',
    'Product Support, Bridge':                            'Product Support Specialist',
    ' Director of Medical Products':                      'Product Manager',

    # Design
    'Director of Advanced Design':                        'Director of Design',
    'Production Designer, Brand':                         'Brand Designer',
    'Sr. Interaction Designer, Visualization Real-Time':  'Product Designer',
    'Game Artist - AI Trainer':                           'Game Designer',

    # Marketing / Comms
    'Full Stack Marketer':                                'Marketing Manager',
    'Media Buying Lead Europe and LatAm (TV/Streaming)':  'Paid Media Specialist',
    'Media Expert':                                       'Paid Media Specialist',
    'Media Relations, Safety Comms':                      'Communications Manager',
    'Lead Community Strategist- Monopoly GO!':            'Marketing Manager',
    'Senior Creative Strategist, Retail (Health & Beauty, Grocery)': 'Marketing Manager',
    'Digital Artist - AI Trainer':                        'Data Analyst',

    # Sales / BD / Partnerships
    'German speaking Sales Lead DACH (d/f/m)':            'Account Executive',
    'Inbound Sales - Italian Market':                     'Account Executive',
    'RVP Account Managment, Emerging Enterprise':         'Enterprise Account Executive',
    'Director of Public Sector Business Development':     'Business Development Manager',
    'Director of Strategic Growth - Defense':             'Business Development Manager',
    'Business Development - Construction':                'Business Development Manager',
    'Outbound BDR - Commercial':                          'Business Development Representative',
    'Partner Development Representative | Accounting':    'Business Development Representative',
    'Partner Development Representative | Alliances':     'Business Development Representative',
    'Partner Business Manager, Netherlands (12 month fixed term contract)': 'Partner Manager',
    'Startup Partner - Northern Europe':                  'Partner Manager',
    'Retail & Consumer Goods APAC Leader':                'Sales Manager',
    'Regional Manager- France and Morocco':               'Sales Manager',

    # Customer Success / Support
    'Customer Activation Manager, Commercial':            'Customer Success Manager',
    'Enterprise Customer Activation Manager | Bill Pay & Procurement': 'Customer Success Manager',
    'Customer Programs Manager, Customer Advisory Boards': 'Customer Success Manager',
    'Overnight Customer Support Advocate (Remote)':       'Support Specialist',
    'Senior Customer Care Specialist (International) - Bilingual English & French': 'Support Specialist',
    'Automations & AI Specialist, Product Support':       'Product Support Specialist',
    'Salesforce - Developer Support':                     'IT Support Engineer',

    # Finance
    'Capital Markets & Investor Relations':               'Finance Manager',
    'Revenue Recognition and GTM Accounting':             'Accountant',
    'Principal, Financial Reporting':                     'Accountant',
    'Technical Accounting & Policy':                      'Accountant',
    'Tax Resolution Team Leader':                         'Tax Manager',
    ' Director of Tax Operations':                        'Tax Manager',
    'Customer Risk Strategy':                             'Risk Manager',
    'Lead, Payment Risk Operations':                      'Risk Manager',
    'Principal - Credit Risk Strategy':                   'Risk Manager',
    'Principal, Credit Risk Strategy':                    'Risk Manager',
    'Senior Finance Business Partner, G&A':               'Finance Manager',
    'Home Equity Loan Originator':                        'Sales Representative',
    'Mortgage Loan Originator, Home Equity':              'Sales Representative',

    # Legal / Compliance
    'Compliance Advisory Manager, Payments':              'Compliance Specialist',
    'Regulatory Solutions Analyst UNE':                   'Compliance Specialist',

    # Operations / Program / Project
    'Director of Manufacturing Operations':               'Operations Manager',
    'Director of Strategy and Planning | United States | Remote': 'Program Manager',
    'Strategic Initiatives, Codex':                       'Program Manager',
    'Strategy and Operations, AI Go-to-market strategy':  'Sales Operations Manager',
    'Launch Manager, Certifications':                     'Program Manager',
    'Program Director, Advanced Effects':                 'Program Manager',
    'Project Lead, Uttar Pradesh':                        'Project Manager',
    'City Manager, Glasgow':                              'Operations Manager',
    'Logistics Specialist, EMEA & APAC':                  'Supply Chain Analyst',
    'Logistics Supervisor 2nd Shift':                     'Operations Manager',
    'Business Operations, Air Dominance and Strike':      'Business Analyst',
    'Business Lead, Life Sciences':                       'Business Analyst',
    'Senior Business Process Analyst, People Operations': 'Business Analyst',
    'Department Manager, Quality':                        'Operations Manager',
    'Department Manager, Galeries Lafayette':             'Retail Store Manager',
    'Studio Manager, Beverly Hills':                      'Office Manager',
    'Air Planning Associate, Hanoi':                      'Supply Chain Analyst',

    # HR / People
    'HRBP, APAC':                                         'HR Business Partner',
    'Senior HRBP - EPD':                                  'HR Business Partner',
    'Senior HRBP, R&D':                                   'HR Business Partner',
    'People Operations - HR Generalist':                  'HR Business Partner',
    'Global Head of Benefits':                            'People Operations Specialist',
    'Recruiting Manager, Production':                     'Recruiter',
    'Technical Instructor, Body Repair Program':          'Learning & Development Manager',

    # IT / Systems
    'Database Administrator, PostgreSQL | LATAM':         'Systems Administrator',

    # Real Estate
    'Experience Partner, Real Estate Leasing and Operations': 'Agent Experience Manager',

    # Events
    'Events Coordinator, Air Dominance & Strike':         'Event Marketing Manager',

    # Delivery / Implementation
    'Delivery Consultant EMEA | Services':                'Implementation Consultant',
    ' Implementation Team Lead LATAM':                    'Implementation Manager',

    # Staff / Principal catch-all
    'Staff Platform Manager, Risk':                       'Risk Manager',
    'Director of Revenue Operations, Consumer':           'Revenue Operations Manager',
    'Director of Tax Operations':                         'Tax Manager',
    'Creative Technologist':                              'Product Designer',
    'Senior Product Growth':                              'Product Manager',
    'Assistant Manager, Inventory':                       'Operations Manager',
    'Quality Technician, Inspection':                     'QA Engineer',
    'Production Associate, Sentry':                       'Manufacturing Technician',
}


def main():
    from app import create_app
    from app.models import db, Job, Role, RoleTitleVariation, UnmatchedTitle
    from datetime import date

    app = create_app()
    with app.app_context():
        today = date.today()
        stats = {'whitespace': 0, 'skipped': 0, 'mapped': 0, 'unknown': 0}

        # Fetch all job titles with no role not in queue
        rows = db.session.execute(db.text("""
            SELECT DISTINCT j.title
            FROM jobs j
            LEFT JOIN unmatched_titles rc ON rc.raw_title = j.title
            WHERE j.role_id IS NULL AND rc.raw_title IS NULL
        """)).fetchall()
        titles = [r[0] for r in rows]
        print(f"Found {len(titles)} titles not in queue")

        for title in titles:
            stripped = title.strip()

            # ── Pass 1: whitespace fix ──────────────────────────────────────
            if stripped != title:
                candidate = UnmatchedTitle.query.filter_by(raw_title=stripped).first()
                if candidate and candidate.status == 'approved' and candidate.mapped_role_id:
                    role = Role.query.get(candidate.mapped_role_id)
                    if role:
                        print(f"  🔧 whitespace fix '{title}' → '{role.normalized_title}'")
                        if not DRY_RUN:
                            Job.query.filter_by(title=title).update({'role_id': role.id})
                        stats['whitespace'] += 1
                        continue

            # ── Pass 2: skip ────────────────────────────────────────────────
            if stripped in SKIP_TITLES:
                print(f"  ⏭️  skip '{title}'")
                if not DRY_RUN:
                    existing = UnmatchedTitle.query.filter_by(raw_title=title).first()
                    if not existing:
                        db.session.add(UnmatchedTitle(
                            raw_title=title, job_count=1, company_count=1,
                            first_seen=today, last_seen=today, status='rejected',
                        ))
                stats['skipped'] += 1
                continue

            # ── Pass 3: map ─────────────────────────────────────────────────
            canonical = MAPPINGS.get(stripped) or MAPPINGS.get(title)
            if canonical:
                role = Role.query.filter_by(normalized_title=canonical).first()
                if not role:
                    print(f"  ❌ Role not found: '{canonical}'")
                    continue
                jobs = Job.query.filter_by(title=title).all()
                print(f"  ✅ map '{title}' → '{canonical}' ({len(jobs)} jobs)")
                if not DRY_RUN:
                    for job in jobs:
                        job.role_id = role.id
                    var = RoleTitleVariation.query.filter_by(original_title=title).first()
                    if not var:
                        db.session.add(RoleTitleVariation(
                            role_id=role.id, original_title=title,
                            frequency=max(1, len(jobs)),
                        ))
                    existing_rc = UnmatchedTitle.query.filter_by(raw_title=title).first()
                    if existing_rc:
                        existing_rc.status = 'approved'
                        existing_rc.mapped_role_id = role.id
                    else:
                        db.session.add(UnmatchedTitle(
                            raw_title=title, job_count=len(jobs), company_count=1,
                            first_seen=today, last_seen=today,
                            status='approved', mapped_role_id=role.id,
                        ))
                stats['mapped'] += 1
                continue

            print(f"  ❓ no rule for '{title}'")
            stats['unknown'] += 1

        if not DRY_RUN:
            db.session.commit()
            # Refresh role job counts
            db.session.execute(db.text("""
                UPDATE roles r
                SET total_active_jobs = (
                    SELECT COUNT(*) FROM jobs j
                    WHERE j.role_id = r.id AND j.is_active = true
                )
            """))
            db.session.commit()

        prefix = "DRY RUN " if DRY_RUN else ""
        print(f"\n{prefix}Results:")
        print(f"  Whitespace fixed: {stats['whitespace']}")
        print(f"  Skipped:          {stats['skipped']}")
        print(f"  Mapped:           {stats['mapped']}")
        print(f"  No rule:          {stats['unknown']}")


if __name__ == '__main__':
    main()
