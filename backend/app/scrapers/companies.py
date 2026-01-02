# backend/app/scrapers/companies.py
"""
Centralized company registry for all ATS platforms.
Single source of truth for which companies to scrape.

Last updated: Verified slugs for Greenhouse, Lever, and Ashby
"""

from typing import List, Dict, Optional

# =============================================
# COMPANY REGISTRY
# =============================================

COMPANIES = [
    # ===================================================================================
    # GREENHOUSE (80 companies - verified)
    # ===================================================================================
    
    # AI / ML
    {"slug": "anthropic", "name": "Anthropic", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "stabilityai", "name": "Stability AI", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "jasper", "name": "Jasper", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "assemblyai", "name": "AssemblyAI", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "grammarly", "name": "Grammarly", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "descript", "name": "Descript", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "scaleai", "name": "Scale AI", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "runwayml", "name": "Runway", "ats": "greenhouse", "industry": "AI/ML"},
    {"slug": "labelbox", "name": "Labelbox", "ats": "greenhouse", "industry": "AI/ML"},

    # Fintech
    {"slug": "stripe", "name": "Stripe", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "coinbase", "name": "Coinbase", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "affirm", "name": "Affirm", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "brex", "name": "Brex", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "sofi", "name": "SoFi", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "robinhood", "name": "Robinhood", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "nubank", "name": "Nubank", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "chime", "name": "Chime", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "mercury", "name": "Mercury", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "marqeta", "name": "Marqeta", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "monzo", "name": "Monzo", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "gusto", "name": "Gusto", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "justworks", "name": "Justworks", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "carta", "name": "Carta", "ats": "greenhouse", "industry": "Fintech"},
    {"slug": "adyen", "name": "Adyen", "ats": "greenhouse", "industry": "Fintech"},


    # Data / Analytics
    {"slug": "databricks", "name": "Databricks", "ats": "greenhouse", "industry": "Data/Analytics"},
    {"slug": "datadog", "name": "Datadog", "ats": "greenhouse", "industry": "Data/Analytics"},
    {"slug": "amplitude", "name": "Amplitude", "ats": "greenhouse", "industry": "Data/Analytics"},
    {"slug": "mixpanel", "name": "Mixpanel", "ats": "greenhouse", "industry": "Data/Analytics"},
    {"slug": "planetscale", "name": "PlanetScale", "ats": "greenhouse", "industry": "Data/Analytics"},
    {"slug": "fivetran", "name": "Fivetran", "ats": "greenhouse", "industry": "Data/Analytics"},
    {"slug": "clickhouse", "name": "ClickHouse", "ats": "greenhouse", "industry": "Data/Analytics"},
    {"slug": "starburst", "name": "Starburst", "ats": "greenhouse", "industry": "Data/Analytics"},

    # Security
    {"slug": "cloudflare", "name": "Cloudflare", "ats": "greenhouse", "industry": "Security"},
    {"slug": "zscaler", "name": "Zscaler", "ats": "greenhouse", "industry": "Security"},
    {"slug": "okta", "name": "Okta", "ats": "greenhouse", "industry": "Security"},
    {"slug": "wizinc", "name": "Wiz", "ats": "greenhouse", "industry": "Security"},
    {"slug": "orcasecurity", "name": "Orca Security", "ats": "greenhouse", "industry": "Security"},

    # Developer Tools
    {"slug": "gitlab", "name": "GitLab", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "postman", "name": "Postman", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "vercel", "name": "Vercel", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "webflow", "name": "Webflow", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "netlify", "name": "Netlify", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "circleci", "name": "CircleCI", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "launchdarkly", "name": "LaunchDarkly", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "retool", "name": "Retool", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "apollographql", "name": "Apollo GraphQL", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "figma", "name": "Figma", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "grafanalabs", "name": "Grafana Labs", "ats": "greenhouse", "industry": "Developer Tools"},
    {"slug": "temporal", "name": "Temporal", "ats": "greenhouse", "industry": "Developer Tools"},

    # B2B SaaS
    {"slug": "braze", "name": "Braze", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "intercom", "name": "Intercom", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "asana", "name": "Asana", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "klaviyo", "name": "Klaviyo", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "clickup", "name": "ClickUp", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "airtable", "name": "Airtable", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "calendly", "name": "Calendly", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "salesloft", "name": "SalesLoft", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "pendo", "name": "Pendo", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "lattice", "name": "Lattice", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "remote", "name": "Remote", "ats": "greenhouse", "industry": "B2B SaaS"},
    {"slug": "gongio", "name": "Gong", "ats": "greenhouse", "industry": "B2B SaaS"},

    # E-commerce / Marketplace
    {"slug": "instacart", "name": "Instacart", "ats": "greenhouse", "industry": "E-commerce"},
    {"slug": "flexport", "name": "Flexport", "ats": "greenhouse", "industry": "E-commerce"},
    {"slug": "faire", "name": "Faire", "ats": "greenhouse", "industry": "E-commerce"},
    {"slug": "offerup", "name": "OfferUp", "ats": "greenhouse", "industry": "E-commerce"},
    {"slug": "mercari", "name": "Mercari", "ats": "greenhouse", "industry": "E-commerce"},
    {"slug": "goatgroup", "name": "GOAT", "ats": "greenhouse", "industry": "E-commerce"},
    {"slug": "stockx", "name": "StockX", "ats": "greenhouse", "industry": "E-commerce"},

    # Consumer / Social
    {"slug": "reddit", "name": "Reddit", "ats": "greenhouse", "industry": "Consumer/Social"},
    {"slug": "pinterest", "name": "Pinterest", "ats": "greenhouse", "industry": "Consumer/Social"},
    {"slug": "discord", "name": "Discord", "ats": "greenhouse", "industry": "Consumer/Social"},
    {"slug": "twitch", "name": "Twitch", "ats": "greenhouse", "industry": "Consumer/Social"},
    {"slug": "dropbox", "name": "Dropbox", "ats": "greenhouse", "industry": "Consumer/Social"},
    {"slug": "airbnb", "name": "Airbnb", "ats": "greenhouse", "industry": "Consumer/Social"},

    # Transportation
    {"slug": "lyft", "name": "Lyft", "ats": "greenhouse", "industry": "Transportation"},

    # Health / Wellness
    {"slug": "oura", "name": "Oura", "ats": "greenhouse", "industry": "Health/Wellness"},
    {"slug": "peloton", "name": "Peloton", "ats": "greenhouse", "industry": "Health/Wellness"},
    {"slug": "calm", "name": "Calm", "ats": "greenhouse", "industry": "Health/Wellness"},

    # Education
    {"slug": "duolingo", "name": "Duolingo", "ats": "greenhouse", "industry": "Education"},
    {"slug": "coursera", "name": "Coursera", "ats": "greenhouse", "industry": "Education"},
    {"slug": "masterclass", "name": "MasterClass", "ats": "greenhouse", "industry": "Education"},

    # ===================================================================================
    # LEVER (7 companies - verified)
    # ===================================================================================
    {"slug": "spotify", "name": "Spotify", "ats": "lever", "industry": "Consumer/Social"},
    {"slug": "palantir", "name": "Palantir", "ats": "lever", "industry": "Data/Analytics"},
    {"slug": "zoox", "name": "Zoox", "ats": "lever", "industry": "Transportation"},
    {"slug": "plaid", "name": "Plaid", "ats": "lever", "industry": "Fintech"},
    {"slug": "anchorage", "name": "Anchorage Digital", "ats": "lever", "industry": "Fintech"},
    {"slug": "pipedrive", "name": "Pipedrive", "ats": "lever", "industry": "B2B SaaS"},
    {"slug": "revel", "name": "Revel", "ats": "lever", "industry": "E-commerce"},

    # ===================================================================================
    # ASHBY (33 companies - verified)
    # ===================================================================================
    
    # AI / ML
    {"slug": "openai", "name": "OpenAI", "ats": "ashby", "industry": "AI/ML"},
    {"slug": "cohere", "name": "Cohere", "ats": "ashby", "industry": "AI/ML"},
    {"slug": "perplexity", "name": "Perplexity", "ats": "ashby", "industry": "AI/ML"},
    {"slug": "anyscale", "name": "Anyscale", "ats": "ashby", "industry": "AI/ML"},
    {"slug": "modal", "name": "Modal", "ats": "ashby", "industry": "AI/ML"},

    # Fintech
    {"slug": "ramp", "name": "Ramp", "ats": "ashby", "industry": "Fintech"},
    {"slug": "unit", "name": "Unit", "ats": "ashby", "industry": "Fintech"},
    {"slug": "column", "name": "Column", "ats": "ashby", "industry": "Fintech"},

    # Data / Analytics
    {"slug": "neon", "name": "Neon", "ats": "ashby", "industry": "Data/Analytics"},
    {"slug": "posthog", "name": "PostHog", "ats": "ashby", "industry": "Data/Analytics"},
    {"slug": "fullstory", "name": "FullStory", "ats": "ashby", "industry": "Data/Analytics"},

    # Security
    {"slug": "vanta", "name": "Vanta", "ats": "ashby", "industry": "Security"},
    {"slug": "drata", "name": "Drata", "ats": "ashby", "industry": "Security"},
    {"slug": "clerk", "name": "Clerk", "ats": "ashby", "industry": "Security"},
    {"slug": "stytch", "name": "Stytch", "ats": "ashby", "industry": "Security"},
    {"slug": "persona", "name": "Persona", "ats": "ashby", "industry": "Security"},

    # Developer Tools
    {"slug": "supabase", "name": "Supabase", "ats": "ashby", "industry": "Developer Tools"},
    {"slug": "linear", "name": "Linear", "ats": "ashby", "industry": "Developer Tools"},
    {"slug": "render", "name": "Render", "ats": "ashby", "industry": "Developer Tools"},
    {"slug": "railway", "name": "Railway", "ats": "ashby", "industry": "Developer Tools"},
    {"slug": "resend", "name": "Resend", "ats": "ashby", "industry": "Developer Tools"},
    {"slug": "sentry", "name": "Sentry", "ats": "ashby", "industry": "Developer Tools"},
    {"slug": "docker", "name": "Docker", "ats": "ashby", "industry": "Developer Tools"},
    {"slug": "sanity", "name": "Sanity", "ats": "ashby", "industry": "Developer Tools"},

    # B2B SaaS
    {"slug": "notion", "name": "Notion", "ats": "ashby", "industry": "B2B SaaS"},
    {"slug": "zapier", "name": "Zapier", "ats": "ashby", "industry": "B2B SaaS"},
    {"slug": "gamma", "name": "Gamma", "ats": "ashby", "industry": "B2B SaaS"},
    {"slug": "deel", "name": "Deel", "ats": "ashby", "industry": "B2B SaaS"},
    {"slug": "oyster", "name": "Oyster", "ats": "ashby", "industry": "B2B SaaS"},
    {"slug": "leapsome", "name": "Leapsome", "ats": "ashby", "industry": "B2B SaaS"},

    # Health / Biotech
    {"slug": "benchling", "name": "Benchling", "ats": "ashby", "industry": "Health/Biotech"},

    # HR / Recruiting
    {"slug": "ashby", "name": "Ashby", "ats": "ashby", "industry": "HR/Recruiting"},
]


# =============================================
# HELPER FUNCTIONS
# =============================================

def get_all_companies() -> List[Dict]:
    """Get all companies"""
    return COMPANIES


def get_companies_by_ats(ats: str) -> List[Dict]:
    """Get all companies using a specific ATS"""
    return [c for c in COMPANIES if c["ats"] == ats]


def get_slugs_by_ats(ats: str) -> List[str]:
    """Get just the slugs for a specific ATS"""
    return [c["slug"] for c in COMPANIES if c["ats"] == ats]


def get_all_industries() -> List[str]:
    """Get unique industries"""
    return sorted(set(c["industry"] for c in COMPANIES))


def get_companies_by_industry(industry: str) -> List[Dict]:
    """Get all companies in a specific industry"""
    return [c for c in COMPANIES if c["industry"] == industry]


def get_company_by_slug(slug: str) -> Optional[Dict]:
    """Get company info by slug"""
    for c in COMPANIES:
        if c["slug"] == slug:
            return c
    return None


def get_ats_for_slug(slug: str) -> Optional[str]:
    """Get the ATS type for a company slug"""
    company = get_company_by_slug(slug)
    return company["ats"] if company else None


def get_all_ats_types() -> List[str]:
    """Get unique ATS types"""
    return sorted(set(c["ats"] for c in COMPANIES))


def get_company_count_by_ats() -> Dict[str, int]:
    """Get count of companies per ATS"""
    counts = {}
    for c in COMPANIES:
        ats = c["ats"]
        counts[ats] = counts.get(ats, 0) + 1
    return counts


def get_stats() -> Dict:
    """Get summary statistics"""
    return {
        'total_companies': len(COMPANIES),
        'by_ats': get_company_count_by_ats(),
        'by_industry': {ind: len(get_companies_by_industry(ind)) for ind in get_all_industries()}
    }


# =============================================
# QUICK STATS (run directly)
# =============================================

if __name__ == "__main__":
    print("Company Registry Stats")
    print("=" * 50)
    print(f"Total companies: {len(COMPANIES)}")
    print()
    
    print("By ATS:")
    for ats, count in sorted(get_company_count_by_ats().items()):
        print(f"  {ats}: {count}")
    print()
    
    print("By Industry:")
    for industry in get_all_industries():
        count = len(get_companies_by_industry(industry))
        print(f"  {industry}: {count}")