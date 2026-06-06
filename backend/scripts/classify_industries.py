"""
Classify Company.industry for all active companies.

Three-pass strategy:
  1. Name/domain keyword rules (fast, catches clear cases)
  2. JD intro text rules — strips HTML from description_text and applies the same
     keyword rules against the "About Company" paragraph (much richer signal)
  3. Web-search pass for companies that are still "Other" after passes 1 & 2

Canonical taxonomy (27 labels):
  AI/ML, B2B SaaS, Developer Tools, Data & Analytics, Security,
  Fintech, HealthTech, Biotech & Pharma, EdTech, E-commerce & Retail,
  Gaming, Media & Entertainment, Marketing Tech, HR Tech, Legal Tech,
  PropTech, InsurTech, Climate & Energy, Robotics & Hardware, SpaceTech,
  Automotive & Mobility, GovTech & Defense, Crypto & Web3,
  Logistics & Supply Chain, Travel & Hospitality, Consumer & Social, Other

Usage:
    cd backend
    DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python scripts/classify_industries.py [--apply] [--all]

    --apply  write changes to DB (default: dry-run)
    --all    reclassify EVERYTHING including already-canonical labels
"""
import os, sys, re, html

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)

from app import create_app
from app.models import Company, db

APPLY      = '--apply' in sys.argv
RECLASSIFY = '--all'   in sys.argv   # also reclassify canonical labels

# ── Canonical label set ───────────────────────────────────────────────────────
CANONICAL = {
    'AI/ML', 'B2B SaaS', 'Developer Tools', 'Data & Analytics', 'Security',
    'Fintech', 'HealthTech', 'Biotech & Pharma', 'EdTech', 'E-commerce & Retail',
    'Gaming', 'Media & Entertainment', 'Marketing Tech', 'HR Tech', 'Legal Tech',
    'PropTech', 'InsurTech', 'Climate & Energy', 'Robotics & Hardware', 'SpaceTech',
    'Automotive & Mobility', 'GovTech & Defense', 'Crypto & Web3',
    'Logistics & Supply Chain', 'Travel & Hospitality', 'Consumer & Social', 'Other',
}

# ── Legacy → canonical normalisation map ─────────────────────────────────────
NORMALIZE = {
    'Biotech':             'Biotech & Pharma',
    'Health/Biotech':      'Biotech & Pharma',
    'Health/Wellness':     'HealthTech',
    'Healthcare':          'HealthTech',
    'MarTech':             'Marketing Tech',
    'Data/Analytics':      'Data & Analytics',
    'Consumer/Social':     'Consumer & Social',
    'GovTech/Defense':     'GovTech & Defense',
    'CleanTech':           'Climate & Energy',
    'Energy/Climate':      'Climate & Energy',
    'Climate':             'Climate & Energy',
    'SpaceTech':           'SpaceTech',
    'Robotics':            'Robotics & Hardware',
    'Education':           'EdTech',
    'E-commerce':          'E-commerce & Retail',
    'Food Delivery':       'Logistics & Supply Chain',
    'HR/Recruiting':       'HR Tech',
    'Automotive':          'Automotive & Mobility',
    'Transportation':      'Automotive & Mobility',
    'Logistics':           'Logistics & Supply Chain',
    'Media/Entertainment': 'Media & Entertainment',
    'Media':               'Media & Entertainment',
    'Crypto/Web3':         'Crypto & Web3',
    'LegalTech':           'Legal Tech',
    'Travel':              'Travel & Hospitality',
    'Agriculture':         'Climate & Energy',
}


def _w(text, *words):
    """True if any phrase appears as a whole word / at a word boundary in text."""
    for word in words:
        if re.search(r'\b' + re.escape(word), text, re.IGNORECASE):
            return True
    return False


def _sub(text, *words):
    """True if any word appears anywhere in text (substring, case-insensitive)."""
    tl = text.lower()
    return any(w.lower() in tl for w in words)


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities; collapse whitespace."""
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def classify(name: str, website: str | None, jd_intro: str = '') -> str:
    """
    Classify a company into one canonical industry label.
    jd_intro should be the first ~800 chars of plain-text JD description.
    Rules are applied first to name/domain, then to jd_intro.
    """
    n = (name or '').lower()
    d = (website or '').lower()
    j = jd_intro.lower()          # JD intro text (already stripped of HTML)
    # domain body without scheme/www/TLD  e.g. "gong.io" → "gong"
    dom = re.sub(r'^https?://', '', d).replace('www.', '').split('.')[0].split('/')[0]

    def _check(*texts):
        """Return a checker that tests all provided text blobs."""
        combined = ' '.join(texts)
        def has_sub(*words):
            return _sub(combined, *words)
        def has_w(*words):
            return _w(combined, *words)
        return has_sub, has_w

    # Strategy: name/domain rules run on `n` (high-precision).
    # JD text runs ONLY on explicit multi-word phrases that can't appear in boilerplate.
    # Single ambiguous words (space, security, insurance, legal, travel…) are NOT
    # searched in JD text because they fire constantly on benefits paragraphs etc.

    # ════════════════════════════════════════════════════
    # PASS 1 — name + domain (high-precision, single words OK here)
    # ════════════════════════════════════════════════════

    # ── Biotech & Pharma ─────────────────────────────────────────────────────────
    if _sub(n, 'therapeutics', 'biosciences', 'bioscience', 'biologics', 'biopharma',
               'genomics', 'pharmaceut', 'biotech', 'proteomics', 'pharmacol',
               'preclinical', 'biofoundry', 'bioprocess', 'biomedicine', 'biomedical',
               'biochem', 'bioinformatics', 'biologic'):
        return 'Biotech & Pharma'
    if _sub(n, 'oncology', 'oncolog'):
        return 'Biotech & Pharma'
    if d.endswith('.bio') or re.search(r'\.bio[/.]', d):
        return 'Biotech & Pharma'

    # ── SpaceTech ────────────────────────────────────────────────────────────────
    if _sub(n, 'aerospace', 'rocket lab', 'launch vehicle', 'spacecraft', 'spacetech'):
        return 'SpaceTech'
    if _sub(n, 'orbital') and not _sub(n, 'orbital insight'):
        return 'SpaceTech'
    if _sub(n, 'satellite') and not _sub(n, 'satellite office'):
        return 'SpaceTech'
    if _w(n, 'space') and not _sub(n, 'workspace', 'namespace', 'headspace', 'mindspace',
                                        'airspace', 'backspace', 'cyberspace', 'whitespace',
                                        'greenspace', 'makerspace', 'office space',
                                        'living space', 'working space', 'open space'):
        return 'SpaceTech'

    # ── Automotive & Mobility ────────────────────────────────────────────────────
    if _sub(n, 'autonomous vehicle', 'self-driving', 'evtol', 'autonomous driving',
               'electric vehicle', 'autonomous car'):
        return 'Automotive & Mobility'
    _AUTO = {'waymo', 'wayve', 'zoox', 'motional', 'lucid motor', 'aurora ',
             'nuro ', 'rivian', 'canoo', 'moia', 'may mobility', 'parallel systems',
             'gatik', 'torc robot', 'avride', 'arc boat', 'fernride', 'bot auto',
             'scout motors', 'xpeng', 'faraday future', 'kodiak robot',
             'latitude ai', 'xos '}
    if any(k in n for k in _AUTO):
        return 'Automotive & Mobility'

    # ── Robotics & Hardware ──────────────────────────────────────────────────────
    if _sub(n, 'robotics', 'semiconductor', 'photonics', 'microelectronics',
               'chip design', 'fpga'):
        return 'Robotics & Hardware'
    if _w(n, 'robot') and not _sub(n, 'robots and pencils', 'robots.txt'):
        return 'Robotics & Hardware'

    # ── Gaming ───────────────────────────────────────────────────────────────────
    if _sub(n, 'esports', 'esport', 'game studio', 'video game', 'gaming'):
        return 'Gaming'
    if _w(n, 'games') and not _sub(n, 'gamification', 'game plan', 'game theory',
                                        'game changer', 'brain games'):
        return 'Gaming'
    if _w(n, 'game') and _sub(n, 'studio', 'interactive', 'entertainment', 'lab'):
        return 'Gaming'

    # ── Security ─────────────────────────────────────────────────────────────────
    if _sub(n, 'cybersecurity', 'cyber security', 'infosec', 'pentest', 'vulnerability',
               'threat intelligence'):
        return 'Security'
    if _w(n, 'security') and not _sub(n, 'social security'):
        return 'Security'
    if _w(n, 'cyber') and not _sub(n, 'cyberbully', 'cybermedia'):
        return 'Security'

    # ── Crypto & Web3 ────────────────────────────────────────────────────────────
    if _sub(n, 'crypto', 'blockchain', 'web3', 'bitcoin', 'ethereum',
               'digital asset', 'digital currency', 'decentralized finance',
               'smart contract', 'defi '):
        return 'Crypto & Web3'
    if _w(n, 'coin') and not _sub(n, 'coinstar', 'coincide', 'coinage'):
        return 'Crypto & Web3'

    # ── InsurTech ────────────────────────────────────────────────────────────────
    if _sub(n, 'insurance', 'insurtech', 'insuretech', 'reinsurance'):
        return 'InsurTech'

    # ── Legal Tech ───────────────────────────────────────────────────────────────
    if _sub(n, 'legaltech', 'legal tech', 'legal ai', 'legal analytics'):
        return 'Legal Tech'
    if _sub(n, 'legal') and _sub(n, 'tech', 'software', 'platform') and not _sub(n, 'paralegal'):
        return 'Legal Tech'

    # ── HealthTech ───────────────────────────────────────────────────────────────
    if _sub(n, 'telehealth', 'telemedicine', 'healthtech', 'health tech', 'digital health',
               'virtual care', 'remote patient'):
        return 'HealthTech'
    if _sub(n, 'health') and not _sub(n, 'healtheon'):
        return 'HealthTech'
    if _sub(n, 'medical', 'clinical', 'hospital', 'hospice', 'dental', 'optometry',
               'dermatology', 'cardiology', 'neurology', 'orthopedic',
               'veterinary', 'pharmacy', 'pharmacist', 'behavioral health',
               'mental health', 'rehabilitation', 'occupational therapy',
               'physical therapy', 'speech therapy', 'teletherapy', 'therapist',
               'counseling', 'psychiatry', 'psychotherapy', 'pediatric'):
        return 'HealthTech'
    if _sub(n, 'home care', 'primary care', 'urgent care', 'eye care',
               'senior care', 'elder care', 'palliative care', 'wound care',
               'animal care', 'cancer care', 'nursing home', 'assisted living'):
        return 'HealthTech'
    if _sub(dom, 'health', 'medic', 'clinic', 'dental', 'pharma'):
        return 'HealthTech'

    # ── Fintech ──────────────────────────────────────────────────────────────────
    if _sub(n, 'fintech', 'neobank', 'neo-bank', 'paytech', 'wealthtech',
               'regtech', 'open banking', 'embedded finance', 'bnpl',
               'buy now pay later'):
        return 'Fintech'
    if _sub(n, 'payment', 'payments'):
        return 'Fintech'
    if _w(n, 'bank') and not _sub(n, 'benchmark', 'food bank', 'blood bank',
                                        'memory bank', 'databank', 'riverbank'):
        return 'Fintech'
    if _sub(n, 'financial') and not _sub(n, 'financial times'):
        return 'Fintech'
    if _sub(n, 'finance') and not _sub(n, 'personal finance tips'):
        return 'Fintech'
    if _sub(n, 'lending', 'lender', 'mortgage', 'credit union'):
        return 'Fintech'
    if _w(n, 'loan') or _sub(n, 'loans'):
        return 'Fintech'
    if _sub(n, 'wealth management', 'asset management', 'investment management',
               'hedge fund', 'trading firm', 'brokerage'):
        return 'Fintech'

    # ── EdTech ───────────────────────────────────────────────────────────────────
    if _sub(n, 'edtech', 'edutech', 'e-learning', 'elearning', 'online learning',
               'online education', 'coding bootcamp', 'learning platform', 'lms '):
        return 'EdTech'
    if _sub(n, 'education', 'educational', 'educate'):
        return 'EdTech'
    if _w(n, 'school') and not _sub(n, 'school bus', 'old school'):
        return 'EdTech'
    if _sub(n, 'academy') and not _sub(n, 'military academy'):
        return 'EdTech'
    if _w(n, 'learning') and not _sub(n, 'machine learning', 'deep learning',
                                           'reinforcement learning', 'transfer learning'):
        if _sub(n, 'platform', 'solution', 'system', 'course', 'bootcamp', 'prep', 'tutor'):
            return 'EdTech'
    if _sub(n, 'tutoring', 'curriculum', 'coursework', 'university', 'college'):
        return 'EdTech'
    if _sub(dom, 'edu', 'learn', 'school', 'academ', 'tutor'):
        return 'EdTech'

    # ── Climate & Energy ─────────────────────────────────────────────────────────
    if _sub(n, 'cleantech', 'clean energy', 'clean tech', 'renewable energy',
               'green energy', 'sustainable energy', 'decarbonization', 'net zero',
               'carbon capture', 'carbon removal', 'climate tech', 'climatetech',
               'hydrogen energy', 'energy storage', 'battery tech', 'wind energy',
               'wind power', 'solar energy', 'nuclear energy', 'biomass', 'geothermal',
               'microgrid', 'energy transition', 'carbon market', 'carbon credits'):
        return 'Climate & Energy'
    if _sub(n, 'energy') and not _sub(n, 'energy drink', 'kinetic energy', 'potential energy'):
        return 'Climate & Energy'
    if _sub(n, 'solar') and not _sub(n, 'solaris'):
        return 'Climate & Energy'
    if _sub(n, 'climate') and not _sub(n, 'microclimate'):
        return 'Climate & Energy'

    # ── GovTech & Defense ────────────────────────────────────────────────────────
    if _sub(n, 'govtech', 'gov tech', 'defense tech', 'defensetech',
               'national security', 'defense contractor', 'intelligence community',
               'federal government', 'department of defense', 'military technology'):
        return 'GovTech & Defense'
    if _w(n, 'defense') and not _sub(n, 'self defense'):
        return 'GovTech & Defense'
    if _sub(n, 'armament', 'munition', 'military tech'):
        return 'GovTech & Defense'

    # ── Logistics & Supply Chain ─────────────────────────────────────────────────
    if _sub(n, 'logistics', 'supply chain', 'freight', 'last mile', 'last-mile',
               'fulfillment', 'warehouse management', 'trucking', 'fleet management',
               'courier', 'parcel', 'same-day delivery', 'cold chain',
               'load board', 'ltl ', 'truckload', 'freight brokerage'):
        return 'Logistics & Supply Chain'
    if _sub(n, 'shipping') and not _sub(n, 'drop shipping'):
        return 'Logistics & Supply Chain'
    if _sub(n, 'delivery') and not _sub(n, 'drug delivery', 'content delivery',
                                              'vaccine delivery', 'gene delivery',
                                              'email delivery', 'message delivery'):
        return 'Logistics & Supply Chain'

    # ── PropTech ─────────────────────────────────────────────────────────────────
    if _sub(n, 'proptech', 'real estate tech', 'property tech'):
        return 'PropTech'
    if _sub(n, 'real estate', 'realestate', 'realty', 'realtor'):
        return 'PropTech'

    # ── Travel & Hospitality ──────────────────────────────────────────────────────
    if _sub(n, 'traveltech', 'hospitality tech', 'hotel tech'):
        return 'Travel & Hospitality'
    if _sub(n, 'travel') and not _sub(n, 'travel nurse', 'medical travel', 'travel therapy'):
        return 'Travel & Hospitality'
    if _sub(n, 'hotel', 'hospitality', 'airline', 'aviation', 'tourism',
               'vacation rental', 'short-term rental', 'cruise line', 'resort'):
        return 'Travel & Hospitality'

    # ── Media & Entertainment ────────────────────────────────────────────────────
    if _sub(n, 'entertainment', 'broadcast', 'publishing', 'podcast', 'streaming',
               'record label', 'film studio', 'film production', 'tv network',
               'magazine', 'newspaper', 'digital media', 'content studio'):
        return 'Media & Entertainment'
    if _w(n, 'media') and not _sub(n, 'social media management', 'media buying'):
        return 'Media & Entertainment'
    if _sub(n, 'music') and not _sub(n, 'music software', 'music tech', 'music ai'):
        return 'Media & Entertainment'

    # ── Marketing Tech ───────────────────────────────────────────────────────────
    if _sub(n, 'martech', 'adtech', 'ad tech', 'marketing automation',
               'marketing analytics', 'programmatic', 'demand side platform',
               'attribution platform', 'performance marketing', 'affiliate marketing',
               'influencer marketing'):
        return 'Marketing Tech'
    if _sub(n, 'marketing') and not _sub(n, 'marketing agency'):
        return 'Marketing Tech'
    if _sub(n, 'advertising') and not _sub(n, 'advertising agency'):
        return 'Marketing Tech'

    # ── HR Tech ───────────────────────────────────────────────────────────────────
    if _sub(n, 'hrtech', 'hr tech', 'hris', 'applicant tracking',
               'recruiting platform', 'talent intelligence', 'workforce management',
               'payroll platform', 'employee engagement', 'people analytics',
               'compensation platform', 'human capital management', 'hcm ',
               'employer of record', 'eor ', 'global payroll'):
        return 'HR Tech'
    if _sub(n, 'recruiting', 'recruitment') and not _sub(n, 'firm', 'agency', 'group'):
        return 'HR Tech'
    if _sub(n, 'staffing') and _sub(n, 'tech', 'software', 'platform'):
        return 'HR Tech'
    if _sub(n, 'payroll') and _sub(n, 'tech', 'software', 'platform'):
        return 'HR Tech'

    # ── E-commerce & Retail ───────────────────────────────────────────────────────
    if _sub(n, 'ecommerce', 'e-commerce', 'online retail', 'dtc ',
               'direct-to-consumer', 'direct to consumer', 'recommerce',
               'resale platform', 'marketplace platform'):
        return 'E-commerce & Retail'
    if _sub(n, 'commerce') and not _sub(n, 'chamber of commerce', 'commerce bank'):
        return 'E-commerce & Retail'

    # ── AI/ML ─────────────────────────────────────────────────────────────────────
    if _sub(n, 'artificial intelligence', 'machine learning', 'deep learning',
               'large language model', 'llm ', 'generative ai', 'foundation model',
               'computer vision', 'neural network'):
        return 'AI/ML'
    if re.search(r'\bai\b', n) and not _sub(n, 'aid ', 'aim ', 'air ', 'aig', 'ail',
                                                    'ain', 'aio', 'ais ', 'ait', 'aiv',
                                                    'airbnb', 'airport', 'airline'):
        return 'AI/ML'
    if d.endswith('.ai'):
        return 'AI/ML'

    # ── Data & Analytics ─────────────────────────────────────────────────────────
    if _sub(n, 'analytics', 'data analytics', 'business intelligence', 'data platform',
               'data warehouse', 'data lakehouse', 'data lake', 'data mesh',
               'data observability', 'data catalog', 'data quality', 'data governance',
               'etl ', 'elt ', 'reverse etl', 'data pipeline', 'data integration',
               'event analytics', 'product analytics'):
        return 'Data & Analytics'

    # ── Developer Tools ───────────────────────────────────────────────────────────
    if _sub(n, 'developer tools', 'devtools', 'devops', 'devsecops', 'gitops',
               'ci/cd', 'continuous integration', 'cloud infrastructure',
               'infrastructure as code', 'api gateway', 'api management',
               'code editor', 'test automation', 'open source'):
        return 'Developer Tools'

    # ── Consumer & Social ────────────────────────────────────────────────────────
    if _sub(n, 'social network', 'social platform', 'community platform',
               'creator platform', 'creator economy', 'dating app', 'dating platform',
               'messaging app', 'consumer app', 'lifestyle app'):
        return 'Consumer & Social'

    # ── Domain-level fallbacks ────────────────────────────────────────────────────
    if _sub(dom, 'security', 'cyber', 'infosec'):
        return 'Security'
    if _sub(dom, 'logistics', 'freight', 'shipment', 'fleet'):
        return 'Logistics & Supply Chain'
    if _sub(dom, 'travel', 'hotel', 'hospitality', 'airline'):
        return 'Travel & Hospitality'
    if _sub(dom, 'finance', 'bank', 'fintech', 'payment', 'invest'):
        return 'Fintech'
    if _sub(dom, 'game', 'gaming', 'esport'):
        return 'Gaming'
    if _sub(dom, 'media', 'entertain', 'broadcast', 'stream'):
        return 'Media & Entertainment'
    if _sub(dom, 'robot', 'autonom', 'semiconductor'):
        return 'Robotics & Hardware'
    if _sub(dom, 'energy', 'solar', 'climate', 'cleantech'):
        return 'Climate & Energy'
    if _sub(dom, 'legal', 'lawfirm'):
        return 'Legal Tech'
    if _sub(dom, 'market', 'adtech'):
        return 'Marketing Tech'
    if _sub(dom, 'recruit', 'talent', 'workforce', 'payroll'):
        return 'HR Tech'

    # ════════════════════════════════════════════════════
    # PASS 2 — JD intro text (multi-word phrases only — avoids boilerplate false positives)
    # Single ambiguous words (space, security, insurance, legal, travel…)
    # are NOT searched here because they fire constantly in boilerplate.
    # ════════════════════════════════════════════════════
    if not j:
        return 'Other'

    # Biotech (specific compound phrases that won't appear in boilerplate)
    if _sub(j, 'drug discovery', 'gene therapy', 'cell therapy', 'clinical stage',
               'clinical-stage', 'fda approval', 'investigational new drug',
               'clinical trial', 'preclinical', 'biopharma', 'therapeutics'):
        return 'Biotech & Pharma'

    # SpaceTech
    if _sub(j, 'launch vehicle', 'satellite constellation', 'low earth orbit',
               'reusable rocket', 'cubesat', 'smallsat', 'spacecraft'):
        return 'SpaceTech'

    # Automotive (only specific phrases that are about the product, not general use)
    if _sub(j, 'autonomous vehicle', 'self-driving', 'electric vehicle', 'evtol',
               'autonomous driving', 'vehicle ownership experience', 'automotive software',
               'automotive platform', 'automotive dealer', 'vehicle lifecycle',
               'connected car', 'fleet electrification'):
        return 'Automotive & Mobility'

    # Robotics (very specific)
    if _sub(j, 'humanoid robot', 'industrial robot', 'autonomous robot',
               'robotic system', 'robot arm', 'mobile robot'):
        return 'Robotics & Hardware'

    # Gaming (unambiguous compound phrases)
    if _sub(j, 'video game', 'game development', 'game studio', 'game engine',
               'mobile game', 'console game', 'multiplayer game', 'online game',
               'game developer', 'game designer'):
        return 'Gaming'

    # Security (product-specific phrases only)
    if _sub(j, 'cybersecurity company', 'security platform', 'threat detection platform',
               'endpoint protection', 'zero trust security', 'cloud security platform',
               'security operations center', 'vulnerability management platform',
               'identity and access management', 'penetration testing firm',
               'threat intelligence platform', 'siem platform', 'xdr platform'):
        return 'Security'

    # Crypto
    if _sub(j, 'cryptocurrency', 'blockchain platform', 'digital asset platform',
               'decentralized finance', 'smart contract', 'tokenization',
               'stablecoin', 'proof of stake', 'web3 platform', 'defi protocol'):
        return 'Crypto & Web3'

    # InsurTech (product-specific, not "we offer health insurance")
    if _sub(j, 'insurance platform', 'insurance technology', 'insurance software',
               'insurance carrier', 'p&c insurance', 'property and casualty',
               'reinsurance', 'insurtech', 'digital insurance'):
        return 'InsurTech'

    # Legal Tech
    if _sub(j, 'legal technology', 'legal software', 'legal platform',
               'legal operations', 'e-discovery', 'ediscovery', 'contract management platform',
               'legal workflow', 'legal research platform', 'legal ai'):
        return 'Legal Tech'

    # HealthTech (specific product phrases)
    if _sub(j, 'digital health', 'healthcare platform', 'healthcare technology',
               'health technology', 'health platform', 'electronic health record',
               'ehr platform', 'emr platform', 'population health', 'value-based care',
               'care coordination platform', 'telehealth', 'telemedicine',
               'health data platform', 'clinical decision support', 'healthcare ai',
               'remote patient monitoring', 'virtual care platform'):
        return 'HealthTech'

    # Fintech (specific product phrases)
    if _sub(j, 'financial technology', 'fintech company', 'financial platform',
               'payments platform', 'banking platform', 'digital banking',
               'digital wallet', 'cross-border payment', 'remittance platform',
               'investment platform', 'brokerage platform', 'trading platform',
               'proprietary trading', 'quantitative trading', 'algorithmic trading',
               'embedded finance', 'open banking', 'financial infrastructure',
               'payments infrastructure', 'wealth management platform'):
        return 'Fintech'

    # EdTech (specific product phrases)
    if _sub(j, 'learning management system', 'lms platform', 'educational technology',
               'online learning platform', 'e-learning platform', 'edtech',
               'online education platform', 'k-12 platform', 'higher education platform',
               'student success platform', 'career development platform',
               'skills training platform', 'online course platform'):
        return 'EdTech'

    # Climate & Energy
    if _sub(j, 'clean energy', 'renewable energy', 'decarbonization', 'net zero',
               'carbon capture', 'energy storage', 'energy transition', 'carbon market',
               'clean technology', 'sustainable energy', 'solar energy', 'wind energy',
               'distributed energy', 'virtual power plant', 'battery storage'):
        return 'Climate & Energy'

    # GovTech & Defense
    if _sub(j, 'government software', 'public sector software', 'federal government',
               'department of defense', 'defense contractor', 'defense technology',
               'intelligence community', 'warfighter', 'military technology'):
        return 'GovTech & Defense'

    # Logistics
    if _sub(j, 'supply chain', 'logistics platform', 'freight platform',
               'last-mile delivery', 'warehouse management system',
               'fleet management platform', 'shipment tracking', 'freight brokerage',
               'carrier management', 'route optimization platform',
               'inventory management platform'):
        return 'Logistics & Supply Chain'

    # PropTech
    if _sub(j, 'real estate platform', 'real estate marketplace', 'real estate technology',
               'real estate software', 'property management platform',
               'mortgage platform', 'home buying platform', 'commercial real estate'):
        return 'PropTech'

    # Travel & Hospitality
    if _sub(j, 'travel booking', 'hotel booking', 'flight booking', 'online travel',
               'travel marketplace', 'vacation rental platform', 'travel platform',
               'hospitality platform', 'global distribution system', 'online travel agency'):
        return 'Travel & Hospitality'

    # Media & Entertainment
    if _sub(j, 'media company', 'entertainment company', 'streaming platform',
               'content platform', 'film production', 'animation studio',
               'record label', 'podcast platform', 'news organization',
               'digital media company', 'sports media', 'content studio'):
        return 'Media & Entertainment'

    # Marketing Tech
    if _sub(j, 'marketing technology', 'marketing platform', 'marketing automation',
               'customer data platform', 'demand side platform', 'ad platform',
               'adtech', 'martech', 'attribution platform', 'programmatic advertising',
               'performance marketing platform', 'affiliate marketing platform',
               'influencer marketing platform', 'email marketing platform',
               'seo platform', 'customer engagement platform'):
        return 'Marketing Tech'

    # HR Tech
    if _sub(j, 'hr platform', 'hr software', 'recruiting platform', 'talent platform',
               'workforce management platform', 'payroll platform',
               'human capital management', 'employer of record', 'global payroll',
               'talent acquisition platform', 'employee engagement platform',
               'people analytics platform', 'compensation platform',
               'performance management platform', 'background screening platform'):
        return 'HR Tech'

    # E-commerce
    if _sub(j, 'online marketplace', 'e-commerce platform', 'ecommerce platform',
               'direct-to-consumer', 'dtc brand', 'online retail platform',
               'recommerce', 'social commerce', 'resale platform', 'marketplace platform'):
        return 'E-commerce & Retail'

    # AI/ML (specific compound phrases that indicate the company's core product)
    if _sub(j, 'ai company', 'ai platform', 'ai research', 'ai safety', 'frontier ai',
               'generative ai', 'large language model', 'foundation model',
               'ai infrastructure', 'machine learning platform', 'ai-powered platform',
               'conversational ai', 'ai model', 'deep learning platform',
               'computer vision platform', 'nlp platform', 'ai lab'):
        return 'AI/ML'

    # Data & Analytics
    if _sub(j, 'data platform', 'analytics platform', 'data warehouse',
               'data lakehouse', 'business intelligence platform', 'data observability',
               'data catalog platform', 'etl platform', 'data pipeline platform',
               'data integration platform', 'revenue intelligence platform',
               'market intelligence platform'):
        return 'Data & Analytics'

    # Developer Tools
    if _sub(j, 'developer platform', 'developer tools', 'devops platform',
               'cloud infrastructure platform', 'api platform', 'ci/cd platform',
               'kubernetes platform', 'serverless platform', 'platform engineering',
               'software development platform', 'developer productivity'):
        return 'Developer Tools'

    # Consumer & Social
    if _sub(j, 'consumer platform', 'social platform', 'creator economy',
               'creator platform', 'community platform', 'peer-to-peer platform',
               'sharing economy', 'dating platform', 'messaging platform'):
        return 'Consumer & Social'

    return 'Other'


# ── Main ──────────────────────────────────────────────────────────────────────
app = create_app()
with app.app_context():
    from app.models import Job
    from sqlalchemy import text as _sql

    companies = db.session.query(Company).filter(
        Company.is_active == True
    ).order_by(Company.name).all()

    total = len(companies)
    print(f"Active companies: {total}")
    print(f"Mode: {'APPLY' if APPLY else 'DRY RUN'}{'  (reclassify all)' if RECLASSIFY else ''}\n")

    # Pre-fetch one JD description per company (first active job) in a single query.
    # We take the first 1200 chars of description (the "About Company" intro section).
    print("Fetching JD intros…")
    jd_rows = db.session.execute(_sql("""
        SELECT DISTINCT ON (j.company_id)
               j.company_id,
               LEFT(COALESCE(j.description_text, j.description, ''), 1200) AS intro
        FROM jobs j
        WHERE j.is_active = true
          AND (j.description_text IS NOT NULL OR j.description IS NOT NULL)
        ORDER BY j.company_id, j.scraped_at DESC
    """)).fetchall()
    jd_map = {row[0]: strip_html(row[1]) for row in jd_rows}
    print(f"JD intros loaded for {len(jd_map)} companies\n")

    updated = kept = 0

    for company in companies:
        old = company.industry

        # Already canonical (and not "Other") → skip unless --all
        if old in CANONICAL and old != 'Other' and not RECLASSIFY:
            kept += 1
            continue

        jd_intro = jd_map.get(company.id, '')

        # Determine target label
        if old in NORMALIZE:
            # Normalize legacy label — still try classify in case JD gives a better result
            normalized = NORMALIZE[old]
            classified = classify(company.name, company.website, jd_intro)
            # Prefer the keyword-classified result unless it's still "Other"
            new = classified if classified != 'Other' else normalized
        else:
            new = classify(company.name, company.website, jd_intro)

        if new == old:
            kept += 1
            continue

        print(f"  {company.name:<45} {str(old):<25} → {new}")
        if APPLY:
            company.industry = new
        updated += 1

    if APPLY:
        db.session.commit()

    print(f"\nSummary:")
    print(f"  Kept as-is:      {kept}")
    print(f"  {'Updated' if APPLY else 'Would update'}:        {updated}")
    if not APPLY:
        print("\nRe-run with --apply to write changes.")
