"""
Enrich Company rows with location, founded_year, company_type, valuation, website, logo_url
using the Claude API. Processes in batches of 30 companies per request.

Usage:
    cd backend
    ANTHROPIC_API_KEY='...' DATABASE_URL='<prod-dsn>' PYTHONPATH=. \\
        venv/bin/python scripts/enrich_companies.py [--apply] [--limit N] [--offset N]

Dry-run by default. --apply writes to DB. --limit / --offset for incremental runs.
"""
import os, sys, json, time
import anthropic

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

from app import create_app
from app.models import Company, db

APPLY  = '--apply'  in sys.argv
LIMIT  = int(next((sys.argv[sys.argv.index('--limit')  + 1] for _ in ['x'] if '--limit'  in sys.argv), 9999))
OFFSET = int(next((sys.argv[sys.argv.index('--offset') + 1] for _ in ['x'] if '--offset' in sys.argv), 0))
BATCH  = 30

SYSTEM = """You are a company data researcher. Given a list of company names,
return a JSON array with one object per company in the same order.
Each object must have exactly these keys:
  name         - echo the company name back exactly
  location     - HQ city and state/country (e.g. "San Francisco, CA" or "London, UK"). null if unknown.
  founded_year - 4-digit integer year founded. null if unknown.
  company_type - one of: "Public", "Private", "Nonprofit", "Government", "Subsidiary". null if unknown.
  valuation    - market cap or last known valuation as a short string (e.g. "$4.5B", "$800M", "Public (NASDAQ: AAPL)"). null if unknown or private with no disclosed valuation.
  website      - primary website domain only, no protocol or trailing slash (e.g. "stripe.com"). null if unknown.
  logo_url     - URL to the company's logo image (prefer Clearbit: "https://logo.clearbit.com/<domain>"). null if unknown.

Return ONLY a valid JSON array, no prose, no markdown fences."""

def ask_claude(client, names: list[str]) -> list[dict]:
    prompt = "Enrich these companies:\n" + "\n".join(f"- {n}" for n in names)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


app = create_app()
with app.app_context():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    companies = db.session.query(Company).filter(
        Company.is_active == True,
        db.or_(
            Company.location.is_(None),
            Company.founded_year.is_(None),
            Company.company_type.is_(None),
            Company.website.is_(None),
            Company.logo_url.is_(None),
        )
    ).order_by(Company.name).offset(OFFSET).limit(LIMIT).all()

    total = len(companies)
    print(f"Companies to enrich: {total}")
    print(f"Mode: {'APPLY' if APPLY else 'DRY RUN'}\n")

    updated = 0
    for i in range(0, total, BATCH):
        batch = companies[i:i + BATCH]
        names = [c.name for c in batch]
        print(f"Batch {i//BATCH + 1}: {names[0]} … {names[-1]}")

        try:
            results = ask_claude(client, names)
        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(5)
            continue

        for company, result in zip(batch, results):
            changes = []
            if company.location is None and result.get("location"):
                changes.append(f"location={result['location']}")
                if APPLY: company.location = result["location"]
            if company.founded_year is None and result.get("founded_year"):
                changes.append(f"founded={result['founded_year']}")
                if APPLY: company.founded_year = result["founded_year"]
            if company.company_type is None and result.get("company_type"):
                changes.append(f"type={result['company_type']}")
                if APPLY: company.company_type = result["company_type"]
            if company.valuation is None and result.get("valuation"):
                changes.append(f"valuation={result['valuation']}")
                if APPLY: company.valuation = result["valuation"]
            if company.website is None and result.get("website"):
                changes.append(f"website={result['website']}")
                if APPLY: company.website = result["website"]
            if company.logo_url is None and result.get("logo_url"):
                changes.append(f"logo={result['logo_url']}")
                if APPLY: company.logo_url = result["logo_url"]
            if changes:
                print(f"  {company.name}: {', '.join(changes)}")
                updated += 1

        if APPLY:
            db.session.commit()
        time.sleep(1)

    print(f"\n{'Applied' if APPLY else 'Would update'}: {updated}/{total} companies")
    if not APPLY:
        print("Re-run with --apply to write changes.")
