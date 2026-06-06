"""
Manual enrichment for companies the API couldn't handle.
Only includes companies we're confident about from training data.

Usage:
    cd backend
    DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/enrich_companies_manual.py [--apply]
"""
import os, sys

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)

from app import create_app
from app.models import Company, db

APPLY = '--apply' in sys.argv

# name -> {field: value, ...}  — only fields we're confident about
DATA = {
    # W
    "WPP":                    {"location": "London, UK",           "founded_year": 1971, "company_type": "Public",    "valuation": "Public (NYSE: WPP)",      "website": "wpp.com"},
    "WPP Media":              {"location": "London, UK",           "founded_year": 1971, "company_type": "Subsidiary","valuation": "Public (NYSE: WPP)",      "website": "wpp.com"},
    "Woolpert":               {"location": "Dayton, OH",           "founded_year": 1911, "company_type": "Private",                                           "website": "woolpert.com"},
    "WorkBoard":              {"location": "San Francisco, CA",    "founded_year": 2013, "company_type": "Private",                                           "website": "workboard.com"},
    "Workera AI":             {"location": "San Jose, CA",         "founded_year": 2019, "company_type": "Private",                                           "website": "workera.ai"},
    "Workhelix":              {"location": "San Francisco, CA",    "founded_year": 2022, "company_type": "Private",                                           "website": "workhelix.com"},
    "Workleap - en":          {"location": "Montreal, Canada",     "founded_year": 2006, "company_type": "Private",                                           "website": "workleap.com"},
    "Workleap - fr":          {"location": "Montreal, Canada",     "founded_year": 2006, "company_type": "Private",                                           "website": "workleap.com"},
    "Workstream":             {"location": "San Jose, CA",         "founded_year": 2018, "company_type": "Private",                                           "website": "workstream.us"},
    "Workwize":               {"location": "Amsterdam, Netherlands","founded_year": 2020, "company_type": "Private",                                          "website": "workwize.com"},
    "Workato":                {"location": "San Mateo, CA",        "founded_year": 2013, "company_type": "Private",   "valuation": "$1.7B",                   "website": "workato.com"},
    "World Resources Institute": {"location": "Washington, DC",   "founded_year": 1982, "company_type": "Nonprofit",                                         "website": "wri.org"},
    "World Surf League":      {"location": "Santa Monica, CA",     "founded_year": 1976, "company_type": "Private",                                           "website": "worldsurfleague.com"},
    "WorldQuant":             {"location": "Old Greenwich, CT",    "founded_year": 2007, "company_type": "Private",                                           "website": "worldquant.com"},
    "WorldStrides":           {"location": "Charlottesville, VA",  "founded_year": 1967, "company_type": "Private",                                           "website": "worldstrides.com"},
    "WOO X":                  {"location": "Hong Kong",            "founded_year": 2019, "company_type": "Private",                                           "website": "woo.org"},
    "Wrike":                  {"location": "San Jose, CA",         "founded_year": 2006, "company_type": "Private",                                           "website": "wrike.com"},
    "Writer":                 {"location": "San Francisco, CA",    "founded_year": 2020, "company_type": "Private",   "valuation": "$1.9B",                   "website": "writer.com"},
    "Wunderkind":             {"location": "New York, NY",         "founded_year": 2010, "company_type": "Private",                                           "website": "wunderkind.co"},
    "Wurl":                   {"location": "San Jose, CA",         "founded_year": 2017, "company_type": "Private",                                           "website": "wurl.com"},
    "Wunder Capital":         {"location": "Boulder, CO",          "founded_year": 2014, "company_type": "Private",                                           "website": "wundercapital.com"},
    # X
    "xAI":                    {"location": "San Francisco, CA",    "founded_year": 2023, "company_type": "Private",   "valuation": "$50B",                    "website": "x.ai"},
    "Xaira Therapeutics":     {"location": "South San Francisco, CA","founded_year": 2024,"company_type": "Private",  "valuation": "$1B",                     "website": "xaira.com"},
    "Xapo Bank":              {"location": "Gibraltar",            "founded_year": 2013, "company_type": "Private",                                           "website": "xapo.com"},
    "Xealth":                 {"location": "Seattle, WA",          "founded_year": 2016, "company_type": "Private",                                           "website": "xealth.com"},
    "Xendit":                 {"location": "Jakarta, Indonesia",   "founded_year": 2015, "company_type": "Private",   "valuation": "$1B",                     "website": "xendit.co"},
    "Xometry":                {"location": "Gaithersburg, MD",     "founded_year": 2013, "company_type": "Public",    "valuation": "Public (NASDAQ: XMTR)",   "website": "xometry.com"},
    "XPENG":                  {"location": "Guangzhou, China",     "founded_year": 2014, "company_type": "Public",    "valuation": "Public (NYSE: XPEV)",     "website": "xpeng.com"},
    "XP Inc.":                {"location": "São Paulo, Brazil",    "founded_year": 2001, "company_type": "Public",    "valuation": "Public (NASDAQ: XP)",     "website": "xpi.com.br"},
    "XTX Markets":            {"location": "London, UK",           "founded_year": 2015, "company_type": "Private",                                           "website": "xtxmarkets.com"},
    "Xos, Inc.":              {"location": "Los Angeles, CA",      "founded_year": 2018, "company_type": "Public",    "valuation": "Public (NASDAQ: XOS)",    "website": "xostrucks.com"},
    # Y
    "Yale Investments":       {"location": "New Haven, CT",        "founded_year": 1718, "company_type": "Nonprofit",                                         "website": "yale.edu"},
    "Yalo Inc.":              {"location": "Mexico City, Mexico",  "founded_year": 2016, "company_type": "Private",                                           "website": "yalo.com"},
    "Yellowbrick Data":       {"location": "Mountain View, CA",    "founded_year": 2014, "company_type": "Private",                                           "website": "yellowbrick.com"},
    "Yext":                   {"location": "New York, NY",         "founded_year": 2006, "company_type": "Public",    "valuation": "Public (NYSE: YEXT)",     "website": "yext.com"},
    "YipitData":              {"location": "New York, NY",         "founded_year": 2010, "company_type": "Private",                                           "website": "yipitdata.com"},
    "YipitData (Alternative)":{"location": "New York, NY",         "founded_year": 2010, "company_type": "Private",                                           "website": "yipitdata.com"},
    "YLD":                    {"location": "London, UK",           "founded_year": 2013, "company_type": "Private",                                           "website": "yld.io"},
    "Ylopo":                  {"location": "El Segundo, CA",       "founded_year": 2015, "company_type": "Private",                                           "website": "ylopo.com"},
    "Yoodli AI Roleplays":    {"location": "Seattle, WA",          "founded_year": 2021, "company_type": "Private",                                           "website": "yoodli.ai"},
    "Yotpo":                  {"location": "New York, NY",         "founded_year": 2011, "company_type": "Private",   "valuation": "$1.4B",                   "website": "yotpo.com"},
    "You.com":                {"location": "San Francisco, CA",    "founded_year": 2020, "company_type": "Private",                                           "website": "you.com"},
    "Yousician":              {"location": "Helsinki, Finland",    "founded_year": 2010, "company_type": "Private",                                           "website": "yousician.com"},
    "Yubico":                 {"location": "Stockholm, Sweden",    "founded_year": 2007, "company_type": "Public",    "valuation": "Public (Nasdaq Stockholm: YUBICO)", "website": "yubico.com"},
    "Yugabyte":               {"location": "Sunnyvale, CA",        "founded_year": 2016, "company_type": "Private",                                           "website": "yugabyte.com"},
    # Z
    "Zapier":                 {"location": "Sunnyvale, CA",        "founded_year": 2011, "company_type": "Private",   "valuation": "$5B",                     "website": "zapier.com"},
    "Zipline":                {"location": "South San Francisco, CA","founded_year": 2014,"company_type": "Private",  "valuation": "$4.2B",                   "website": "zipline.com"},
    "Zocdoc":                 {"location": "New York, NY",         "founded_year": 2007, "company_type": "Private",   "valuation": "$3B",                     "website": "zocdoc.com"},
    "ZoomInfo":               {"location": "Vancouver, WA",        "founded_year": 2007, "company_type": "Public",    "valuation": "Public (NASDAQ: ZI)",     "website": "zoominfo.com"},
    "Zoox":                   {"location": "Foster City, CA",      "founded_year": 2014, "company_type": "Subsidiary","valuation": "$1.2B",                   "website": "zoox.com"},
    "Zscaler":                {"location": "San Jose, CA",         "founded_year": 2007, "company_type": "Public",    "valuation": "Public (NASDAQ: ZS)",     "website": "zscaler.com"},
    "Zuora":                  {"location": "Redwood City, CA",     "founded_year": 2007, "company_type": "Public",    "valuation": "Public (NYSE: ZUO)",      "website": "zuora.com"},
    "Zwift":                  {"location": "Long Beach, CA",       "founded_year": 2014, "company_type": "Private",   "valuation": "$1B",                     "website": "zwift.com"},
    # Sports/media
    "MLB Data Operations":    {"location": "New York, NY",         "founded_year": 1903, "company_type": "Private",                                           "website": "mlb.com"},
    "MLB FFP":                {"location": "New York, NY",         "founded_year": 1903, "company_type": "Private",                                           "website": "mlb.com"},
    "Philadelphia Eagles Game Day Staff": {"location": "Philadelphia, PA", "founded_year": 1933, "company_type": "Private", "website": "philadelphiaeagles.com"},
    "Philadelphia Phillies - Game Day":   {"location": "Philadelphia, PA", "founded_year": 1883, "company_type": "Private", "website": "phillies.com"},
    "World Surf League":      {"location": "Santa Monica, CA",     "founded_year": 1976, "company_type": "Private",                                           "website": "worldsurfleague.com"},
    # Finance/trading
    "DRW Montreal":           {"location": "Chicago, IL",          "founded_year": 1992, "company_type": "Private",                                           "website": "drw.com"},
    "Dalio Family Office":    {"location": "Westport, CT",                               "company_type": "Private",                                           "website": "bridgewater.com"},
    "XTX Markets":            {"location": "London, UK",           "founded_year": 2015, "company_type": "Private",                                           "website": "xtxmarkets.com"},
    # Media/journalism
    "ProPublica Opportunities":{"location": "New York, NY",        "founded_year": 2007, "company_type": "Nonprofit",                                         "website": "propublica.org"},
    # Education
    "UChicago Energy & Environment Lab": {"location": "Chicago, IL","founded_year": 1890,"company_type": "Nonprofit",                                         "website": "uchicago.edu"},
}

# Derive logo_url from website for all entries
for name, fields in DATA.items():
    if "website" in fields and "logo_url" not in fields:
        fields["logo_url"] = f"https://logo.clearbit.com/{fields['website']}"


app = create_app()
with app.app_context():
    updated = 0
    skipped = 0

    for name, fields in DATA.items():
        company = db.session.query(Company).filter_by(name=name, is_active=True).first()
        if not company:
            print(f"  NOT FOUND: {name}")
            skipped += 1
            continue

        changes = []
        if company.location is None and fields.get("location"):
            changes.append(f"location={fields['location']}")
            if APPLY: company.location = fields["location"]
        if company.founded_year is None and fields.get("founded_year"):
            changes.append(f"founded={fields['founded_year']}")
            if APPLY: company.founded_year = fields["founded_year"]
        if company.company_type is None and fields.get("company_type"):
            changes.append(f"type={fields['company_type']}")
            if APPLY: company.company_type = fields["company_type"]
        if company.valuation is None and fields.get("valuation"):
            changes.append(f"valuation={fields['valuation']}")
            if APPLY: company.valuation = fields["valuation"]
        if company.website is None and fields.get("website"):
            changes.append(f"website={fields['website']}")
            if APPLY: company.website = fields["website"]
        if company.logo_url is None and fields.get("logo_url"):
            changes.append(f"logo={fields['logo_url']}")
            if APPLY: company.logo_url = fields["logo_url"]

        if changes:
            print(f"  {name}: {', '.join(changes)}")
            updated += 1

    if APPLY:
        db.session.commit()

    print(f"\n{'Applied' if APPLY else 'Would update'}: {updated} companies ({skipped} not found in DB)")
    if not APPLY:
        print("Re-run with --apply to write changes.")
