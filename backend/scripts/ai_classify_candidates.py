"""
AI batch classifier for pending unmatched_titles.

Sends batches of raw job titles to Claude and asks it to map each to a
canonical role (or flag as new_role / skip).

Output: data/candidate_classifications.csv  (id, raw_title, action, mapped_role, notes)

Run: PYTHONPATH=. venv/bin/python scripts/ai_classify_candidates.py [--batch-size 150] [--resume]
"""
import sys
import os
import csv
import json
import time

sys.path.insert(0, os.getcwd())

BATCH_SIZE = 150
RESUME = '--resume' in sys.argv
for arg in sys.argv[1:]:
    if arg.startswith('--batch-size='):
        BATCH_SIZE = int(arg.split('=')[1])

INPUT_CSV  = 'data/pending_candidates.csv'
OUTPUT_CSV = 'data/candidate_classifications.csv'

CANONICAL_ROLES = [
    "Accountant", "Accounting Manager", "Controller", "Revenue Accountant", "Revenue Accounting Manager",
    "Account Executive", "Account Manager", "Commercial Account Executive", "Corporate Account Executive",
    "Enterprise Account Executive", "Enterprise Account Manager", "Key Account Director",
    "Major Account Executive", "Mid-Market Account Executive", "Strategic Account Executive",
    "Technical Account Manager", "Territory Account Executive",
    "Ad Operations Associate", "Mission Operations Engineer",
    "Business Analyst", "Data Analyst", "Product Analyst",
    "Internal Auditor",
    "Mental Health Therapist", "Neuropsychologist", "Psychiatrist", "Testing Psychologist",
    "Brand Designer", "Graphic Designer", "Motion Designer",
    "Business Development Manager", "Operations Manager",
    "Clinical Lab Scientist", "Clinical Oncology Specialist", "Family Medicine Physician",
    "Medical Assistant", "Nurse Care Manager", "Nurse Practitioner", "Phlebotomist",
    "Physician", "Physician Assistant", "Primary Care Physician",
    "Medical Director",
    "Communications Manager",
    "Compliance Specialist",
    "Copywriter",
    "Content Designer",
    "Deployment Strategist", "Field Engineer", "Forward Deployed Data Scientist",
    "Implementation Consultant", "Implementation Engineer", "Implementation Manager", "Integration Engineer",
    "Customer Experience Manager",
    "AI Success Manager", "Customer Onboarding Manager", "Customer Success Manager",
    "Enterprise Customer Success Manager", "Mid-Market Customer Success Manager",
    "Renewals Manager", "Technical Success Manager",
    "Incident Manager", "Product Support Engineer", "Product Support Specialist",
    "Support Specialist", "Technical Support Engineer", "Technical Support Specialist",
    "Analytics Engineer", "Data Engineer",
    "Data Scientist",
    "Data Science Manager",
    "Creative Director", "Design Director", "Director of Design",
    "Technical Writer",
    "Director of Engineering", "Engineering Manager",
    "Equity Program Manager", "Stock Plan Administrator",
    "Administrative Assistant", "Executive Assistant", "Executive Business Partner",
    "Field Service Technician",
    "Finance Manager", "Financial Analyst",
    "Electrical Engineer", "FPGA Engineer", "Mechanical Engineer", "Thermal Engineer",
    "HR Business Partner", "People Business Partner", "People Partner",
    "Cloud Engineer", "Cloud Infrastructure Engineer", "DevOps Engineer",
    "Infrastructure Engineer", "Network Engineer", "Platform Engineer", "Site Reliability Engineer",
    "Sales Representative",
    "Portfolio Manager",
    "Business Systems Analyst", "Business Systems Engineer",
    "IT Engineer", "IT Support Engineer", "Salesforce Administrator", "Systems Administrator", "Workday Administrator",
    "Associate General Counsel", "Commercial Counsel", "Contracts Manager", "Contracts Negotiator",
    "Corporate Counsel", "Legal Counsel", "Paralegal", "Privacy Counsel", "Product Paralegal",
    "Customs Specialist", "Global Operations Manager", "Ocean Operations Associate", "Trade Advisory Lead",
    "AI Engineer", "AI Infrastructure Engineer", "Applied AI Engineer", "Applied Scientist", "Machine Learning Engineer",
    "Manufacturing Engineer", "Manufacturing Technician", "Manufacturing Test Engineer", "Production Supervisor",
    "Content Marketing Manager", "Demand Generation Manager", "Event Marketing Manager",
    "Field Marketing Manager", "Influencer Marketing Manager", "Marketing Manager",
    "Paid Media Specialist", "Partner Marketing Manager", "Social Media Manager",
    "Mobile Engineer",
    "Office Manager", "Workplace Experience Manager",
    "Area Manager", "Physical Security Manager",
    "Partner Development Manager", "Partner Manager", "Partner Sales Manager",
    "Strategic Partner Manager", "Technology Partner Manager",
    "Payroll Manager", "Payroll Specialist",
    "Director of People",
    "People Operations Specialist",
    "Procurement Manager", "Senior Buyer",
    "Product Designer", "UX Designer",
    "Director of Product", "Group Product Manager", "Product Manager", "Technical Product Manager",
    "Product Marketing Manager",
    "Product Operations Manager",
    "Engagement Manager",
    "Program Manager", "Technical Program Manager",
    "Project Manager",
    "Quality Inspector", "QA Engineer", "Test Engineer",
    "Agent Experience Coordinator", "Agent Experience Manager",
    "Strategic Growth Manager", "Strategic Growth Partner", "Transaction Coordinator",
    "Research Engineer", "Research Scientist",
    "Cashier", "Store Associate", "Retail Store Manager",
    "Risk Manager",
    "Robotics Engineer",
    "Business Development Representative", "Sales Development Representative",
    "Field Enablement Manager", "Sales Enablement Manager",
    "Partner Solutions Architect", "Resident Solutions Architect", "Sales Engineer",
    "Solutions Architect", "Solutions Consultant", "Solutions Engineer",
    "Regional Sales Director", "Sales Manager",
    "Deal Desk Analyst", "Deal Operations Analyst", "Revenue Operations Manager",
    "Revenue Strategy & Operations Lead", "Sales Operations Manager", "Sales Specialist",
    "Application Security Engineer", "Cloud Security Engineer", "Enterprise Security Engineer",
    "Information Security Engineer", "Infrastructure Security Engineer", "Offensive Security Engineer",
    "Product Security Engineer", "Security Engineer", "Security Operations Analyst",
    "Security Operations Engineer", "Threat Specialist",
    "Design Engineer", "GTM Engineer", "Software Engineer",
    "Brand Ambassador", "Restaurant General Manager", "Restaurant Manager",
    "Retail Ambassador", "Shift Supervisor", "Store Advisor",
    "Strategic Finance Manager",
    "Global Supply Manager", "Material Planner", "Supply Chain Analyst",
    "Systems Engineer",
    "Director of Talent Acquisition", "Recruiter", "Talent Acquisition Specialist",
    "Talent Sourcer", "Technical Recruiter",
    "Tax Manager",
    "Compensation Analyst",
    "Treasury Analyst",
    "UX Researcher",
    # recently added via mappings
    "IT Support Engineer", "HR Business Partner", "People Operations Specialist",
    "Content Marketing Manager", "Paid Media Specialist", "Revenue Operations Manager",
    "Sales Operations Manager", "Data Science Manager", "Product Operations Manager",
    "Information Security Engineer", "Security Operations Analyst",
]

SYSTEM_PROMPT = """You are a job role taxonomy expert. You will be given a list of raw job titles and a list of canonical roles.

For each raw title, decide:
- "map_to": it clearly belongs to one of the canonical roles (use the exact canonical name)
- "new_role": it represents a legitimate role type not in the list (suggest a clean canonical name)
- "skip": it is a junk/placeholder title (e.g. "Join Our Team", "Open Application", vague internal codes)

Rules:
- Prefer mapping to an existing role over creating a new one — only suggest new_role when the function is genuinely distinct
- Seniority variants (Senior, Lead, Staff, Principal, Jr, Associate) → map to the base role, NOT new_role
- Geographic/region suffixes (APAC, EMEA, LATAM, US, UK, etc.) → map to base role
- Industry qualifiers (Healthcare, Finance, Enterprise, SMB) → map to base role unless function is truly different
- Intern/Contract variants → map to the closest base role
- For new_role suggestions, use clean Title Case, drop company-specific jargon

Respond with a JSON array. Each element:
{
  "raw_title": "<exact input title>",
  "action": "map_to" | "new_role" | "skip",
  "canonical": "<exact canonical role name if map_to, suggested name if new_role, null if skip>",
  "confidence": "high" | "medium" | "low",
  "note": "<brief reason only if non-obvious>"
}"""


def classify_batch(client, titles: list[dict]) -> list[dict]:
    titles_text = '\n'.join(f'{i+1}. {t["raw_title"]}' for i, t in enumerate(titles))
    canonical_list = '\n'.join(f'- {r}' for r in sorted(set(CANONICAL_ROLES)))

    response = client.messages.create(
        model='claude-opus-4-7',
        max_tokens=8096,
        messages=[{
            'role': 'user',
            'content': (
                f"Canonical roles:\n{canonical_list}\n\n"
                f"Raw titles to classify:\n{titles_text}\n\n"
                "Return a JSON array with one object per title."
            )
        }],
        system=SYSTEM_PROMPT,
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        text = text.rsplit('```', 1)[0]

    return json.loads(text)


def main():
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    # Load candidates
    with open(INPUT_CSV) as f:
        candidates = list(csv.DictReader(f))
    print(f"Loaded {len(candidates)} candidates")

    # Determine already-processed titles if resuming
    done_titles = set()
    if RESUME and os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV) as f:
            for row in csv.DictReader(f):
                done_titles.add(row['raw_title'])
        print(f"Resuming — {len(done_titles)} already classified")

    remaining = [c for c in candidates if c['raw_title'] not in done_titles]
    print(f"To classify: {len(remaining)}")

    out_mode = 'a' if RESUME and os.path.exists(OUTPUT_CSV) else 'w'
    out_file = open(OUTPUT_CSV, out_mode, newline='')
    writer = csv.DictWriter(out_file, fieldnames=['id', 'raw_title', 'job_count', 'action', 'canonical', 'confidence', 'note'])
    if out_mode == 'w':
        writer.writeheader()

    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num in range(total_batches):
        batch = remaining[batch_num * BATCH_SIZE:(batch_num + 1) * BATCH_SIZE]
        print(f"  Batch {batch_num + 1}/{total_batches} ({len(batch)} titles)...", end=' ', flush=True)

        try:
            results = classify_batch(client, batch)
        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep(5)
            continue

        # Build lookup by raw_title
        result_map = {r['raw_title']: r for r in results}

        for c in batch:
            res = result_map.get(c['raw_title'], {})
            writer.writerow({
                'id': c['id'],
                'raw_title': c['raw_title'],
                'job_count': c['job_count'],
                'action': res.get('action', 'unknown'),
                'canonical': res.get('canonical', ''),
                'confidence': res.get('confidence', ''),
                'note': res.get('note', ''),
            })
        out_file.flush()
        print(f"done")
        time.sleep(1)  # avoid rate limits

    out_file.close()

    # Summary
    actions = {}
    with open(OUTPUT_CSV) as f:
        for row in csv.DictReader(f):
            actions[row['action']] = actions.get(row['action'], 0) + 1
    print(f"\nClassification summary:")
    for action, count in sorted(actions.items()):
        print(f"  {action}: {count}")
    print(f"\nResults saved to {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
