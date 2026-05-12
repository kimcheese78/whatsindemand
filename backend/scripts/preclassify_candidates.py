"""
Rule-based pre-classifier for pending unmatched_titles.

Handles obvious cases without AI:
  - Interns / fellowships / rotational programs / grad programs → skip
  - Non-English titles → skip
  - Clear seniority+function variants → map_to existing role

Writes data/preclassified.csv and prints a summary.
Remaining (needs_review) titles go to data/needs_ai_review.csv.

Run: PYTHONPATH=. venv/bin/python scripts/preclassify_candidates.py [--apply]
"""
import sys, os, csv, re
sys.path.insert(0, os.getcwd())

APPLY = '--apply' in sys.argv

INPUT_CSV      = 'data/pending_candidates.csv'
PRE_OUT_CSV    = 'data/preclassified.csv'
REVIEW_OUT_CSV = 'data/needs_ai_review.csv'

# ── SKIP patterns ──────────────────────────────────────────────────────────────
SKIP_SUBSTRINGS = [
    'intern', 'internship', 'fellowship', 'fellow program', 'fellows program',
    'rotational program', 'rotation program', 'associate program', 'apprentice',
    'apprenticeship', 'co-op', 'coop ', 'summer 2026', 'fall 2026', 'spring 2026',
    'winter 2026', 'summer 2025', 'new grad', 'new/recent grad', 'recent grad',
    'graduate program', 'early talent', 'campus recruit',
    'year at palantir',
    'brex rotational', 'circleci associate rotation',
    'neurodivergent fellowship',
    'american tech fellowship',
    'anthropic fellows', 'anthropic stem fellow',
    '[2026]',
    'working student',
    'alternance',
    'stage ',
    'freelance', 'project-based',
    '(temp)', '- temp', 'temp)',
    '(1099)',
    '12-month duration',          # e.g. "Autonomous Vehicle Operator (12-Month Duration)"
    '(6 month',                   # explicit short-term contract in parens
    # Residency / non-standard programs
    'in residence', 'ai builder resident', 'ai fellow',
    # Junk / culture titles
    'sorcerer', 'wizard', 'ninja', 'rockstar', 'evangelist',
    # Per diem / float positions
    'per diem', 'float ',
    # College creator programs
    'college creator',
    # Specific placeholder-like programs
    'helix data creator',
    # Education roles (out of scope for tech job market)
    'assistant teacher', 'assistant coach',
    # Creator outreach contractor
    'creator outreach associate contractor',
]

# Non-ASCII heuristic for detecting non-English titles
def _is_non_english(title: str) -> bool:
    non_ascii = sum(1 for c in title if ord(c) > 127)
    return non_ascii / max(len(title), 1) > 0.15

# Extra non-English keywords
NON_ENGLISH_KEYWORDS = [
    'chef de', 'commerciale', 'consultor', 'conseiller', 'animateur',
    'coordinador', 'approvisionnement', 'opérations',
    # Note: "fluent spanish/french/etc." is a language requirement, not a non-English title — do NOT skip
]


def should_skip(title: str) -> bool:
    t = title.lower()
    if _is_non_english(title):
        return True
    for kw in SKIP_SUBSTRINGS:
        if kw in t:
            return True
    for kw in NON_ENGLISH_KEYWORDS:
        if kw in t:
            return True
    return False


# ── MAP_TO patterns (title → canonical role) ──────────────────────────────────
# Each entry: (substring_to_match, canonical_role)
# Order matters — first match wins.
MAP_RULES = [
    # Software Engineering — put 'full stack engineer/developer' BEFORE generic 'full stack'
    # to avoid 'Full Stack Marketer' matching
    ('full stack engineer', 'Software Engineer'),
    ('full stack developer', 'Software Engineer'),
    ('full stack sw', 'Software Engineer'),
    ('fullstack engineer', 'Software Engineer'),
    ('fullstack developer', 'Software Engineer'),
    ('backend engineer', 'Software Engineer'),
    ('front-end engineer', 'Software Engineer'),
    ('frontend engineer', 'Software Engineer'),
    ('software developer', 'Software Engineer'),
    ('software engineer', 'Software Engineer'),
    ('ios engineer', 'Mobile Engineer'),
    ('android engineer', 'Mobile Engineer'),
    ('mobile engineer', 'Mobile Engineer'),
    ('ios developer', 'Mobile Engineer'),
    ('android developer', 'Mobile Engineer'),
    # ML/AI
    ('machine learning engineer', 'Machine Learning Engineer'),
    ('ml engineer', 'Machine Learning Engineer'),
    ('ai engineer', 'AI Engineer'),
    ('applied ai engineer', 'Applied AI Engineer'),
    ('ai infrastructure', 'AI Infrastructure Engineer'),
    ('research engineer', 'Research Engineer'),
    ('applied scientist', 'Applied Scientist'),
    ('research scientist', 'Research Scientist'),
    # Director/VP/Head of Data Science → manager role
    ('director of data science', 'Data Science Manager'),
    ('vp of data science', 'Data Science Manager'),
    ('head of data science', 'Data Science Manager'),
    ('data science manager', 'Data Science Manager'),
    ('data scientist', 'Data Scientist'),
    ('data science', 'Data Scientist'),
    # Data
    ('data engineer', 'Data Engineer'),
    ('analytics engineer', 'Analytics Engineer'),
    ('data analyst', 'Data Analyst'),
    # Infrastructure / DevOps
    ('site reliability', 'Site Reliability Engineer'),
    ('sre ', 'Site Reliability Engineer'),
    ('devops', 'DevOps Engineer'),
    ('platform engineer', 'Platform Engineer'),
    ('infrastructure engineer', 'Infrastructure Engineer'),
    ('cloud engineer', 'Cloud Engineer'),
    ('network engineer', 'Network Engineer'),
    # Security
    ('security engineer', 'Security Engineer'),
    ('appsec', 'Application Security Engineer'),
    ('application security', 'Application Security Engineer'),
    ('cloud security', 'Cloud Security Engineer'),
    ('product security', 'Product Security Engineer'),
    ('information security', 'Information Security Engineer'),
    ('infosec', 'Information Security Engineer'),
    ('cybersecurity', 'Security Engineer'),
    ('cyber security', 'Security Engineer'),
    ('security operations', 'Security Operations Analyst'),
    ('threat intelligence', 'Security Operations Analyst'),
    # Hardware
    ('electrical engineer', 'Electrical Engineer'),
    ('mechanical engineer', 'Mechanical Engineer'),
    ('fpga', 'FPGA Engineer'),
    ('robotics engineer', 'Robotics Engineer'),
    ('systems engineer', 'Systems Engineer'),
    ('manufacturing engineer', 'Manufacturing Engineer'),
    # Product
    ('product manager', 'Product Manager'),
    ('product owner', 'Product Manager'),
    ('technical product manager', 'Technical Product Manager'),
    ('group product manager', 'Group Product Manager'),
    ('director of product', 'Director of Product'),
    ('vp of product', 'Director of Product'),
    ('head of product', 'Director of Product'),
    ('product operations', 'Product Operations Manager'),
    # Design
    ('product designer', 'Product Designer'),
    ('ux designer', 'UX Designer'),
    ('ui designer', 'UX Designer'),
    ('ux/ui', 'UX Designer'),
    ('brand designer', 'Brand Designer'),
    ('graphic designer', 'Graphic Designer'),
    ('motion designer', 'Motion Designer'),
    ('creative director', 'Creative Director'),
    ('design director', 'Design Director'),
    ('content designer', 'Content Designer'),
    ('ux researcher', 'UX Researcher'),
    # Sales
    ('enterprise account executive', 'Enterprise Account Executive'),
    ('mid-market account executive', 'Mid-Market Account Executive'),
    ('commercial account executive', 'Commercial Account Executive'),
    ('strategic account executive', 'Strategic Account Executive'),
    ('account executive', 'Account Executive'),
    ('account manager', 'Account Manager'),
    ('enterprise account manager', 'Enterprise Account Manager'),
    ('technical account manager', 'Technical Account Manager'),
    ('sales development representative', 'Sales Development Representative'),
    ('business development representative', 'Business Development Representative'),
    ('sales development rep', 'Sales Development Representative'),
    ('bdr', 'Business Development Representative'),
    ('sdr', 'Sales Development Representative'),
    ('sales engineer', 'Sales Engineer'),
    ('sales manager', 'Sales Manager'),
    ('regional sales director', 'Regional Sales Director'),
    ('sales representative', 'Sales Representative'),
    ('sales specialist', 'Sales Specialist'),
    ('sales enablement', 'Sales Enablement Manager'),
    ('sales operations', 'Sales Operations Manager'),
    # Solutions / Pre-sales
    ('solutions engineer', 'Solutions Engineer'),
    ('solutions architect', 'Solutions Architect'),
    ('solutions consultant', 'Solutions Consultant'),
    ('partner solutions architect', 'Partner Solutions Architect'),
    # Customer Success
    ('customer success manager', 'Customer Success Manager'),
    ('customer success', 'Customer Success Manager'),
    ('customer onboarding', 'Customer Onboarding Manager'),
    ('renewals manager', 'Renewals Manager'),
    ('engagement manager', 'Engagement Manager'),
    ('customer experience', 'Customer Experience Manager'),
    # Support — avoid matching 'AI Conversation Designer, Customer Support'
    # Rule: only match when 'support' is at the start or right before a function word
    ('technical support engineer', 'Technical Support Engineer'),
    ('technical support specialist', 'Technical Support Specialist'),
    ('technical support analyst', 'Technical Support Specialist'),
    ('technical support', 'Technical Support Specialist'),
    ('product support engineer', 'Product Support Engineer'),
    ('product support specialist', 'Product Support Specialist'),
    ('product support', 'Product Support Specialist'),
    ('support specialist', 'Support Specialist'),
    ('customer support advocate', 'Support Specialist'),
    ('customer support agent', 'Support Specialist'),
    ('customer support analyst', 'Support Specialist'),
    ('customer support and success', 'Support Specialist'),
    ('customer support incident', 'Support Specialist'),
    ('customer technical support', 'Technical Support Specialist'),
    # Marketing
    ('product marketing manager', 'Product Marketing Manager'),
    ('content marketing', 'Content Marketing Manager'),
    ('demand generation', 'Demand Generation Manager'),
    ('field marketing', 'Field Marketing Manager'),
    ('event marketing', 'Event Marketing Manager'),
    ('partner marketing', 'Partner Marketing Manager'),
    ('media buyer', 'Paid Media Specialist'),
    ('paid media', 'Paid Media Specialist'),
    ('paid search', 'Paid Media Specialist'),
    ('paid social', 'Paid Media Specialist'),
    ('social media manager', 'Social Media Manager'),
    ('marketing manager', 'Marketing Manager'),
    ('communications manager', 'Communications Manager'),
    ('copywriter', 'Copywriter'),
    # Engineering leadership
    ('engineering manager', 'Engineering Manager'),
    ('director of engineering', 'Director of Engineering'),
    ('vp of engineering', 'Director of Engineering'),
    ('head of engineering', 'Director of Engineering'),
    # People / HR / Recruiting
    ('recruiter', 'Recruiter'),
    ('talent acquisition', 'Talent Acquisition Specialist'),
    ('talent sourcer', 'Talent Sourcer'),
    ('technical recruiter', 'Technical Recruiter'),
    ('director of talent', 'Director of Talent Acquisition'),
    ('hr business partner', 'HR Business Partner'),
    ('people business partner', 'People Business Partner'),
    ('people operations', 'People Operations Specialist'),
    ('hr generalist', 'HR Business Partner'),
    ('payroll specialist', 'Payroll Specialist'),
    ('payroll manager', 'Payroll Manager'),
    ('compensation analyst', 'Compensation Analyst'),
    ('director of people', 'Director of People'),
    # Finance
    ('financial analyst', 'Financial Analyst'),
    ('financial planning', 'Financial Analyst'),
    ('fp&a', 'Financial Analyst'),
    ('accountant', 'Accountant'),
    ('accounting manager', 'Accounting Manager'),
    ('controller', 'Controller'),
    ('revenue accountant', 'Revenue Accountant'),
    ('tax manager', 'Tax Manager'),
    ('treasury analyst', 'Treasury Analyst'),
    ('strategic finance', 'Strategic Finance Manager'),
    ('finance manager', 'Finance Manager'),
    ('risk manager', 'Risk Manager'),
    ('internal auditor', 'Internal Auditor'),
    # Legal
    ('general counsel', 'Associate General Counsel'),
    ('corporate counsel', 'Corporate Counsel'),
    ('commercial counsel', 'Commercial Counsel'),
    ('privacy counsel', 'Privacy Counsel'),
    ('paralegal', 'Paralegal'),
    ('contracts manager', 'Contracts Manager'),
    # CCO is a senior role; compliance officer/specialist for mid-level
    ('chief compliance officer', 'Compliance Specialist'),  # no CCO canonical role; closest is compliance specialist
    ('compliance specialist', 'Compliance Specialist'),
    ('compliance officer', 'Compliance Specialist'),
    # Operations / PM
    ('program manager', 'Program Manager'),
    ('technical program manager', 'Technical Program Manager'),
    ('project manager', 'Project Manager'),
    ('operations manager', 'Operations Manager'),
    ('business analyst', 'Business Analyst'),
    ('executive assistant', 'Executive Assistant'),
    ('executive business partner', 'Executive Business Partner'),
    ('administrative assistant', 'Administrative Assistant'),
    ('office manager', 'Office Manager'),
    # IT
    ('it support', 'IT Support Engineer'),
    ('systems administrator', 'Systems Administrator'),
    ('it engineer', 'IT Engineer'),
    # Technical Writer
    ('technical writer', 'Technical Writer'),
    # Partnerships
    ('partner manager', 'Partner Manager'),
    ('partner development', 'Partner Development Manager'),
    # Supply Chain / Procurement
    ('supply chain', 'Supply Chain Analyst'),
    ('procurement manager', 'Procurement Manager'),
    # 'buyer' rule must NOT match 'media buyer' (handled above) or 'buyer/planner' ambiguously
    # only match when title is clearly a procurement buyer context
    ('federal buyer', 'Senior Buyer'),
    ('strategic buyer', 'Senior Buyer'),
    ('senior buyer', 'Senior Buyer'),
    ('buyer/planner', 'Senior Buyer'),
    ('buyer ii', 'Senior Buyer'),
    ('buyer i', 'Senior Buyer'),
    # Healthcare
    ('physician assistant', 'Physician Assistant'),
    ('nurse practitioner', 'Nurse Practitioner'),
    ('medical director', 'Medical Director'),
    ('psychiatrist', 'Psychiatrist'),
    ('therapist', 'Mental Health Therapist'),
    # Real Estate
    ('transaction coordinator', 'Transaction Coordinator'),
    # Finance — additional
    ('accounts payable', 'Accountant'),
    ('accounts receivable', 'Accountant'),
    ('tax analyst', 'Financial Analyst'),
    ('tax resolution', 'Financial Analyst'),
    ('billing specialist', 'Accountant'),
    ('billing and accounts', 'Accountant'),
    ('corporate treasurer', 'Controller'),
    # Art / Creative
    ('art director', 'Creative Director'),
    # Research
    ('applied research lead', 'Research Scientist'),
    ('applied research scientist', 'Research Scientist'),
    # Operations / Logistics
    ('air freight', 'Global Operations Manager'),
    ('ocean operations', 'Global Operations Manager'),
    ('air operations', 'Operations Manager'),
    ('robotaxi', 'Operations Manager'),
    ('workforce planning', 'People Operations Specialist'),
    # Sales management
    ('ae manager', 'Sales Manager'),
    ('account executive manager', 'Sales Manager'),
    # Growth / lifecycle marketing
    ('growth - emails', 'Demand Generation Manager'),
    ('lifecycle marketing', 'Demand Generation Manager'),
    ('acquisition growth', 'Demand Generation Manager'),
    # Manufacturing / Machinist
    ('assembly integration', 'Manufacturing Technician'),
    ('cnc machinist', 'Manufacturing Technician'),
    ('cnc setup', 'Manufacturing Technician'),
    ('5 axis machinist', 'Manufacturing Technician'),
    ('senior machinist', 'Manufacturing Technician'),
    ('a&p mechanic', 'Field Service Technician'),
    ('avionics technician', 'Field Service Technician'),
    ('blanking line', 'Manufacturing Technician'),
    # Security / Investigations
    ('abuse investigator', 'Security Operations Analyst'),
    ('senior investigator', 'Security Operations Analyst'),
    ('threat intelligence', 'Security Operations Analyst'),
    ('aml investigator', 'Security Operations Analyst'),
    ('anti-money laundering', 'Security Operations Analyst'),
    ('cyber incident response', 'Security Operations Analyst'),
    ('comsec custodian', 'Security Operations Analyst'),
    # Customer / Account specialist
    ('client account specialist', 'Account Manager'),
    ('client solutions manager', 'Account Manager'),
    ('customer activation manager', 'Customer Success Manager'),
    # Brand / Content writing
    ('brand writer', 'Copywriter'),
    ('content writer', 'Copywriter'),
    # Technical specialist / hardware
    ('technical specialist', 'IT Support Engineer'),
    ('field technician', 'Field Service Technician'),
    ('field service technician', 'Field Service Technician'),
    # Corporate Development
    ('corporate development', 'Business Analyst'),
    ('corporate strategy', 'Business Analyst'),
    # People / HR
    ('ai enablement lead', 'People Operations Specialist'),
    ('area leader', 'Operations Manager'),
    # IT Director
    ('director of information technology', 'IT Engineer'),
    ('field cto', 'Solutions Architect'),
    # Healthcare
    ('care navigator', 'Nurse Care Manager'),
    ('care coordinator', 'Nurse Care Manager'),
    ('care advocate', 'Medical Assistant'),
    ('clinical veterinarian', 'Physician'),
    ('medical receptionist', 'Medical Assistant'),
    ('clinical care navigator', 'Nurse Care Manager'),
    # Legal / Compliance financial
    ('credit risk', 'Risk Manager'),
    ('consumer loan reviewer', 'Risk Manager'),
    ('claims adjuster', 'Risk Manager'),
    ('claims advocate', 'Risk Manager'),
    ('credit underwriter', 'Risk Manager'),
    ('loan reviewer', 'Risk Manager'),
    # Authentication / Training admin
    ('authentication training', 'Systems Administrator'),
    ('authentication admin', 'Systems Administrator'),
    # Data annotation / training
    ('data annotation', 'Data Analyst'),
    ('data annotator', 'Data Analyst'),
    ('data trainer', 'Data Analyst'),
    # New roles (added 2026-05-13)
    ('developer relations', 'Developer Relations Engineer'),
    ('developer educator', 'Developer Relations Engineer'),
    ('devrel', 'Developer Relations Engineer'),
    ('developer advocate', 'Developer Relations Engineer'),
    ('learning & development', 'Learning & Development Manager'),
    ('learning and development', 'Learning & Development Manager'),
    ('learning design', 'Learning & Development Manager'),
    ('curriculum developer', 'Learning & Development Manager'),
    ('curriculum design', 'Learning & Development Manager'),
    ('instructional design', 'Learning & Development Manager'),
    ('game designer', 'Game Designer'),
    ('ui artist', 'Game Designer'),
    ('level designer', 'Game Designer'),
    ('otc trader', 'Trader'),
    (' trader', 'Trader'),
    ('crypto trader', 'Trader'),
    ('execution trader', 'Trader'),
    # Retail / store roles
    ('peloton expert', 'Store Advisor'),
    ('starbucks barista', 'Store Associate'),
    ('barista', 'Store Associate'),
    ('retail sales floor leader', 'Retail Store Manager'),
    ('keyholder', 'Shift Supervisor'),
    ('key lead', 'Shift Supervisor'),
    ('key holder', 'Shift Supervisor'),
    ('shift lead', 'Shift Supervisor'),
    ('back of house associate', 'Store Associate'),
    ('department manager', 'Retail Store Manager'),
    # Sales / BD
    ('vercel development representative', 'Business Development Representative'),
    ('solution architect', 'Solutions Architect'),         # typo variant
    ('sr. industry manager', 'Sales Manager'),
    ('partner director', 'Partner Manager'),
    ('general manager', 'Operations Manager'),
    ('gm,', 'Operations Manager'),
    # HR
    ('hrbp', 'HR Business Partner'),
    ('finance business partner', 'Finance Manager'),
    # Security / Compliance
    ('fraud investigator', 'Security Operations Analyst'),
    ('member of compliance', 'Compliance Specialist'),
    ('field ciso', 'Security Operations Analyst'),
    ('comsec', 'Security Operations Analyst'),
    # Operations / Retail
    ('service manager', 'Operations Manager'),
    ('regional manager', 'Regional Sales Director'),
    ('area manager', 'Area Manager'),
    # Healthcare / Veterinary
    ('service advisor', 'Customer Experience Manager'),
    # Hardware / Manufacturing
    ('propulsion technician', 'Field Service Technician'),
    # Content / Comms
    ('developer relations', 'Solutions Engineer'),
    ('devrel', 'Solutions Engineer'),
    ('policy manager', 'Communications Manager'),
    ('communications lead', 'Communications Manager'),
    ('content lead', 'Content Marketing Manager'),
    # Game / Senior titles → base roles
    ('senior scientist', 'Research Scientist'),
    ('staff scientist', 'Research Scientist'),
    ('principal scientist', 'Research Scientist'),
    ('senior lead', 'Program Manager'),         # "Senior Lead, X" → Program Manager
    # Additional Account/Sales patterns
    ('director of strategic accounts', 'Enterprise Account Executive'),
    ('sales lead', 'Account Executive'),
    ('product lead', 'Product Manager'),
]


def try_map(title: str):
    t = title.lower()
    for substring, canonical in MAP_RULES:
        if substring in t:
            return canonical
    return None


def main():
    with open(INPUT_CSV) as f:
        candidates = list(csv.DictReader(f))

    skipped, mapped, review = [], [], []

    for row in candidates:
        raw = row['raw_title']
        if should_skip(raw):
            skipped.append({**row, 'action': 'skip', 'canonical': '', 'confidence': 'high', 'note': 'intern/program/non-english'})
        else:
            canon = try_map(raw)
            if canon:
                mapped.append({**row, 'action': 'map_to', 'canonical': canon, 'confidence': 'high', 'note': ''})
            else:
                review.append(row)

    fieldnames = ['id', 'raw_title', 'job_count', 'action', 'canonical', 'confidence', 'note']

    with open(PRE_OUT_CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(skipped + mapped)

    with open(REVIEW_OUT_CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['id', 'raw_title', 'job_count'])
        w.writeheader()
        w.writerows(review)

    print(f"Pre-classification results:")
    print(f"  Skipped (intern/program/etc): {len(skipped)}")
    print(f"  Mapped to existing role:      {len(mapped)}")
    print(f"  Needs AI review:              {len(review)}")
    print(f"  Total:                        {len(candidates)}")
    print(f"\nOutput: {PRE_OUT_CSV} ({len(skipped)+len(mapped)} rows)")
    print(f"        {REVIEW_OUT_CSV} ({len(review)} rows)")

    if APPLY:
        _apply_preclassified(skipped + mapped)


def _apply_preclassified(rows):
    from app import create_app
    from app.models import db, Job, Role, RoleTitleVariation, UnmatchedTitle

    app = create_app()
    with app.app_context():
        skip_count = map_count = 0
        for row in rows:
            candidate = UnmatchedTitle.query.get(int(row['id']))
            if not candidate:
                continue

            if row['action'] == 'skip':
                candidate.status = 'rejected'
                skip_count += 1

            elif row['action'] == 'map_to':
                role = Role.query.filter_by(normalized_title=row['canonical']).first()
                if not role:
                    continue
                # Update jobs
                Job.query.filter_by(title=row['raw_title']).update({'role_id': role.id})
                # Upsert RoleTitleVariation
                var = RoleTitleVariation.query.filter_by(original_title=row['raw_title']).first()
                if var:
                    var.role_id = role.id
                else:
                    db.session.add(RoleTitleVariation(
                        role_id=role.id,
                        original_title=row['raw_title'],
                        frequency=max(1, int(row['job_count'])),
                    ))
                candidate.status = 'approved'
                candidate.mapped_role_id = role.id
                map_count += 1

        db.session.commit()
        print(f"\nApplied: {map_count} mapped, {skip_count} rejected")


if __name__ == '__main__':
    main()
