#!/usr/bin/env python3
"""
Salary Extraction Script for WhatsInDemand (v5 - Fixed Extreme Values)

Fixes:
- Properly filters out funding amounts ($496M raised)
- Filters out budget requirements (budgets greater than $500K)
- Filters out company stats boilerplate
- Tighter validation ranges
- Better M/B suffix detection

Usage:
    cd backend
    python scripts/extract_salaries.py --test     # Test the parser
    python scripts/extract_salaries.py --dry-run  # Preview changes
    python scripts/extract_salaries.py            # Run for real
    python scripts/extract_salaries.py --reprocess  # Re-extract ALL jobs
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.models import db, Job
from app.utils.location_resolver import get_currency_for_location

app = create_app()


# ============================================
# SALARY VALIDATION RANGES (UPDATED v5)
# ============================================
# More realistic maximums - very few legitimate job postings exceed these

SALARY_RANGES = {
    'USD': (20000, 600000),       # Max $500K - covers most executive roles on job boards
    'EUR': (18000, 450000),       # ~$485K USD
    'GBP': (15000, 400000),       # ~$500K USD
    'CAD': (20000, 650000),       # ~$480K USD
    'AUD': (25000, 650000),       # ~$400K USD
    'NZD': (25000, 550000),       # ~$310K USD
    'INR': (150000, 30000000),    # 1.5L - 3Cr (~$360K USD max)
    'JPY': (2000000, 60000000),   # ~$400K USD max
    'CNY': (40000, 2500000),      # ~$350K USD max
    'SGD': (20000, 700000),       # ~$520K USD max
    'HKD': (100000, 4000000),     # ~$510K USD max
    'CHF': (35000, 500000),       # ~$560K USD max
    'SEK': (150000, 5000000),     # ~$460K USD max
    'NOK': (200000, 5000000),     # ~$440K USD max
    'DKK': (150000, 3500000),     # ~$505K USD max
    'PLN': (30000, 1000000),      # ~$240K USD max
    'CZK': (200000, 5000000),     # ~$210K USD max
    'BRL': (20000, 1200000),      # ~$204K USD max
    'MXN': (80000, 5000000),      # ~$290K USD max
    'ARS': (500000, 100000000),   # Hyperinflation - keep wide
    'CLP': (5000000, 300000000),  # ~$295K USD max
    'COP': (15000000, 250000000), # ~$60K USD max (Colombia salaries lower)
    'ILS': (60000, 1200000),      # ~$324K USD max
    'AED': (50000, 1800000),      # ~$490K USD max
    'SAR': (50000, 1500000),      # ~$400K USD max
    'KRW': (20000000, 300000000), # ~$207K USD max
    'TWD': (400000, 15000000),    # ~$465K USD max
    'PHP': (150000, 12000000),    # ~$204K USD max
    'MYR': (25000, 1000000),      # ~$210K USD max
    'THB': (200000, 8000000),     # ~$224K USD max
    'IDR': (50000000, 2500000000),# ~$153K USD max
    'VND': (100000000, 6000000000), # ~$234K USD max
    'ZAR': (100000, 5000000),     # ~$265K USD max
    'EGP': (100000, 5000000),     # ~$100K USD max
    'NGN': (1000000, 250000000),  # ~$153K USD max
    'PKR': (300000, 25000000),    # ~$90K USD max
}

HOURLY_RANGES = {
    'USD': (8, 300),    # Reduced max from 500 to 300
    'EUR': (8, 275),
    'GBP': (7, 250),
    'CAD': (10, 325),
    'AUD': (12, 325),
    'NZD': (12, 275),
    'INR': (50, 15000),
    'SGD': (8, 350),
    'HKD': (50, 2500),
    'CHF': (15, 350),
    'JPY': (800, 40000),
}

HOURS_PER_YEAR = 2080


# ============================================
# HELPER FUNCTIONS
# ============================================

def infer_currency_from_country(location_raw):
    """Infer currency from location using geonames database."""
    return get_currency_for_location(location_raw)


def is_internship(title):
    """Check if job title suggests it's an internship."""
    if not title:
        return False
    title_lower = title.lower()
    keywords = [
        'intern', 'internship', 'co-op', 'coop', 'apprentice', 'trainee',
        'graduate program', 'summer analyst', 'summer associate',
        'working student', 'placement', 'industrial training'
    ]
    return any(kw in title_lower for kw in keywords)


def is_non_salary_context(text: str, match_start: int, match_end: int) -> bool:
    """
    Check if a money match is clearly NOT a salary.
    Returns True if we should SKIP this match.
    """
    # Get surrounding context
    context_start = max(0, match_start - 120)
    context_end = min(len(text), match_end + 120)
    context = text[context_start:context_end].lower()
    
    matched_text = text[match_start:match_end]
    matched_lower = matched_text.lower()
    
    # === CHECK FOR M/B SUFFIX (millions/billions) ===
    # This catches $496M, $1.2B, etc.
    if re.search(r'[\$€£₹]\s*[\d,.]+\s*[mMbB]\b', matched_text):
        return True
    
    # Check what comes immediately after the match
    after_pos = match_end
    after_text = text[after_pos:after_pos + 15].strip().lower() if after_pos < len(text) else ''
    
    # If followed by 'm', 'mm', 'b', 'bn' (not 'month'), it's probably funding
    if after_text:
        if re.match(r'^[mM][mM]?\b', after_text) and not after_text.startswith('month'):
            return True
        if re.match(r'^[bB][nN]?\b', after_text):
            return True
        if re.match(r'^million|^billion', after_text):
            return True
    
    # === FUNDING / INVESTMENT PATTERNS ===
    funding_patterns = [
        r'raised\s+[\$€£]?\s*[\d,.]+',
        r'[\$€£]?\s*[\d,.]+[mMbB]?\s+(?:raised|funding|in\s+funding)',
        r'series\s+[a-z]\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
        r'(?:seed|venture|funding)\s+(?:round|of)\s+[\$€£]?\s*[\d,.]+',
        r'(?:secured|closed|announced)\s+[\$€£]?\s*[\d,.]+[mMbB]?',
        r'[\$€£]?\s*[\d,.]+[mMbB]?\s+(?:valuation|investment|round)',
        r'total\s+funding\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
        r'backed\s+by\s+[\$€£]?\s*[\d,.]+',
        r'(?:venture|vc|pe)\s+backed',
        r'funding\s+to\s+date',
    ]
    
    for pattern in funding_patterns:
        if re.search(pattern, context):
            return True
    
    # === BUDGET PATTERNS ===
    budget_patterns = [
        r'budget[s]?\s+(?:of\s+|greater\s+than\s+|over\s+|exceeding\s+|up\s+to\s+)?[\$€£]?\s*[\d,.]+',
        r'[\$€£]?\s*[\d,.]+[kKmM]?\s+budget',
        r'managing\s+(?:a\s+)?[\$€£]?\s*[\d,.]+',
        r'(?:manage|handle|oversee|responsible\s+for)\s+.*?[\$€£]?\s*[\d,.]+[kKmM]?\s+(?:budget|spend|portfolio)',
        r'(?:budget|spend|investment)\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
    ]
    
    for pattern in budget_patterns:
        if re.search(pattern, context):
            return True
    
    # === REVENUE / BUSINESS METRICS ===
    revenue_patterns = [
        r'revenue\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
        r'[\$€£]?\s*[\d,.]+[mMbB]?\s+(?:revenue|arr|mrr|gmv|aum)',
        r'(?:annual|monthly|yearly)\s+(?:revenue|recurring)',
        r'(?:generated|generating|driving|drove|grew|grown)\s+[\$€£]?\s*[\d,.]+',
        r'(?:pipeline|bookings|sales)\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
        r'[\$€£]?\s*[\d,.]+\s+(?:in\s+)?(?:revenue|sales|bookings)',
    ]
    
    for pattern in revenue_patterns:
        if re.search(pattern, context):
            return True
    
    # === COMPANY SIZE/STATS IN BOILERPLATE ===
    # Pattern: "40+ countries 15+ languages $496M raised 430,000+ community"
    boilerplate_indicators = [
        r'\d+\+?\s+(?:countries|languages|employees|customers|users|members)',
        r'community\s+(?:of\s+)?\d+',
        r'\d+[kKmM]?\+?\s+(?:community|users|customers|clients)',
        r'(?:across|in)\s+\d+\+?\s+(?:countries|markets|regions)',
        r'team\s+of\s+\d+',
        r'\d+\+?\s+(?:team\s+)?members',
    ]
    
    # If we're in a section with multiple of these patterns, be very suspicious
    boilerplate_count = sum(1 for p in boilerplate_indicators if re.search(p, context))
    if boilerplate_count >= 2:
        return True
    
    # === DISCOUNT / SAVINGS / GIFT / PERKS ===
    discount_patterns = [
        r'(?:save|saving|discount|off)\s+[\$€£]?\s*[\d,.]+',
        r'[\$€£]?\s*[\d,.]+\s+(?:off|discount|savings?|gift)',
        r'gift\s*card',
        r'(?:referral|signing|sign-on|sign\s+on)\s+bonus\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
        r'[\$€£]?\s*[\d,.]+\s+(?:referral|signing|sign-on)\s+bonus',
        r'(?:wellness|learning|education|home\s+office)\s+(?:stipend|allowance|budget)',
        r'(?:stipend|allowance)\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
    ]
    
    for pattern in discount_patterns:
        if re.search(pattern, context):
            return True
    
    # === EQUITY / STOCK (unless it's total comp context) ===
    # Only exclude if it's clearly just equity, not if it's part of total comp
    equity_only_patterns = [
        r'(?:equity|stock|rsu|options?)\s+(?:grant|award|package)\s+(?:of\s+)?[\$€£]?\s*[\d,.]+',
        r'[\$€£]?\s*[\d,.]+\s+(?:in\s+)?(?:equity|stock|rsu)',
        r'(?:vest|vesting)\s+[\$€£]?\s*[\d,.]+',
    ]
    
    # Only apply if there's no salary context nearby
    if not re.search(r'(?:salary|base|cash|compensation)\s*(?:\+|plus|and)', context):
        for pattern in equity_only_patterns:
            if re.search(pattern, context):
                return True
    
    return False


def has_explicit_salary_context(text: str, match_start: int, match_end: int) -> bool:
    """
    Check if there's explicit salary context near the match.
    For ambiguous amounts, we require explicit salary indicators.
    """
    context_start = max(0, match_start - 100)
    context_end = min(len(text), match_end + 100)
    context = text[context_start:context_end].lower()
    
    salary_indicators = [
        'salary', 'compensation', 'pay', 'wage', 'earning',
        'base', 'annual', 'yearly', 'per year', 'per annum', 'p.a.',
        '/year', '/yr', '/annum',
        'ctc', 'package', 'offer', 'lpa', 'lakhs per annum',
        'ote', 'on-target', 'on target', 'on-track',
        'cash comp', 'total comp',
    ]
    
    return any(indicator in context for indicator in salary_indicators)


def is_hourly_rate(text, value, currency='USD'):
    """Determine if a value is likely an hourly rate (explicit context only)."""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Reject non-salary contexts
    non_salary_patterns = [
        r'gift\s*card', r'stipend', r'allowance', r'save\s+\$', r'discount',
        r'purchase', r'buy\s+', r'\bprice\b', r'\bcost\b', r'\bfee\s',
        r'raised\s+\$', r'\bfunding\b', r'\brevenue\b', r'\binvestment\b',
        r'\bvaluation\b', r'market\s*cap', r'\bbudget\b', r'credit\b',
        r'reimburs', r'expense',
    ]
    for pattern in non_salary_patterns:
        if re.search(pattern, text_lower):
            return False
    
    # Require explicit hourly context
    hourly_patterns = [
        r'\$\s*[\d.,]+\s*/\s*(?:hr|hour|hourly)',
        r'\$\s*[\d.,]+\s+(?:per|an)\s+hour',
        r'hourly\s+(?:rate|pay|wage|salary|compensation)',
        r'[\d.,]+\s*/\s*(?:hr|hour)\b',
        r'[\d.,]+\s+per\s+hour',
        r'rate[:\s]+\$\s*[\d.,]+\s*/\s*h',
        r'(?:hourly|per\s+hour)[:\s]*\$',
        r'\$\s*[\d.,]+\s*(?:hr|hour)\b',
    ]
    for pattern in hourly_patterns:
        if re.search(pattern, text_lower):
            hourly_range = HOURLY_RANGES.get(currency, (8, 300))
            if hourly_range[0] <= value <= hourly_range[1]:
                return True
    
    return False


def clean_number(val):
    """Convert string to number, handling various formats."""
    if val is None:
        return None
    try:
        return float(str(val).replace(',', '').replace(' ', ''))
    except (ValueError, TypeError):
        return None


def is_reasonable(val, currency, is_annual=True):
    """Check if value is reasonable for the currency and type."""
    if val is None or val <= 0:
        return False
    ranges = SALARY_RANGES.get(currency, (20000, 600000)) if is_annual else HOURLY_RANGES.get(currency, (8, 300))
    return ranges[0] <= val <= ranges[1]


def is_likely_salary_context(text, match_start, match_end):
    """Check if a regex match is likely to be a salary vs noise."""
    
    # FIRST: Check if this is clearly NOT a salary
    if is_non_salary_context(text, match_start, match_end):
        return False
    
    context_start = max(0, match_start - 50)
    context_end = min(len(text), match_end + 50)
    context = text[context_start:context_end].lower()
    matched_text = text[match_start:match_end].lower()
    immediate_before = text[max(0, match_start - 5):match_start]
    immediate_after = text[match_end:min(len(text), match_end + 5)]
    
    # Reject URLs
    url_indicators = ['http', 'www.', '.com', '.org', '.io', '.co/', '://', '.html', '.php']
    if any(ind in context for ind in url_indicators):
        if re.search(r'https?://\S*' + re.escape(matched_text), context):
            return False
        if re.search(r'www\.\S*' + re.escape(matched_text), context):
            return False
    
    # Reject hashtags
    if '#' in immediate_before or immediate_before.endswith('#'):
        return False
    if re.search(r'#\w*' + re.escape(matched_text), context):
        return False
    
    # Reject model numbers
    model_patterns = [r'[a-zA-Z]\d+[lL]\b', r'model\s*\d+', r'version\s*\d+', r'v\d+\.\d+', r'iphone\s*\d+', r'series\s*\d+']
    for pattern in model_patterns:
        full_match = re.search(pattern, context)
        if full_match and matched_text in full_match.group(0):
            return False
    
    # Reject alphanumeric codes
    if re.match(r'[a-zA-Z]', immediate_before[-1:]):
        return False
    if re.match(r'^[a-zA-Z]', immediate_after) and not re.match(r'^[kK]\b', immediate_after):
        if not (immediate_after.lower().startswith('l') and '₹' in text[max(0, match_start-3):match_start]):
            return False
    
    # Reject LinkedIn tags
    if re.search(r'#?li-[a-z0-9]+', context, re.IGNORECASE):
        return False
    
    # Reject reference numbers
    ref_patterns = [r'ref[:\s#]*\d+', r'id[:\s#]*\d+', r'job[:\s#]*\d+', r'requisition[:\s#]*\d+', r'posting[:\s#]*\d+', r'req[:\s#]*\d+']
    for pattern in ref_patterns:
        if re.search(pattern, context):
            return False
    
    # Reject non-salary contexts
    non_salary_contexts = [
        r'years?\s+(?:of\s+)?experience', r'experience\s*[:]\s*\d+', r'\d+\s*\+?\s*years?',
        r'\d+\s*months?', r'\d+\s*days?', r'\d+\s*hours?', r'\d+\s*weeks?',
        r'team\s+of\s+\d+', r'\d+\s*people', r'\d+\s*employees', r'\d+\s*customers',
        r'\d+\s*users', r'\d+\s*members', r'\d+\s*locations', r'\d+\s*countries',
        r'\d+\s*offices', r'founded\s+(?:in\s+)?\d+', r'since\s+\d+', r'established\s+\d+',
        r'\d+\s*%', r'top\s*\d+', r'#\d+',
    ]
    for pattern in non_salary_contexts:
        non_salary_match = re.search(pattern, context)
        if non_salary_match:
            ns_start = context_start + non_salary_match.start()
            ns_end = context_start + non_salary_match.end()
            if not (match_end <= ns_start or match_start >= ns_end):
                return False
    
    # Require salary indicators for short matches
    salary_indicators = [
        'salary', 'compensation', 'pay', 'package', 'ctc', 'annual',
        'per year', 'per annum', 'p.a.', '/year', '/yr', 'base', 'total',
        'offer', 'range', 'between', 'from', 'upto', 'up to', 'earn',
        'earning', 'income', 'remuneration', 'wage', 'lpa', 'lakhs', 'lacs',
        '₹', 'inr', 'usd', 'eur', 'gbp', 'k/year', 'k per', 'k annually',
    ]
    if not any(ind in context for ind in salary_indicators) and len(matched_text) <= 3:
        return False
    
    return True


def validate_extracted_salary(salary_min: int, salary_max: int, currency: str) -> bool:
    """
    Final validation check on extracted salary.
    Returns True if valid, False if should be rejected.
    """
    if not salary_min or not salary_max:
        return False
    
    # Get range for currency
    ranges = SALARY_RANGES.get(currency, SALARY_RANGES.get('USD', (20000, 600000)))
    min_allowed, max_allowed = ranges
    
    # Check bounds
    if salary_min < min_allowed:
        return False
    if salary_max > max_allowed * 1.1:  # Small buffer for max
        return False
    
    # Check that range isn't inverted
    if salary_min > salary_max:
        return False
    
    # Check that range isn't absurdly wide (max > 4x min suggests parsing error)
    if salary_max > salary_min * 4:
        return False
    
    return True


# ============================================
# TEXT PRE-PROCESSING
# ============================================

def preprocess_text_for_salary(text: str) -> str:
    """
    Pre-process text to remove sections that commonly contain misleading numbers.
    """
    if not text:
        return text
    
    processed = text
    
    # Remove funding announcement patterns
    funding_removal_patterns = [
        # "raised $496M in funding"
        r'(?:we\'ve\s+|we\s+have\s+)?raised\s+[\$€£]?\s*[\d,.]+(?:\.\d+)?[mMbB](?:\s+(?:in\s+)?(?:funding|from|series|to\s+date))?[^.]*\.',
        # "$496M raised"
        r'[\$€£][\d,.]+(?:\.\d+)?[mMbB]\s+(?:raised|in\s+funding|funding)[^.]*\.',
        # "Series B of $50M"
        r'series\s+[a-z]\s+(?:of\s+)?[\$€£]?\s*[\d,.]+[mMbB][^.]*\.',
        # "backed by $100M"
        r'backed\s+by\s+[\$€£]?\s*[\d,.]+[mMbB][^.]*\.',
        # "valued at $1B"
        r'valued\s+at\s+[\$€£]?\s*[\d,.]+[mMbB][^.]*\.',
        # "$500M valuation"
        r'[\$€£][\d,.]+[mMbB]\s+valuation[^.]*\.',
    ]
    
    for pattern in funding_removal_patterns:
        processed = re.sub(pattern, ' [FUNDING_REMOVED] ', processed, flags=re.IGNORECASE)
    
    # Remove company stats boilerplate
    # Pattern: "40+ countries 15+ languages $496M raised 430,000+ members"
    stats_pattern = r'(?:\d+\+?\s+(?:countries|languages|employees|customers|users|members|offices)[,\s;]*){2,}[\$€£]?[\d,.]+[mMbB]?[^.]*'
    processed = re.sub(stats_pattern, ' [STATS_REMOVED] ', processed, flags=re.IGNORECASE)
    
    return processed


# ============================================
# MAIN SALARY PARSER
# ============================================

def parse_salary_from_text(text, title=None, country=None):
    """Extract salary range from job description text."""
    if not text:
        return None
    
    # Pre-process to remove misleading sections
    text_cleaned = preprocess_text_for_salary(text)
    
    default_currency = infer_currency_from_country(country)
    currency = default_currency
    
    # Normalize text
    text_normalized = text_cleaned.replace('–', '-').replace('—', '-').replace('−', '-')
    text_normalized = re.sub(r'\$\s+', '$', text_normalized)
    text_normalized = re.sub(r'£\s+', '£', text_normalized)
    text_normalized = re.sub(r'€\s+', '€', text_normalized)
    
    patterns = [
        (r'₹?\s*([\d.]+)\s*(?:L|lakhs?|lacs?)\s*[-–—to]+\s*₹?\s*([\d.]+)\s*(?:L|lakhs?|lacs?|LPA|lpa)?\b', 'lakh_range'),
        (r'([\d.]+)\s*[-–—to]+\s*([\d.]+)\s*(?:LPA|lpa|L\.?P\.?A\.?|lakhs?|lacs?)\b', 'lakh_range'),
        (r'₹?\s*([\d.]+)\s*(?:LPA|lpa|L\.?P\.?A\.?|lakhs?|lacs?|L)\b', 'lakh_single'),
        (r'[ACSNHK]{1,2}\$\s*([\d.]+)\s*[kK]\s*[-–—to]+\s*[ACSNHK]{0,2}\$?\s*([\d.]+)\s*[kK]', 'prefixed_k_range'),
        (r'[ACSNHK]{1,2}\$\s*([\d,]+(?:\.\d+)?)\s*[-–—to]+\s*[ACSNHK]{0,2}\$?\s*([\d,]+(?:\.\d+)?)', 'prefixed_range'),
        (r'[\$£€]\s*([\d.]+)\s*[kK]\s*[-–—to]+\s*[\$£€]?\s*([\d.]+)\s*[kK]', 'k_range'),
        (r'[\$£€]\s*([\d.]+)\s*[kK]\s*[-–—to]+\s*[\$£€]?\s*([\d,]+)(?![kK\d])', 'k_to_full_range'),
        (r'[\$£€]\s*([\d,]+)\s*[-–—to]+\s*[\$£€]?\s*([\d.]+)\s*[kK]', 'full_to_k_range'),
        (r'[\$£€]\s*([\d.]+)\s*[kK](?:[\s/,.\-+;)]|per|annum|annual|year|$)', 'k_single'),
        (r'[\$£€₹]\s*([\d,]+(?:\.\d+)?)\s*(?:to|TO|To)\s*[\$£€₹]?\s*([\d,]+(?:\.\d+)?)', 'standard_range_to'),
        (r'[\$£€₹]\s*([\d,]+(?:\.\d+)?)\s*-\s*[\$£€₹]?\s*([\d,]+(?:\.\d+)?)', 'standard_range_dash'),
        (r'[\$£€]\s*([\d,]+(?:\.\d+)?)\s*(?:/\s*(?:hr|hour|h\b)|per\s+hour)', 'hourly'),
        (r'[\$£€]\s*([\d,]+(?:\.\d+)?)\s*[kK]?\s*(?:/\s*(?:year|yr|annum|annual|p\.?a\.?)|per\s+(?:year|annum))', 'annual_explicit'),
        (r'(?:base\s+)?(?:salary|compensation|pay|package)[:\s]+[\$£€₹]\s*([\d,]+(?:\.\d+)?)[kK]?', 'base_salary'),
        (r'(?:USD|EUR|GBP|CAD|AUD|SGD)\s*([\d,]+(?:\.\d+)?)\s*[kK]?', 'code_prefix'),
        (r'([\d,]+(?:\.\d+)?)\s*[kK]?\s*(?:USD|EUR|GBP|CAD|AUD|SGD)', 'code_suffix'),
        (r'[\$£€₹]\s*([\d,]+(?:\.\d+)?)', 'single'),
    ]
    
    for pattern, pattern_type in patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if not match:
            continue
        
        # Skip if in a non-salary context
        if is_non_salary_context(text_normalized, match.start(), match.end()):
            continue
        
        if not is_likely_salary_context(text_normalized, match.start(), match.end()):
            continue
        
        matched_text = match.group(0)
        
        # === Check for M/B suffix after match (millions/billions) ===
        after_pos = match.end()
        after_text = text_normalized[after_pos:after_pos + 10].strip().lower() if after_pos < len(text_normalized) else ''
        
        if after_text:
            # Skip if followed by M/B suffix (funding amount, not salary)
            if re.match(r'^[mM][mM]?\b', after_text) and not after_text.startswith('month'):
                continue
            if re.match(r'^[bB][nN]?\b', after_text):
                continue
            if re.match(r'^million|^billion', after_text):
                continue
        
        # Also check within matched text
        if re.search(r'[\d.]+\s*[mMbB]\b', matched_text):
            # Contains M/B suffix - skip unless it's part of a currency code
            if not re.search(r'(?:USD|EUR|GBP|CAD|AUD)[mMbB]', matched_text):
                continue
        
        # ============================================
        # FIXED: Currency detection (now includes $ -> USD)
        # ============================================
        # ============================================
        # FIXED: Currency detection (respects country context for $)
        # ============================================
        match_currency = None
        
        # Check for prefixed dollar currencies FIRST
        if 'A$' in matched_text:
            match_currency = 'AUD'
        elif 'C$' in matched_text:
            match_currency = 'CAD'
        elif 'S$' in matched_text:
            match_currency = 'SGD'
        elif 'HK$' in matched_text:
            match_currency = 'HKD'
        elif 'NZ$' in matched_text:
            match_currency = 'NZD'
        # Then check for currency symbols
        elif '£' in matched_text:
            match_currency = 'GBP'
        elif '€' in matched_text:
            match_currency = 'EUR'
        elif '₹' in matched_text:
            match_currency = 'INR'
        # Then check for explicit currency codes
        elif re.search(r'\bCAD\b', matched_text, re.IGNORECASE):
            match_currency = 'CAD'
        elif re.search(r'\bAUD\b', matched_text, re.IGNORECASE):
            match_currency = 'AUD'
        elif re.search(r'\bUSD\b', matched_text, re.IGNORECASE):
            match_currency = 'USD'
        elif re.search(r'\bGBP\b', matched_text, re.IGNORECASE):
            match_currency = 'GBP'
        elif re.search(r'\bEUR\b', matched_text, re.IGNORECASE):
            match_currency = 'EUR'
        elif re.search(r'\bSGD\b', matched_text, re.IGNORECASE):
            match_currency = 'SGD'
        elif re.search(r'\bINR\b', matched_text, re.IGNORECASE):
            match_currency = 'INR'
        elif re.search(r'\bCHF\b', matched_text, re.IGNORECASE):
            match_currency = 'CHF'
        # Plain $ - use country-inferred currency if it's a $-based currency
        elif '$' in matched_text:
            # If country suggests a dollar-based currency, use that
            if default_currency in ['USD', 'CAD', 'AUD', 'NZD', 'SGD', 'HKD']:
                match_currency = default_currency
            else:
                # Default to USD for ambiguous cases
                match_currency = 'USD'
        
        currency = match_currency if match_currency else default_currency
        groups = match.groups()
        salary_min = None
        salary_max = None
        is_hourly_source = False
        
        if pattern_type == 'lakh_range':
            val1, val2 = clean_number(groups[0]), clean_number(groups[1])
            if val1 and val2:
                salary_min = int(min(val1, val2) * 100000)
                salary_max = int(max(val1, val2) * 100000)
                currency = 'INR'
        elif pattern_type == 'lakh_single':
            val = clean_number(groups[0])
            if val:
                salary_min = salary_max = int(val * 100000)
                currency = 'INR'
        elif pattern_type in ('prefixed_k_range', 'k_range'):
            val1, val2 = clean_number(groups[0]), clean_number(groups[1])
            if val1 and val2:
                salary_min = int(min(val1, val2) * 1000)
                salary_max = int(max(val1, val2) * 1000)
        elif pattern_type == 'prefixed_range':
            val1, val2 = clean_number(groups[0]), clean_number(groups[1])
            if val1 and val2:
                salary_min, salary_max = int(min(val1, val2)), int(max(val1, val2))
        elif pattern_type == 'k_to_full_range':
            val1, val2 = clean_number(groups[0]), clean_number(groups[1])
            if val1 and val2:
                salary_min, salary_max = int(val1 * 1000), int(val2)
                if salary_min > salary_max:
                    salary_min, salary_max = salary_max, salary_min
        elif pattern_type == 'full_to_k_range':
            val1, val2 = clean_number(groups[0]), clean_number(groups[1])
            if val1 and val2:
                salary_min, salary_max = int(val1), int(val2 * 1000)
                if salary_min > salary_max:
                    salary_min, salary_max = salary_max, salary_min
        elif pattern_type == 'k_single':
            val = clean_number(groups[0])
            if val:
                salary_min = salary_max = int(val * 1000)
        elif pattern_type in ('standard_range_to', 'standard_range_dash'):
            val1, val2 = clean_number(groups[0]), clean_number(groups[1])
            if val1 and val2:
                salary_min, salary_max = int(min(val1, val2)), int(max(val1, val2))
        elif pattern_type == 'hourly':
            val = clean_number(groups[0])
            if val and is_reasonable(val, currency, is_annual=False):
                salary_min = salary_max = int(val * HOURS_PER_YEAR)
                is_hourly_source = True
        elif pattern_type in ('annual_explicit', 'base_salary', 'code_prefix', 'code_suffix'):
            val = clean_number(groups[0])
            if val:
                salary_min = salary_max = int(val * 1000) if 'k' in match.group(0).lower() else int(val)
        elif pattern_type == 'single':
            val = clean_number(groups[0])
            if val:
                match_context = text_normalized[max(0, match.start()-30):min(len(text_normalized), match.end()+30)].lower()
                
                # Reject more non-salary keywords
                non_salary_keywords = [
                    'gift', 'card', 'stipend', 'allowance', 'save ', 'discount', 
                    'purchase', 'buy ', 'price', 'cost', 'fee', 'funding', 
                    'revenue', 'investment', 'valuation', 'budget', 'credit', 
                    'reimburs', 'expense', 'bonus of', 'referral', 'raised',
                    'series', 'venture', 'backed', 'round', 'arr', 'mrr',
                ]
                if any(kw in match_context for kw in non_salary_keywords):
                    continue
                
                # Require explicit salary context for single values
                if not has_explicit_salary_context(text_normalized, match.start(), match.end()):
                    continue
                
                if is_hourly_rate(text, val, currency):
                    if is_reasonable(val, currency, is_annual=False):
                        salary_min = salary_max = int(val * HOURS_PER_YEAR)
                        is_hourly_source = True
                elif is_internship(title) and val < 100 and currency in ['USD', 'EUR', 'GBP', 'CAD', 'AUD']:
                    if is_reasonable(val, currency, is_annual=False):
                        salary_min = salary_max = int(val * HOURS_PER_YEAR)
                        is_hourly_source = True
                elif is_reasonable(val, currency, is_annual=True):
                    salary_min = salary_max = int(val)
        
        if salary_min and salary_max:
            if salary_min > salary_max:
                salary_min, salary_max = salary_max, salary_min
            
            # FIXED: Continue to next pattern instead of returning None
            if not currency:
                continue
            
            # Final validation
            if not validate_extracted_salary(salary_min, salary_max, currency):
                continue
            
            return {
                'salary_min': salary_min,
                'salary_max': salary_max,
                'currency': currency,
                'is_hourly_source': is_hourly_source,
                'raw_match': match.group(0)
            }
    
    return None


# ============================================
# BACKFILL FUNCTION
# ============================================

def backfill_salaries(dry_run=False, reprocess=False, batch_size=500):
    """Extract salary data from job descriptions."""
    with app.app_context():
        if reprocess:
            jobs = Job.query.filter(Job.is_active == True).all()
            print(f"\n*** REPROCESS MODE: Re-extracting salaries for ALL jobs ***\n")
        else:
            jobs = Job.query.filter(Job.salary_min.is_(None), Job.is_active == True).all()
        
        total_jobs = len(jobs)
        print(f"\n{'=' * 70}")
        print(f"Salary Extraction Script v5 (Fixed Extreme Values)")
        print(f"{'=' * 70}")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        print(f"Jobs to process: {total_jobs:,}")
        print(f"{'=' * 70}\n")
        
        if total_jobs == 0:
            print("No jobs to process.")
            return
        
        updated = 0
        skipped = 0
        hourly_converted = 0
        currency_counts = {}
        examples = []
        high_salary_warnings = []
        
        for i, job in enumerate(jobs):
            text = job.description_text or job.description or ''
            country = job.location_country or job.location_raw or ''
            result = parse_salary_from_text(text, title=job.title, country=country)
            
            if result:
                if not dry_run:
                    job.salary_min = result['salary_min']
                    job.salary_max = result['salary_max']
                    job.salary_currency = result['currency']
                
                updated += 1
                curr = result['currency']
                currency_counts[curr] = currency_counts.get(curr, 0) + 1
                
                if result['is_hourly_source']:
                    hourly_converted += 1
                
                # Track high salaries for review
                if curr == 'USD' and result['salary_min'] > 350000:
                    high_salary_warnings.append({
                        'job_id': job.id,
                        'title': job.title[:40],
                        'salary': result['salary_min'],
                        'raw': result['raw_match']
                    })
                
                if len([e for e in examples if e['currency'] == curr]) < 3:
                    examples.append({
                        'title': job.title[:45],
                        'country': country[:15] if country else 'N/A',
                        'min': result['salary_min'],
                        'max': result['salary_max'],
                        'currency': curr,
                        'raw': result['raw_match'][:40]
                    })
                
                if not dry_run and updated % batch_size == 0:
                    db.session.commit()
                    print(f"Progress: {updated:,} jobs updated...")
            else:
                skipped += 1
            
            if (i + 1) % 2000 == 0:
                print(f"Processed {i + 1:,}/{total_jobs:,} jobs...")
        
        if not dry_run:
            db.session.commit()
        
        # Results
        print(f"\n{'=' * 70}")
        print(f"RESULTS")
        print(f"{'=' * 70}")
        print(f"Jobs processed: {total_jobs:,}")
        print(f"Jobs with salary: {updated:,} ({round(updated/total_jobs*100, 1) if total_jobs else 0}%)")
        print(f"  - Hourly converted: {hourly_converted:,}")
        print(f"Jobs without salary: {skipped:,}")
        
        print(f"\n{'=' * 70}")
        print(f"CURRENCY DISTRIBUTION")
        print(f"{'=' * 70}")
        for curr, count in sorted(currency_counts.items(), key=lambda x: -x[1]):
            curr_str = curr if curr else 'UNKNOWN'
            print(f"  {curr_str:7}: {count:>6,} ({round(count/updated*100, 1) if updated else 0:>5.1f}%)")
        
        if examples:
            print(f"\n{'=' * 70}")
            print(f"SAMPLE EXTRACTIONS")
            print(f"{'=' * 70}")
            for ex in examples:
                print(f"  [{ex['currency']:3}] {ex['title']:40}")
                print(f"        {ex['min']:>12,} - {ex['max']:>12,}")
                print(f"        Raw: {ex['raw']}\n")
        
        # Warning for high salaries
        if high_salary_warnings:
            print(f"\n{'=' * 70}")
            print(f"⚠️  HIGH SALARY WARNINGS ({len(high_salary_warnings)} jobs > $350K)")
            print(f"{'=' * 70}")
            for w in high_salary_warnings[:10]:
                print(f"  Job #{w['job_id']}: ${w['salary']:,} - {w['title']}")
                print(f"    Raw: {w['raw']}")
            if len(high_salary_warnings) > 10:
                print(f"  ... and {len(high_salary_warnings) - 10} more")
            print(f"\n  Review with: python scripts/diagnose_extreme_salaries.py --threshold 350000")
        
        if not dry_run:
            total_active = Job.query.filter(Job.is_active == True).count()
            with_salary = Job.query.filter(Job.is_active == True, Job.salary_min.isnot(None)).count()
            print(f"\n{'=' * 70}")
            print(f"DATABASE STATUS")
            print(f"{'=' * 70}")
            print(f"Total active: {total_active:,}")
            print(f"With salary: {with_salary:,} ({round(with_salary/total_active*100, 1)}%)")
            print(f"\n*** Run convert_salaries_to_usd.py next! ***")


# ============================================
# TEST FUNCTION
# ============================================

# ============================================
# TEST FUNCTION (FIXED)
# ============================================

def test_parser():
    """Test the parser with various formats."""
    test_cases = [
        # Standard salary formats
        ("$143,675 to $176,000", None, "United States", {'min': 143675, 'max': 176000, 'curr': 'USD'}),
        ("$120k - $150k", None, "USA", {'min': 120000, 'max': 150000, 'curr': 'USD'}),
        ("£50,000 - £70,000", None, "UK", {'min': 50000, 'max': 70000, 'curr': 'GBP'}),
        ("€60,000 - €80,000", None, "Germany", {'min': 60000, 'max': 80000, 'curr': 'EUR'}),
        ("10-15 LPA", None, "India", {'min': 1000000, 'max': 1500000, 'curr': 'INR'}),
        ("$90,000 - $120,000", None, "Canada", {'min': 90000, 'max': 120000, 'curr': 'CAD'}),
        ("$100,000 - $140,000", None, "Australia", {'min': 100000, 'max': 140000, 'curr': 'AUD'}),
        ("8L - 12L", None, "Karnataka", {'min': 800000, 'max': 1200000, 'curr': 'INR'}),
        ("Salary: $150,000 - $200,000 per year", None, "US", {'min': 150000, 'max': 200000, 'curr': 'USD'}),
        ("Base compensation: $180K - $220K", None, "US", {'min': 180000, 'max': 220000, 'curr': 'USD'}),
        
        # Hourly (should convert)
        ("$55/hr", "Software Engineer", "US", {'min': 114400, 'max': 114400, 'curr': 'USD'}),
        ("Hourly rate: $75 per hour", None, "US", {'min': 156000, 'max': 156000, 'curr': 'USD'}),
        
        # Should NOT match (funding amounts)
        ("$496M raised", None, "US", None),
        ("raised $300m in funding", None, "US", None),
        ("Series B of $50M", None, "US", None),
        ("backed by $100M", None, "US", None),
        ("$1.2B valuation", None, "US", None),
        ("We've raised $286 million", None, "US", None),
        ("40+ countries 15+ languages $496M raised 430,000+ community members", None, "US", None),
        
        # Should NOT match (budgets)
        ("managing budgets greater than $500K", None, "US", None),
        ("$2M budget for marketing", None, "US", None),
        ("experience with $1M+ budgets", None, "US", None),
        
        # Should NOT match (revenue)
        ("$10M ARR", None, "US", None),
        ("revenue of $50M", None, "US", None),
        ("driving $5M in pipeline", None, "US", None),
        
        # Should NOT match (discounts/perks)
        ("$50 gift card", None, None, None),
        ("$500 learning stipend", None, "US", None),
        ("$1000 referral bonus", None, "US", None),
        
        # Edge cases
        ("Compensation range: $200,000-$300,000 annually", None, "US", {'min': 200000, 'max': 300000, 'curr': 'USD'}),
    ]
    
    print("Testing salary parser v5...\n")
    passed = 0
    failed = 0
    
    for text, title, country, expected in test_cases:
        result = parse_salary_from_text(text, title=title, country=country)
        
        # Determine success (ensure boolean result)
        if expected is None:
            success = (result is None)
        elif result is None:
            success = False
        else:
            success = (
                result['salary_min'] == expected['min'] and 
                result['salary_max'] == expected['max'] and 
                result['currency'] == expected['curr']
            )
        
        if success:
            passed += 1
            status = "✓"
        else:
            failed += 1
            status = "✗"
        
        result_str = "None" if not result else f"{result['currency']} {result['salary_min']:,}-{result['salary_max']:,}"
        expected_str = "None" if not expected else f"{expected['curr']} {expected['min']:,}-{expected['max']:,}"
        
        # Truncate text for display
        display_text = text[:45] + "..." if len(text) > 45 else text
        
        print(f"  {status} | {(country or 'N/A')[:10]:10} | {display_text:48} | {result_str:25} | exp: {expected_str}")
        
        if not success:
            print(f"      ^ FAILED")
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}")
    
    return failed == 0

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Extract salary data from job descriptions')
    parser.add_argument('--dry-run', action='store_true', help='Preview without updating')
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--reprocess', action='store_true', help='Re-extract ALL jobs')
    args = parser.parse_args()
    
    if args.test:
        sys.exit(0 if test_parser() else 1)
    else:
        backfill_salaries(dry_run=args.dry_run, reprocess=args.reprocess)