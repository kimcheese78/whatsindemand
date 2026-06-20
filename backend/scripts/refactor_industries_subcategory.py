"""Refactor the 'Industries' subcategory into 4 specific functional subcategories
and assign `industry` tags to indicate which sector each skill belongs to.

New subcategories:
  - Sector Knowledge   : top-level sector/industry awareness (Healthcare, Banking, etc.)
  - Clinical Practice  : hands-on clinical/medical skills and specialties
  - Sciences & Research: scientific disciplines and research methodologies
  - Engineering Disciplines: domain engineering fields (Civil Eng, Chemical Eng, etc.)

Skills that don't fit any of the 4 new subcategories are reassigned to the closest
existing functional subcategory (Finance & Accounting, Business & Operations, etc.).

Run:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/refactor_industries_subcategory.py
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/refactor_industries_subcategory.py --apply
"""
import os, sys
if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from app import create_app
from app.models import db, Skill
app = create_app()
APPLY = '--apply' in sys.argv

# ─── Clinical Practice ─────────────────────────────────────────────────────
# id → industry tag (all Healthcare unless noted)
CLINICAL = {
    2028: 'Healthcare', 2136: 'Healthcare', 2042: 'Healthcare', 2212: 'Healthcare',
    2037: 'Healthcare', 2102: 'Healthcare', 2016: 'Healthcare', 2143: 'Healthcare',
    4196: 'Healthcare', 2162: 'Healthcare', 2015: 'Healthcare', 2014: 'Healthcare',
    2172: 'Healthcare', 2301: 'Healthcare', 4184: 'Healthcare', 2023: 'Healthcare',
    2055: 'Healthcare', 2075: 'Healthcare', 2178: 'Healthcare', 2074: 'Healthcare',
    2135: 'Healthcare', 2260: 'Healthcare', 2163: 'Healthcare', 1294: 'Healthcare',
    2032: 'Healthcare', 4199: 'Healthcare', 2039: 'Healthcare', 2036: 'Healthcare',
    2203: 'Healthcare', 2221: 'Healthcare', 2217: 'Healthcare',
    2267: 'Healthcare', 2067: 'Healthcare', 2133: 'Healthcare', 1295: 'Healthcare',
    2264: 'Healthcare', 2268: 'Healthcare', 2346: 'Healthcare', 2269: 'Healthcare',
    2022: 'Healthcare', 2024: 'Healthcare', 2170: 'Healthcare', 2021: 'Healthcare',
    2054: 'Healthcare', 2293: 'Healthcare', 2137: 'Healthcare', 2233: 'Healthcare',
    2245: 'Healthcare', 2056: 'Healthcare', 2013: 'Healthcare', 2094: 'Healthcare',
    2026: 'Healthcare', 2079: 'Healthcare', 2300: 'Healthcare', 2109: 'Healthcare',
    2092: 'Healthcare', 352:  'Healthcare', 2126: 'Healthcare',
    2107: 'Healthcare', 2132: 'Healthcare', 2175: 'Healthcare', 2208: 'Healthcare',
    2214: 'Healthcare', 2205: 'Healthcare', 2210: 'Healthcare', 2199: 'Healthcare',
    4193: 'Healthcare', 2019: 'Healthcare', 2020: 'Healthcare', 4123: 'Healthcare',
    2038: 'Healthcare', 2040: 'Healthcare', 2270: 'Healthcare', 2271: 'Healthcare',
    2274: 'Healthcare', 2298: 'Healthcare', 2189: 'Healthcare', 2166: 'Healthcare',
    2062: 'Healthcare', 2083: 'Healthcare', 2070: 'Healthcare', 2076: 'Healthcare',
    2322: 'Healthcare', 2165: 'Healthcare', 2302: 'Healthcare', 2304: 'Healthcare',
    2044: 'Healthcare', 4181: 'Healthcare', 4180: 'Healthcare', 4191: 'Healthcare',
    2025: 'Healthcare', 2231: 'Healthcare', 2177: 'Healthcare', 355:  'Healthcare',
    2124: 'Healthcare', 2034: 'Healthcare', 2043: 'Healthcare', 2047: 'Healthcare',
    2048: 'Healthcare', 2275: 'Healthcare', 2234: 'Healthcare', 2314: 'Healthcare',
    2305: 'Healthcare', 2307: 'Healthcare', 2077: 'Healthcare', 2197: 'Healthcare',
    4192: 'Healthcare', 2053: 'Healthcare', 2058: 'Healthcare', 2345: 'Healthcare',
    2100: 'Healthcare', 4183: 'Healthcare', 2348: 'Healthcare', 1244: 'Healthcare',
    2073: 'Healthcare', 2106: 'Healthcare', 2193: 'Healthcare', 2072: 'Healthcare',
    2116: 'Healthcare', 2090: 'Healthcare', 2311: 'Healthcare', 2313: 'Healthcare',
    2324: 'Healthcare', 356:  'Healthcare', 2127: 'Healthcare', 2294: 'Healthcare',
    2098: 'Healthcare', 2295: 'Healthcare', 2105: 'Healthcare', 2031: 'Healthcare',
    2129: 'Healthcare', 2130: 'Healthcare', 2134: 'Healthcare', 2286: 'Healthcare',
    2086: 'Healthcare', 2093: 'Healthcare', 2280: 'Healthcare', 2246: 'Healthcare',
    4114: 'Healthcare', 2215: 'Healthcare', 2139: 'Healthcare', 2141: 'Healthcare',
    2266: 'Healthcare', 4187: 'Healthcare', 4185: 'Healthcare', 2259: 'Healthcare',
    2057: 'Healthcare', 4189: 'Healthcare', 2239: 'Healthcare', 2030: 'Healthcare',
    2289: 'Healthcare', 2033: 'Healthcare', 2082: 'Healthcare', 2196: 'Healthcare',
    2334: 'Healthcare', 2066: 'Healthcare', 2061: 'Healthcare', 2258: 'Healthcare',
    2060: 'Healthcare', 2225: 'Healthcare', 2308: 'Healthcare',
    4182: 'Healthcare', 2156: 'Healthcare', 2035: 'Healthcare',
    2059: 'Healthcare', 2240: 'Healthcare', 2174: 'Healthcare', 2249: 'Healthcare',
    2263: 'Healthcare', 2290: 'Healthcare', 2257: 'Healthcare', 2351: 'Healthcare',
    2328: 'Healthcare', 353:  'Healthcare', 2078: 'Healthcare', 2117: 'Healthcare',
    2103: 'Healthcare', 2108: 'Healthcare', 2247: 'Healthcare', 2068: 'Healthcare',
    2128: 'Healthcare', 2087: 'Healthcare', 2164: 'Healthcare', 2071: 'Healthcare',
    2065: 'Healthcare', 2171: 'Healthcare', 2330: 'Healthcare', 2115: 'Healthcare',
    2242: 'Healthcare', 2253: 'Healthcare', 4194: 'Healthcare', 2182: 'Healthcare',
    2045: 'Healthcare', 2248: 'Healthcare', 2254: 'Healthcare', 2140: 'Healthcare',
    2194: 'Healthcare', 2230: 'Healthcare', 2278: 'Healthcare',
    2224: 'Healthcare', 2229: 'Healthcare', 2167: 'Healthcare', 2226: 'Healthcare',
    2282: 'Healthcare', 5358: 'Healthcare',
    1386: 'Healthcare', 2238: 'Healthcare', 2121: 'Healthcare', 2243: 'Healthcare',
    2251: 'Healthcare', 2250: 'Healthcare', 2255: 'Healthcare', 2331: 'Healthcare',
    2306: 'Healthcare', 2265: 'Healthcare', 2342: 'Healthcare', 2050: 'Healthcare',
    2341: 'Healthcare', 2273: 'Healthcare', 2291: 'Healthcare', 2344: 'Healthcare',
    2272: 'Healthcare', 2281: 'Healthcare', 2277: 'Healthcare', 2319: 'Healthcare',
    2236: 'Healthcare', 2287: 'Healthcare', 2285: 'Healthcare', 2292: 'Healthcare',
    2114: 'Healthcare', 2296: 'Healthcare', 2297: 'Healthcare', 2309: 'Healthcare',
    2131: 'Healthcare', 2123: 'Healthcare', 4197: 'Healthcare', 2190: 'Healthcare',
    2085: 'Healthcare', 2303: 'Healthcare', 4053: 'Healthcare',
    2310: 'Healthcare', 2089: 'Healthcare', 4188: 'Healthcare', 2081: 'Healthcare',
    2095: 'Healthcare', 2097: 'Healthcare', 2262: 'Healthcare', 2200: 'Healthcare',
    2204: 'Healthcare', 2195: 'Healthcare', 2191: 'Healthcare', 2207: 'Healthcare',
    2219: 'Healthcare', 2222: 'Healthcare', 2188: 'Healthcare', 2316: 'Healthcare',
    2321: 'Healthcare', 2063: 'Healthcare', 2338: 'Healthcare', 2288: 'Healthcare',
    2080: 'Healthcare', 2261: 'Healthcare', 2088: 'Healthcare', 2327: 'Healthcare',
    2335: 'Healthcare', 2326: 'Healthcare', 2052: 'Healthcare', 4198: 'Healthcare',
    2333: 'Healthcare', 2312: 'Healthcare', 2157: 'Healthcare', 4126: 'Healthcare',
    4128: 'Healthcare', 2142: 'Healthcare', 2161: 'Healthcare', 2084: 'Healthcare',
    2179: 'Healthcare', 2337: 'Healthcare', 2336: 'Healthcare', 2213: 'Healthcare',
    2187: 'Healthcare', 2343: 'Healthcare', 2347: 'Healthcare', 2096: 'Healthcare',
    2168: 'Healthcare', 2360: 'Healthcare', 2359: 'Healthcare', 2064: 'Healthcare',
    2029: 'Healthcare', 2041: 'Healthcare', 2241: 'Healthcare', 2091: 'Healthcare',
    4190: 'Healthcare', 2173: 'Healthcare', 2235: 'Healthcare', 2223: 'Healthcare',
    2069: 'Healthcare', 2349: 'Healthcare', 5379: 'Healthcare',
    2153: 'Healthcare', 2325: 'Healthcare', 2332: 'Healthcare', 2017: 'Healthcare',
    2284: 'Healthcare', 2051: 'Healthcare', 2158: 'Healthcare', 2155: 'Healthcare',
    2159: 'Healthcare', 2160: 'Healthcare', 2169: 'Healthcare', 2101: 'Healthcare',
    5380: 'Healthcare',  # RWE (Real-World Evidence)
    5379: 'Healthcare',  # Utilization Management
}

# ─── Sciences & Research ───────────────────────────────────────────────────
SCIENCES = {
    3960: 'Life Sciences',      # Astronomy → broad science
    3896: 'Life Sciences',      # Biology
    3902: 'Life Sciences',      # Biotechnology
    1728: 'Energy & Environment', # Climate Change Adaptation
    1726: 'Energy & Environment', # Climate Change Mitigation
    1729: 'Energy & Environment', # Climate Modeling
    1730: 'Energy & Environment', # Climate Resilience
    1727: 'Energy & Environment', # Climate Variability And Change
    1737: 'Energy & Environment', # Coastal Ecology
    2228: 'Life Sciences',      # Computational Neuroscience
    1731: 'Energy & Environment', # Conservation Planning
    4049: 'Life Sciences',      # Drug Development
    4052: 'Life Sciences',      # Drug Discovery
    1738: 'Energy & Environment', # Ecological Restoration
    1742: 'Energy & Environment', # Ecological Systems
    1739: 'Energy & Environment', # Ecology
    1741: 'Energy & Environment', # Ecosystem Science
    2209: 'Life Sciences',      # Experimental Psychology
    3998: 'Life Sciences',      # Genetics
    5364: 'Life Sciences',      # genetic testing
    3997: 'Life Sciences',      # Genomics
    3976: 'Energy & Environment', # Geology
    5354: 'Defense & Government', # geospatial intelligence
    1769: 'Energy & Environment', # Groundwater
    3953: 'Energy & Environment', # Hydrology
    1740: 'Energy & Environment', # Landscape Ecology
    3883: 'Life Sciences',      # Life Sciences
    5355: 'Life Sciences',      # ligand binding assays
    3969: 'Energy & Environment', # Meteorology
    4042: 'Life Sciences',      # Microbiology
    4026: 'Life Sciences',      # Molecular Biology
    1751: 'Energy & Environment', # Natural Resource Management
    4047: 'Life Sciences',      # Neuroscience
    3889: 'Life Sciences',      # Synthetic Biology
    1770: 'Agriculture',        # Soil Management
    1772: 'Agriculture',        # Soil Science
    1778: 'Energy & Environment', # Forest Management
    1779: 'Energy & Environment', # Forestry
    1735: 'Energy & Environment', # Wildlife Conservation
    1755: 'Agriculture',        # Land Management
    1784: 'Energy & Environment', # Landfill
    1782: 'Energy & Environment', # Radioactive Waste
    1771: 'Energy & Environment', # Sediment
    1785: 'Energy & Environment', # Sludge
    1768: 'Energy & Environment', # Surface Water
    1452: 'Energy & Environment', # Wastewater
    1457: 'Energy & Environment', # Water Distribution
    1766: 'Energy & Environment', # Water Pollution
    1455: 'Energy & Environment', # Water Quality
    1757: 'Energy & Environment', # Water Resource Management
    1762: 'Energy & Environment', # Water Resources
    1454: 'Energy & Environment', # Water Treatment
    1780: 'Agriculture',        # Agroforestry
    556:  'Agriculture',        # Agronomy
    558:  'Agriculture',        # Composting
    544:  'Agriculture',        # Precision Agriculture
    563:  'Agriculture',        # Pruning
    1745: 'Energy & Environment', # Environmental Degradation
    1764: 'Energy & Environment', # Environmental Emergency
    2323: 'Healthcare',         # Environmental Health (occupational health context)
    1733: 'Energy & Environment', # Environmentalism
    1761: 'Energy & Environment', # Environmental Issue
    1754: 'Energy & Environment', # Environmental Monitoring
    1760: 'Energy & Environment', # Environmental Resource Management
    1744: 'Energy & Environment', # Environmental Science
    1743: 'Energy & Environment', # Environmental Studies
    1767: 'Energy & Environment', # Environmental Technology
    1724: 'Energy & Environment', # Air Quality
    1725: 'Energy & Environment', # Greenhouse Gas
    1747: 'Energy & Environment', # Green Infrastructure
    1226: None,                 # Anthropology (academic, cross-sector)
    1240: None,                 # Archaeology
    1242: None,                 # Cultural Geography
    1269: None,                 # Prehistory
    2227: 'Life Sciences',      # Cognitive Neuroscience
    2314: 'Healthcare',         # Epidemiology
    3945: 'Healthcare',         # Clinical Trials
    352:  'Healthcare',         # Clinical Research (also in Clinical above — will be overridden by Clinical)
}

# ─── Engineering Disciplines ───────────────────────────────────────────────
ENGINEERING = {
    1463: 'Defense & Government', # Aerospace Engineering
    1484: 'Healthcare',          # Biomedical Engineering
    1483: 'Manufacturing',       # Chemical Engineering
    1519: 'Real Estate & Construction', # Civil Engineering
    1553: 'Manufacturing',       # Electrical Engineering
    1584: 'Manufacturing',       # Electronic Engineering
    1628: 'Manufacturing',       # Industrial Engineering
    1645: 'Manufacturing',       # Materials Engineering
    1638: 'Manufacturing',       # Materials Science
    1649: 'Manufacturing',       # Mechatronics
    3523: 'Manufacturing',       # Advanced Manufacturing
    3546: 'Manufacturing',       # Manufacturing Operations
    3535: 'Manufacturing',       # Manufacturing Processes
    1423: 'Energy & Environment', # Nuclear Engineering
    1430: 'Energy & Environment', # Oil And Gas
    1746: 'Energy & Environment', # Environmental Engineering
    829:  'Real Estate & Construction', # Carpentry
    831:  'Real Estate & Construction', # Masonry
    837:  'Real Estate & Construction', # Renovation
    850:  'Real Estate & Construction', # Roofing
    843:  'Real Estate & Construction', # Trenching
    839:  'Real Estate & Construction', # Painting (trades)
    3561: 'Manufacturing',       # Sewing
}

# ─── Sector Knowledge ──────────────────────────────────────────────────────
SECTOR = {
    350:  'Healthcare',          # Healthcare
    372:  'Manufacturing',       # Manufacturing
    361:  'Financial Services',  # Banking
    358:  'Retail & E-Commerce', # Retail
    366:  'Media & Entertainment', # Media
    369:  'Defense & Government', # Government
    367:  'Media & Entertainment', # Entertainment
    365:  'Media & Entertainment', # Gaming
    362:  'Financial Services',  # FinTech
    363:  'Education',           # EdTech
    364:  'Healthcare',          # HealthTech
    370:  'Defense & Government', # Aerospace (industry)
    371:  'Transportation & Logistics', # Automotive
    357:  'Retail & E-Commerce', # E-Commerce
    368:  None,                  # Nonprofit (cross-sector)
    359:  'Real Estate & Construction', # Real Estate
    926:  None,                  # Non-Profit Organization
    1350: 'Media & Entertainment', # ESports
    1352: 'Media & Entertainment', # Minecraft
    962:  None,                  # Social Entrepreneurship
    2358: 'Retail & E-Commerce', # Hospitality Management
    1349: 'Media & Entertainment', # Sports Management
    921:  'Retail & E-Commerce', # Restaurant Management
    2354: 'Retail & E-Commerce', # Restaurant Operation
    3835: 'Agriculture',         # Rural Development
    1274: None,                  # Regional Development
    1257: 'Real Estate & Construction', # Urbanization
    1278: 'Real Estate & Construction', # Urban Design
    1736: 'Real Estate & Construction', # Urban Ecology
    1277: 'Real Estate & Construction', # Urban Planning
    1280: 'Real Estate & Construction', # Urban Renewal
    1276: 'Real Estate & Construction', # Urban Sustainability
    1275: 'Transportation & Logistics', # Urban Transportation
    1311: 'Education',           # Higher Education
    4117: None,                  # Poverty Reduction
    914:  None,                  # Triple Bottom Line
    975:  None,                  # Corporate Sustainability
    1749: None,                  # Sustainable Business
    1756: None,                  # Sustainable Development
    1758: None,                  # Sustainable Management
    5373: 'Retail & E-Commerce', # CPG industry
    5374: 'Transportation & Logistics', # EV architectures
    5362: 'Defense & Government', # UAVs
    3673: 'Media & Entertainment', # News Stories
    3652: 'Financial Services',  # Auctioneering
    844:  'Real Estate & Construction', # Construction
    1516: 'Real Estate & Construction', # Public Works
    3560: 'Manufacturing',       # Textiles
    552:  'Agriculture',         # Cannabis
    553:  'Healthcare',          # Medical Cannabis
    1393: 'Energy & Environment', # Renewable Energy
    1477: 'Transportation & Logistics', # Electric Vehicles
    1479: 'Transportation & Logistics', # Autonomous Vehicles
    4134: 'Transportation & Logistics', # Aviation
    1465: 'Defense & Government', # Spacecraft
    1470: 'Defense & Government', # Spacecraft Propulsion
    1461: 'Defense & Government', # Space Exploration
    1462: 'Defense & Government', # Space Flight
    1466: 'Defense & Government', # Space Stations
    1423: 'Energy & Environment', # Nuclear Engineering (also in Engineering above)
    1426: 'Energy & Environment', # Nuclear Fuel
    2232: 'Healthcare',          # Nuclear Medicine
    1422: 'Energy & Environment', # Nuclear Power
    1424: 'Energy & Environment', # Nuclear Safety
    3908: 'Energy & Environment', # Petrochemical
    1516: 'Real Estate & Construction', # Public Works
    3848: 'Defense & Government', # Missile Guidance
    3846: 'Defense & Government', # Reconnaissance
    3850: 'Defense & Government', # Guarding
    3841: 'Real Estate & Construction', # Smoke Detector (fire safety)
    1246: None,                  # Folklore
    1268: None,                  # Cultural Studies
    1236: None,                  # Humanism
    4127: None,                  # Theology
    4129: None,                  # Religious Studies
    4130: None,                  # World Religions
    1201: None,                  # Political Economy
    1259: None,                  # Political Philosophy
    1232: None,                  # Political Sciences
    1249: None,                  # Gender Studies
    1239: None,                  # United States History
    1262: None,                  # International Studies
    1267: None,                  # Sociology
    1241: None,                  # Social Sciences
    1248: None,                  # Social Theories
    1230: None,                  # Social Change
    2211: None,                  # Social Development
    962:  None,                  # Social Entrepreneurship
    1229: None,                  # Social Progress
    2218: None,                  # Social Psychology
    1266: None,                  # Social Research
    4118: None,                  # Social Welfare
    4120: 'Healthcare',          # Social Work
    1251: None,                  # Theory Of Change
    1203: None,                  # National Income (macroeconomics concept)
    4135: 'Transportation & Logistics', # Airspace
    4131: 'Transportation & Logistics', # Air Traffic Control
    4133: 'Transportation & Logistics', # Air Traffic Flow
    4137: 'Transportation & Logistics', # Flatbed Truck Operation
    4138: 'Transportation & Logistics', # Passenger Transport
    3903: 'Manufacturing',       # Biomechanical Engineering? No wait, this may not be in the list
    5117: None,                  # AI safety → Legal & Compliance, industry: Technology
    1361: None,                  # Human Development (broad/cross-sector)
}

# ─── Reassign to other existing subcategories ─────────────────────────────
# id → (subcategory, industry)
OTHER = {
    # Finance & Accounting
    861:  ('Business & Operations', None),    # Analytic Applications
    957:  ('Business & Operations', None),    # Applied Business Technologies
    1211: ('Finance & Accounting', None),     # Econometric Modeling
    1200: ('Finance & Accounting', None),     # Macroeconomics
    1205: ('Finance & Accounting', None),     # Managerial Economics
    1878: ('Finance & Accounting', None),     # Monetary Policies
    1203: ('Finance & Accounting', None),     # National Income
    1201: ('Finance & Accounting', None),     # Political Economy
    1184: ('Finance & Accounting', None),     # Development Economics
    2339: ('Finance & Accounting', None),     # Deficits
    1211: ('Finance & Accounting', None),     # Econometric Modeling
    # Marketing & Growth
    987:  ('Marketing & Growth', None),       # Creative Strategies
    3595: ('Marketing & Growth', None),       # Mature Market
    3592: ('Business & Operations', None),    # Foreign Market
    3673: ('Marketing & Growth', 'Media & Entertainment'), # News Stories — also in SECTOR above; override
    # People & HR
    1307: ('People & HR', None),             # ALEKS (ed assessment tool)
    2237: ('People & HR', None),             # Life Skills
    1357: ('People & HR', None),             # Formative/Summative Assessments
    1364: ('People & HR', None),             # Guided Reading
    2214: ('People & HR', None),             # Cognitive Load Theory
    1317: ('People & HR', None),             # Interactive Learning
    # Business & Operations
    932:  ('Business & Operations', None),   # Feasibility Studies
    1753: ('Business & Operations', None),   # Mitigation
    1078: ('Business & Operations', None),   # Development Management
    964:  ('Business & Operations', None),   # Customer Demand Planning
    542:  ('Sciences & Research', 'Agriculture'),  # Agriculture → Sciences (keep)
    # AI/Legal
    5117: ('Legal & Compliance', 'Technology'),  # AI safety
    # Historical/academic
    1261: ('Product & Design', None),        # Architectural History
    1234: ('Sciences & Research', None),     # Historic Artifacts
    1240: ('Sciences & Research', None),     # Archaeology
    # Landscaping/land
    560:  ('Engineering Disciplines', 'Real Estate & Construction'),  # Landscaping
    561:  ('Engineering Disciplines', 'Real Estate & Construction'),  # Landscape Architecture
    1272: ('Sciences & Research', 'Energy & Environment'),            # Land Use
    # Manufacturing/food
    3503: ('Methodologies', 'Manufacturing'),     # Lean Manufacturing
    3498: ('Sciences & Research', 'Agriculture'), # Food Science
    3500: ('Manufacturing', 'Agriculture'),       # Food Manufacturing → Sector Knowledge
    # Defense
    4132: ('Sector Knowledge', 'Defense & Government'),  # Unmanned Aerial Vehicle (dup of UAVs)
    # Community/social
    1271: ('Business & Operations', None),    # Community Design
    1281: ('Business & Operations', None),    # Community Planning
    1279: ('Business & Operations', None),    # Community Sustainability
    4115: ('Business & Operations', None),    # Community Development
    2317: ('Healthcare', None),               # Community Health → Clinical Practice below; override
    1252: ('Sciences & Research', 'Life Sciences'),  # Population Dynamics
    2315: ('Healthcare', None),               # Population Health → Clinical Practice
    # Culture/society
    1334: ('Business & Operations', 'Media & Entertainment'),  # Museum Operations
    1337: ('People & HR', 'Media & Entertainment'),            # Museum Education
    1245: ('Sector Knowledge', None),         # United States History
    1238: ('Sector Knowledge', None),         # Social Issue
    1250: ('Sector Knowledge', None),         # Social Inequality
    2125: ('People & HR', 'Healthcare'),      # Social History Records
    2220: ('Sector Knowledge', None),         # Social Influences
    2318: ('Clinical Practice', 'Healthcare'), # International Health
    2340: ('Clinical Practice', 'Healthcare'), # Articulation (speech therapy)
    # Environment
    1783: ('Sciences & Research', 'Energy & Environment'),  # Waste Collection
    1786: ('Sciences & Research', 'Energy & Environment'),  # Waste Treatment
    1787: ('Sciences & Research', 'Energy & Environment'),  # Waste Management
    1734: ('Sciences & Research', 'Energy & Environment'),  # Rainwater Harvesting
    1763: ('Sciences & Research', 'Energy & Environment'),  # Restoration Ecology
    # Food/health
    2352: ('Clinical Practice', 'Healthcare'),  # Food Safety And Sanitation
    2353: ('Sector Knowledge', 'Retail & E-Commerce'),  # Food Services
    2356: ('Sciences & Research', 'Agriculture'),       # Food Security
    # Medical
    354:  ('Sector Knowledge', 'Healthcare'),   # Pharmaceutical (industry)
    2252: ('Clinical Practice', 'Healthcare'),  # Gynecology
    4139: ('Engineering Disciplines', 'Manufacturing'),  # Heavy Equipment
    4186: ('Clinical Practice', 'Healthcare'),  # Mono
    4195: ('Clinical Practice', 'Healthcare'),  # DSM
    3863: ('Marketing & Growth', 'Retail & E-Commerce'),  # Direct-to-Consumer (DTC)
}


def main():
    with app.app_context():
        now = __import__('datetime').datetime.utcnow()
        skills = {s.id: s for s in Skill.query.filter(
            Skill.is_verified == True,
            Skill.subcategory == 'Industries'
        ).all()}
        print(f'Found {len(skills)} skills with subcategory=Industries')

        counts = {'Clinical Practice': 0, 'Sciences & Research': 0,
                  'Engineering Disciplines': 0, 'Sector Knowledge': 0, 'other': 0}

        # Apply in order: OTHER overrides SECTOR/SCIENCES/ENGINEERING/CLINICAL
        for sid, s in skills.items():
            if sid in OTHER:
                sub, ind = OTHER[sid]
                if APPLY:
                    s.subcategory = sub
                    s.industry = ind
                    s.updated_at = now
                counts['other'] += 1
            elif sid in CLINICAL:
                if APPLY:
                    s.subcategory = 'Clinical Practice'
                    s.industry = CLINICAL[sid]
                    s.updated_at = now
                counts['Clinical Practice'] += 1
            elif sid in SCIENCES:
                if APPLY:
                    s.subcategory = 'Sciences & Research'
                    s.industry = SCIENCES[sid]
                    s.updated_at = now
                counts['Sciences & Research'] += 1
            elif sid in ENGINEERING:
                if APPLY:
                    s.subcategory = 'Engineering Disciplines'
                    s.industry = ENGINEERING[sid]
                    s.updated_at = now
                counts['Engineering Disciplines'] += 1
            elif sid in SECTOR:
                if APPLY:
                    s.subcategory = 'Sector Knowledge'
                    s.industry = SECTOR[sid]
                    s.updated_at = now
                counts['Sector Knowledge'] += 1
            else:
                print(f'  UNHANDLED: [{sid}] {s.name}')

        if APPLY:
            db.session.commit()
            print(f'\n✓ Committed.')
        else:
            print(f'\nDry-run:')
        for k, v in counts.items():
            print(f'  {k}: {v}')
        remaining = len(skills) - sum(counts.values())
        if remaining:
            print(f'  UNHANDLED: {remaining}')


if __name__ == '__main__':
    main()
