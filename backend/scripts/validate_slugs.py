# scripts/validate_slugs.py

import requests
import time

# Companies to validate
COMPANIES_TO_CHECK = [
    # AI/ML - checking variations
    {"slug": "openai", "name": "OpenAI"},
    {"slug": "open-ai", "name": "OpenAI"},
    {"slug": "openaicom", "name": "OpenAI"},
    {"slug": "cohere", "name": "Cohere"},
    {"slug": "cohere-ai", "name": "Cohere"},
    {"slug": "cohereai", "name": "Cohere"},
    {"slug": "huggingface", "name": "Hugging Face"},
    {"slug": "hugging-face", "name": "Hugging Face"},
    {"slug": "scale", "name": "Scale AI"},
    {"slug": "scaleai", "name": "Scale AI"},
    {"slug": "scale-ai", "name": "Scale AI"},
    {"slug": "runway", "name": "Runway"},
    {"slug": "runwayml", "name": "Runway"},
    {"slug": "replicate", "name": "Replicate"},
    {"slug": "replicatehq", "name": "Replicate"},
    {"slug": "replit", "name": "Replit"},
    {"slug": "perplexity", "name": "Perplexity AI"},
    {"slug": "perplexityai", "name": "Perplexity AI"},
    {"slug": "glean", "name": "Glean"},
    {"slug": "anyscale", "name": "Anyscale"},
    {"slug": "wandb", "name": "Weights & Biases"},
    {"slug": "weights-and-biases", "name": "Weights & Biases"},
    {"slug": "weightsandbiases", "name": "Weights & Biases"},
    {"slug": "labelbox", "name": "Labelbox"},
    
    # Fintech
    {"slug": "stripe", "name": "Stripe"},
    {"slug": "plaid", "name": "Plaid"},
    {"slug": "ramp", "name": "Ramp"},
    {"slug": "carta", "name": "Carta"},
    {"slug": "rippling", "name": "Rippling"},
    {"slug": "deel", "name": "Deel"},
    {"slug": "wise", "name": "Wise"},
    {"slug": "wisecom", "name": "Wise"},
    {"slug": "transferwise", "name": "Wise"},
    {"slug": "checkout", "name": "Checkout.com"},
    {"slug": "checkoutcom", "name": "Checkout.com"},
    {"slug": "moderntreasury", "name": "Modern Treasury"},
    {"slug": "modern-treasury", "name": "Modern Treasury"},
    
    # Data
    {"slug": "snowflake", "name": "Snowflake"},
    {"slug": "snowflakecomputing", "name": "Snowflake"},
    {"slug": "fivetran", "name": "Fivetran"},
    {"slug": "dbtlabs", "name": "dbt Labs"},
    {"slug": "dbt-labs", "name": "dbt Labs"},
    {"slug": "getdbt", "name": "dbt Labs"},
    {"slug": "airbyte", "name": "Airbyte"},
    {"slug": "airbytehq", "name": "Airbyte"},
    {"slug": "clickhouse", "name": "ClickHouse"},
    {"slug": "clickhouseinc", "name": "ClickHouse"},
    {"slug": "confluent", "name": "Confluent"},
    {"slug": "confluentinc", "name": "Confluent"},
    {"slug": "starburst", "name": "Starburst"},
    {"slug": "starburstdata", "name": "Starburst"},
    {"slug": "preset", "name": "Preset"},
    {"slug": "presetio", "name": "Preset"},
    {"slug": "hex", "name": "Hex"},
    {"slug": "hextech", "name": "Hex"},
    
    # Developer Tools
    {"slug": "figma", "name": "Figma"},
    {"slug": "notion", "name": "Notion"},
    {"slug": "notionhq", "name": "Notion"},
    {"slug": "linear", "name": "Linear"},
    {"slug": "linearapp", "name": "Linear"},
    {"slug": "supabase", "name": "Supabase"},
    {"slug": "neon", "name": "Neon"},
    {"slug": "neondatabase", "name": "Neon"},
    {"slug": "sourcegraph", "name": "Sourcegraph"},
    {"slug": "snyk", "name": "Snyk"},
    {"slug": "sentry", "name": "Sentry"},
    {"slug": "sentryio", "name": "Sentry"},
    {"slug": "hashicorp", "name": "HashiCorp"},
    {"slug": "pulumi", "name": "Pulumi"},
    {"slug": "temporal", "name": "Temporal"},
    {"slug": "temporalio", "name": "Temporal"},
    {"slug": "temporaltechnologies", "name": "Temporal"},
    {"slug": "grafana", "name": "Grafana Labs"},
    {"slug": "grafanalabs", "name": "Grafana Labs"},
    {"slug": "grafana-labs", "name": "Grafana Labs"},
    {"slug": "render", "name": "Render"},
    {"slug": "renderco", "name": "Render"},
    {"slug": "railway", "name": "Railway"},
    {"slug": "railwayapp", "name": "Railway"},
    
    # Security
    {"slug": "1password", "name": "1Password"},
    {"slug": "onepassword", "name": "1Password"},
    {"slug": "wiz", "name": "Wiz"},
    {"slug": "wizinc", "name": "Wiz"},
    {"slug": "wizio", "name": "Wiz"},
    {"slug": "crowdstrike", "name": "CrowdStrike"},
    {"slug": "lacework", "name": "Lacework"},
    {"slug": "orca-security", "name": "Orca Security"},
    {"slug": "orcasecurity", "name": "Orca Security"},
    {"slug": "stytch", "name": "Stytch"},
    {"slug": "workos", "name": "WorkOS"},
    
    # B2B SaaS
    {"slug": "hubspot", "name": "HubSpot"},
    {"slug": "zendesk", "name": "Zendesk"},
    {"slug": "monday", "name": "monday.com"},
    {"slug": "mondaycom", "name": "monday.com"},
    {"slug": "gong", "name": "Gong"},
    {"slug": "gongio", "name": "Gong"},
    {"slug": "outreach", "name": "Outreach"},
    {"slug": "outreachio", "name": "Outreach"},
    {"slug": "attentive", "name": "Attentive"},
    {"slug": "attentivemobile", "name": "Attentive"},
    {"slug": "loom", "name": "Loom"},
    {"slug": "loomhq", "name": "Loom"},
    {"slug": "miro", "name": "Miro"},
    {"slug": "realtimeboard", "name": "Miro"},
    {"slug": "canva", "name": "Canva"},
    
    # E-commerce
    {"slug": "shopify", "name": "Shopify"},
    {"slug": "doordash", "name": "DoorDash"},
    {"slug": "etsy", "name": "Etsy"},
    {"slug": "etsyinc", "name": "Etsy"},
    {"slug": "goat", "name": "GOAT"},
    {"slug": "goatgroup", "name": "GOAT"},
    {"slug": "stockx", "name": "StockX"},
    {"slug": "shippo", "name": "Shippo"},
    {"slug": "goshippo", "name": "Shippo"},
    
    # Consumer
    {"slug": "spotify", "name": "Spotify"},
    {"slug": "spotifyjobs", "name": "Spotify"},
    {"slug": "netflix", "name": "Netflix"},
    {"slug": "netflixjobs", "name": "Netflix"},
    {"slug": "airbnb", "name": "Airbnb"},
    {"slug": "snap", "name": "Snap"},
    {"slug": "snapchat", "name": "Snap"},
    {"slug": "snapinc", "name": "Snap"},
    
    # Health
    {"slug": "headspace", "name": "Headspace"},
    {"slug": "noom", "name": "Noom"},
    {"slug": "noominc", "name": "Noom"},
    {"slug": "whoop", "name": "WHOOP"},
    {"slug": "ro", "name": "Ro"},
    {"slug": "rohealth", "name": "Ro"},
    {"slug": "hims", "name": "Hims & Hers"},
    {"slug": "himshers", "name": "Hims & Hers"},
    {"slug": "forhims", "name": "Hims & Hers"},
    {"slug": "tempus", "name": "Tempus"},
    {"slug": "tempuslabs", "name": "Tempus"},
]


def check_slug(slug: str) -> dict:
    """Check if a Greenhouse slug is valid"""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            job_count = len(data.get('jobs', []))
            return {"valid": True, "jobs": job_count}
        return {"valid": False, "status": response.status_code}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def main():
    print("🔍 Validating Greenhouse slugs...\n")
    
    valid = []
    invalid = []
    
    # Group by company name
    checked_companies = set()
    
    for company in COMPANIES_TO_CHECK:
        slug = company["slug"]
        name = company["name"]
        
        # Skip if we already found a valid slug for this company
        if name in checked_companies:
            continue
        
        result = check_slug(slug)
        time.sleep(0.3)  # Rate limit
        
        if result["valid"] and result["jobs"] > 0:
            print(f"  ✅ {name}: {slug} ({result['jobs']} jobs)")
            valid.append({"slug": slug, "name": name, "jobs": result["jobs"]})
            checked_companies.add(name)
        else:
            # Don't print invalid - we're trying variations
            pass
    
    # Now print companies we couldn't find
    all_names = set(c["name"] for c in COMPANIES_TO_CHECK)
    not_found = all_names - checked_companies
    
    print(f"\n{'='*50}")
    print(f"✅ Found: {len(valid)} companies")
    print(f"❌ Not found: {len(not_found)} companies")
    
    if not_found:
        print(f"\n⚠ Could not find valid slugs for:")
        for name in sorted(not_found):
            print(f"  • {name}")
    
    # Output valid companies for copy-paste
    print(f"\n{'='*50}")
    print("📋 VALID COMPANIES (copy to companies.py):")
    print("{'='*50}\n")
    
    for c in sorted(valid, key=lambda x: x["jobs"], reverse=True):
        print(f'    {{"slug": "{c["slug"]}", "name": "{c["name"]}", "industry": "TODO"}},  # {c["jobs"]} jobs')


if __name__ == "__main__":
    main()