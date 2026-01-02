# backend/scripts/discover_greenhouse.py

"""
Discover and verify Greenhouse companies.
Tests if a company has a public Greenhouse job board.

Usage: python scripts/discover_greenhouse.py
"""

import sys
import os
import requests
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def check_greenhouse_company(slug: str) -> dict:
    """Check if a company has a Greenhouse job board"""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            job_count = len(data.get('jobs', []))
            return {"slug": slug, "exists": True, "jobs": job_count}
        else:
            return {"slug": slug, "exists": False, "jobs": 0}
            
    except Exception as e:
        return {"slug": slug, "exists": False, "jobs": 0, "error": str(e)}


def discover_companies(slugs: list) -> list:
    """Check multiple companies and return valid ones"""
    valid = []
    
    print(f"\n🔍 Checking {len(slugs)} companies...\n")
    
    for i, slug in enumerate(slugs, 1):
        result = check_greenhouse_company(slug)
        
        if result["exists"] and result["jobs"] > 0:
            print(f"  ✅ {slug:<25} {result['jobs']:>4} jobs")
            valid.append(result)
        else:
            print(f"  ❌ {slug:<25} not found")
        
        # Rate limit
        if i % 10 == 0:
            time.sleep(1)
    
    return valid


# Companies to check (add more as needed)
COMPANIES_TO_CHECK = [
    # Big Tech / Unicorns
    "spotify", "discord", "pinterest", "reddit", "snapchat", "twitch",
    "dropbox", "lyft", "doordash", "instacart", "uber", "palantir",
    "databricks", "snowflakecomputing", "cloudflare", "datadog",
    
    # Fintech
    "coinbase", "robinhood", "plaid", "squareup", "brex", "ramp",
    "mercury", "chime", "affirm", "klarna", "wise", "revolut",
    "sofi", "nubank", "monzo", "marqeta", "checkout", "adyen",
    
    # Dev Tools
    "github", "gitlab", "vercel", "netlify", "postman", "retool",
    "linear", "sentry", "launchdarkly", "hashicorp", "circleci",
    "supabase", "planetscale", "prisma", "render", "railway",
    
    # AI/ML
    "openai", "anthropic", "cohere", "huggingface", "scale",
    "wandb", "replicate", "stabilityai", "runway", "descript",
    "assemblyai", "deepgram", "perplexity", "glean", "jasper",
    
    # Productivity
    "notion", "airtable", "asana", "monday", "clickup", "mural",
    "miro", "loom", "calendly", "zapier", "grammarly", "coda",
    
    # Security
    "1password", "snyk", "crowdstrike", "okta", "zscaler",
    "wiz", "vanta", "drata", "lacework",
    
    # HR Tech
    "gusto", "lattice", "rippling", "deel", "remote", "oyster",
    "justworks", "personio", "hibob", "ashbyhq",
    
    # Marketing/Sales
    "hubspot", "intercom", "zendesk", "gong", "outreach",
    "salesloft", "apollo", "drift", "braze", "klaviyo",
    
    # Analytics
    "mixpanel", "amplitude", "segment", "heap", "fullstory",
    "hotjar", "pendo", "walkme",
    
    # Design
    "canva", "webflow", "framer", "invision", "sketch",
    
    # Other notable
    "duolingo", "coursera", "masterclass", "calm", "headspace",
    "peloton", "whoop", "oura", "flexport", "faire", "goat",
    "poshmark", "mercari", "offerup", "letgo", "vinted",
]


if __name__ == "__main__":
    valid_companies = discover_companies(COMPANIES_TO_CHECK)
    
    print(f"\n{'='*50}")
    print(f"✅ Found {len(valid_companies)} valid Greenhouse companies")
    print(f"{'='*50}\n")
    
    # Sort by job count
    valid_companies.sort(key=lambda x: x["jobs"], reverse=True)
    
    print("Top companies by job count:")
    print(f"{'Slug':<25} {'Jobs':>6}")
    print("-" * 35)
    
    for company in valid_companies[:30]:
        print(f"{company['slug']:<25} {company['jobs']:>6}")
    
    # Output for copy-paste into companies.py
    print(f"\n{'='*50}")
    print("📋 Copy-paste for companies.py:")
    print(f"{'='*50}\n")
    
    for company in valid_companies:
        print(f'    {{"slug": "{company["slug"]}", "name": "{company["slug"].title()}", "category": "Unknown"}},')