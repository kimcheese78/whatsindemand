# backend/app/utils/location_normalizer.py
"""
Centralized location normalization logic.
Used by both the locations endpoint and the job filter.
"""

import re
from typing import Optional, Set, List

# ============================================
# CANONICAL COUNTRY MAPPINGS
# ============================================

COUNTRY_TO_REGION = {
    # North America
    'United States': 'North America',
    'Canada': 'North America',
    
    # Latin America
    'Mexico': 'Latin America',
    'Brazil': 'Latin America',
    'Argentina': 'Latin America',
    'Colombia': 'Latin America',
    'Chile': 'Latin America',
    'Peru': 'Latin America',
    'Costa Rica': 'Latin America',
    'Uruguay': 'Latin America',
    'Ecuador': 'Latin America',
    
    # Europe
    'United Kingdom': 'Europe',
    'Germany': 'Europe',
    'France': 'Europe',
    'Netherlands': 'Europe',
    'Ireland': 'Europe',
    'Spain': 'Europe',
    'Italy': 'Europe',
    'Sweden': 'Europe',
    'Switzerland': 'Europe',
    'Poland': 'Europe',
    'Portugal': 'Europe',
    'Belgium': 'Europe',
    'Austria': 'Europe',
    'Denmark': 'Europe',
    'Norway': 'Europe',
    'Finland': 'Europe',
    'Czech Republic': 'Europe',
    'Romania': 'Europe',
    'Serbia': 'Europe',
    'Greece': 'Europe',
    'Luxembourg': 'Europe',
    'Hungary': 'Europe',
    'Ukraine': 'Europe',
    
    # Asia Pacific
    'India': 'Asia Pacific',
    'Australia': 'Asia Pacific',
    'Singapore': 'Asia Pacific',
    'Japan': 'Asia Pacific',
    'China': 'Asia Pacific',
    'Hong Kong': 'Asia Pacific',
    'South Korea': 'Asia Pacific',
    'Taiwan': 'Asia Pacific',
    'Philippines': 'Asia Pacific',
    'Vietnam': 'Asia Pacific',
    'Thailand': 'Asia Pacific',
    'Malaysia': 'Asia Pacific',
    'Indonesia': 'Asia Pacific',
    'New Zealand': 'Asia Pacific',
    'Pakistan': 'Asia Pacific',
    
    # Middle East & Africa
    'Israel': 'Middle East & Africa',
    'United Arab Emirates': 'Middle East & Africa',
    'South Africa': 'Middle East & Africa',
    'Nigeria': 'Middle East & Africa',
    'Egypt': 'Middle East & Africa',
    'Kenya': 'Middle East & Africa',
    'Saudi Arabia': 'Middle East & Africa',
}

# ============================================
# US STATES (abbreviations and full names)
# ============================================

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    'D.C.': 'District of Columbia'
}

US_STATE_NAMES = set(US_STATES.values())
US_STATE_ABBREVS = set(US_STATES.keys())

# ============================================
# CANADIAN PROVINCES
# ============================================

CANADIAN_PROVINCES = {
    'ON': 'Ontario', 'QC': 'Quebec', 'BC': 'British Columbia', 'AB': 'Alberta',
    'MB': 'Manitoba', 'SK': 'Saskatchewan', 'NS': 'Nova Scotia', 'NB': 'New Brunswick',
    'NL': 'Newfoundland and Labrador', 'PE': 'Prince Edward Island',
    'NT': 'Northwest Territories', 'YT': 'Yukon', 'NU': 'Nunavut'
}

CANADIAN_PROVINCE_NAMES = set(CANADIAN_PROVINCES.values())
CANADIAN_PROVINCE_ABBREVS = set(CANADIAN_PROVINCES.keys())

# ============================================
# CITY TO COUNTRY MAPPINGS
# ============================================

CITY_TO_COUNTRY = {
    # United States cities
    'new york': 'United States',
    'new york city': 'United States',
    'nyc': 'United States',
    'san francisco': 'United States',
    'sf': 'United States',
    'san francisco bay area': 'United States',
    'los angeles': 'United States',
    'la': 'United States',
    'chicago': 'United States',
    'houston': 'United States',
    'phoenix': 'United States',
    'philadelphia': 'United States',
    'san antonio': 'United States',
    'san diego': 'United States',
    'dallas': 'United States',
    'san jose': 'United States',
    'austin': 'United States',
    'jacksonville': 'United States',
    'fort worth': 'United States',
    'columbus': 'United States',
    'charlotte': 'United States',
    'indianapolis': 'United States',
    'seattle': 'United States',
    'denver': 'United States',
    'boston': 'United States',
    'nashville': 'United States',
    'detroit': 'United States',
    'portland': 'United States',
    'las vegas': 'United States',
    'atlanta': 'United States',
    'miami': 'United States',
    'oakland': 'United States',
    'minneapolis': 'United States',
    'tampa': 'United States',
    'raleigh': 'United States',
    'pittsburgh': 'United States',
    'cincinnati': 'United States',
    'st. louis': 'United States',
    'cleveland': 'United States',
    'salt lake city': 'United States',
    'palo alto': 'United States',
    'mountain view': 'United States',
    'menlo park': 'United States',
    'sunnyvale': 'United States',
    'cupertino': 'United States',
    'redwood city': 'United States',
    'santa clara': 'United States',
    'berkeley': 'United States',
    'bellevue': 'United States',
    'cottonwood heights': 'United States',
    'durham': 'United States',
    'milwaukee': 'United States',
    'kansas city': 'United States',
    'newark': 'United States',
    
    # Canada cities
    'toronto': 'Canada',
    'vancouver': 'Canada',
    'montreal': 'Canada',
    'calgary': 'Canada',
    'ottawa': 'Canada',
    'kitchener': 'Canada',
    'waterloo': 'Canada',
    'kitchener-waterloo': 'Canada',
    
    # UK cities
    'london': 'United Kingdom',
    'manchester': 'United Kingdom',
    'birmingham': 'United Kingdom',
    'edinburgh': 'United Kingdom',
    'glasgow': 'United Kingdom',
    'cardiff': 'United Kingdom',
    'bristol': 'United Kingdom',
    'leeds': 'United Kingdom',
    'cambridge': 'United Kingdom',
    'oxford': 'United Kingdom',
    
    # Ireland cities
    'dublin': 'Ireland',
    'cork': 'Ireland',
    'galway': 'Ireland',
    
    # Germany cities
    'berlin': 'Germany',
    'munich': 'Germany',
    'frankfurt': 'Germany',
    'hamburg': 'Germany',
    'cologne': 'Germany',
    'frankfurt am main': 'Germany',
    
    # France cities
    'paris': 'France',
    'lyon': 'France',
    'marseille': 'France',
    
    # Netherlands cities
    'amsterdam': 'Netherlands',
    'rotterdam': 'Netherlands',
    'the hague': 'Netherlands',
    'eindhoven': 'Netherlands',
    
    # Spain cities
    'madrid': 'Spain',
    'barcelona': 'Spain',
    
    # Italy cities
    'rome': 'Italy',
    'milan': 'Italy',
    
    # Poland cities
    'warsaw': 'Poland',
    'krakow': 'Poland',
    'wroclaw': 'Poland',
    
    # Sweden cities
    'stockholm': 'Sweden',
    'gothenburg': 'Sweden',
    
    # Switzerland cities
    'zurich': 'Switzerland',
    'geneva': 'Switzerland',
    
    # India cities
    'bengaluru': 'India',
    'bangalore': 'India',
    'mumbai': 'India',
    'delhi': 'India',
    'new delhi': 'India',
    'hyderabad': 'India',
    'pune': 'India',
    'chennai': 'India',
    'gurgaon': 'India',
    'noida': 'India',
    'mohali': 'India',
    
    # Australia cities
    'sydney': 'Australia',
    'melbourne': 'Australia',
    'brisbane': 'Australia',
    'perth': 'Australia',
    
    # Japan cities
    'tokyo': 'Japan',
    'osaka': 'Japan',
    
    # Singapore
    'singapore': 'Singapore',
    
    # China cities
    'beijing': 'China',
    'shanghai': 'China',
    'shenzhen': 'China',
    'hangzhou': 'China',
    'guangzhou': 'China',
    
    # Hong Kong
    'hong kong': 'Hong Kong',
    
    # South Korea cities
    'seoul': 'South Korea',
    
    # Taiwan cities
    'taipei': 'Taiwan',
    
    # Israel cities
    'tel aviv': 'Israel',
    'jerusalem': 'Israel',
    
    # UAE cities
    'dubai': 'United Arab Emirates',
    'abu dhabi': 'United Arab Emirates',
    
    # Brazil cities
    'sao paulo': 'Brazil',
    'são paulo': 'Brazil',
    'rio de janeiro': 'Brazil',
    'belo horizonte': 'Brazil',
    
    # Mexico cities
    'mexico city': 'Mexico',
    
    # Colombia cities
    'bogota': 'Colombia',
    'bogotá': 'Colombia',
    'medellin': 'Colombia',
    'medellín': 'Colombia',
    
    # Argentina cities
    'buenos aires': 'Argentina',
    
    # New Zealand cities
    'auckland': 'New Zealand',
    'wellington': 'New Zealand',
    
    # Vietnam cities
    'ho chi minh city': 'Vietnam',
    'hanoi': 'Vietnam',
    
    # Thailand cities
    'bangkok': 'Thailand',
    
    # Indonesia cities
    'jakarta': 'Indonesia',
    
    # Philippines cities
    'manila': 'Philippines',
    
    # Denmark cities
    'copenhagen': 'Denmark',
    
    # Finland cities
    'helsinki': 'Finland',
    
    # Norway cities
    'oslo': 'Norway',
    
    # Belgium cities
    'brussels': 'Belgium',
    'antwerp': 'Belgium',
    
    # Austria cities
    'vienna': 'Austria',
    
    # Czech Republic cities
    'prague': 'Czech Republic',
    
    # Romania cities
    'bucharest': 'Romania',
    
    # Serbia cities
    'belgrade': 'Serbia',
}

# ============================================
# DIRECT ALIASES (exact match, case-insensitive)
# ============================================

COUNTRY_ALIASES = {
    # United States variations
    'us': 'United States',
    'usa': 'United States',
    'u.s.': 'United States',
    'u.s.a.': 'United States',
    'united states': 'United States',
    'united states of america': 'United States',
    'us (hybrid)': 'United States',
    'u.s. (hybrid)': 'United States',
    'us-nyc': 'United States',
    'us-sf': 'United States',
    'us remote': 'United States',
    'u.s. remote': 'United States',
    'remote us': 'United States',
    'remote usa': 'United States',
    'remote - us': 'United States',
    'remote - usa': 'United States',
    'remote - united states': 'United States',
    'remote- us': 'United States',
    'remote -us': 'United States',
    'united states - remote': 'United States',
    'united states (remote)': 'United States',
    'united states(remote)': 'United States',
    'remote, us': 'United States',
    'remote,us': 'United States',
    'remote - us: select locations': 'United States',
    'remote - us: all locations': 'United States',
    
    # UK variations
    'uk': 'United Kingdom',
    'u.k.': 'United Kingdom',
    'united kingdom': 'United Kingdom',
    'great britain': 'United Kingdom',
    'britain': 'United Kingdom',
    'england': 'United Kingdom',
    'scotland': 'United Kingdom',
    'wales': 'United Kingdom',
    'northern ireland': 'United Kingdom',
    'gbr': 'United Kingdom',
    'uk (hybrid)': 'United Kingdom',
    'u.k. (hybrid)': 'United Kingdom',
    'remote uk': 'United Kingdom',
    'remote - uk': 'United Kingdom',
    'uk remote': 'United Kingdom',
    'united kingdom (remote)': 'United Kingdom',
    
    # Canada variations
    'canada': 'Canada',
    'can': 'Canada',
    'ca remote': 'Canada',  # Careful - could be California
    'remote canada': 'Canada',
    'remote - canada': 'Canada',
    'remote - canada: select locations': 'Canada',
    'canada - remote': 'Canada',
    'canada (remote)': 'Canada',
    
    # India variations
    'ind': 'India',
    'india': 'India',
    'india (hybrid)': 'India',
    'remote india': 'India',
    'remote - india': 'India',
    'india remote': 'India',
    'karnataka': 'India',
    'telangana': 'India',
    'maharashtra': 'India',
    'tamil nadu': 'India',
    
    # Germany variations
    'germany': 'Germany',
    'deutschland': 'Germany',
    'deu': 'Germany',
    'ger': 'Germany',
    'remote germany': 'Germany',
    'remote - germany': 'Germany',
    'hesse': 'Germany',
    
    # France variations
    'france': 'France',
    'fra': 'France',
    'remote france': 'France',
    'remote - france': 'France',
    
    # Netherlands variations
    'netherlands': 'Netherlands',
    'the netherlands': 'Netherlands',
    'holland': 'Netherlands',
    'nld': 'Netherlands',
    'remote netherlands': 'Netherlands',
    
    # Ireland variations
    'ireland': 'Ireland',
    'irl': 'Ireland',
    'republic of ireland': 'Ireland',
    'remote ireland': 'Ireland',
    'remote - ireland': 'Ireland',
    
    # Spain variations
    'spain': 'Spain',
    'esp': 'Spain',
    'españa': 'Spain',
    'remote spain': 'Spain',
    'remote - spain': 'Spain',
    
    # Poland variations
    'poland': 'Poland',
    'pol': 'Poland',
    'polska': 'Poland',
    'remote poland': 'Poland',
    'remote - poland': 'Poland',
    
    # Japan variations
    'japan': 'Japan',
    'jpn': 'Japan',
    
    # Australia variations
    'australia': 'Australia',
    'aus': 'Australia',
    'nsw': 'Australia',
    'new south wales': 'Australia',
    'victoria': 'Australia',
    'queensland': 'Australia',
    
    # Singapore variations
    'singapore': 'Singapore',
    'sgp': 'Singapore',
    
    # Israel variations
    'israel': 'Israel',
    'isr': 'Israel',
    'tel aviv district': 'Israel',
    
    # South Korea variations
    'south korea': 'South Korea',
    'korea': 'South Korea',
    'republic of korea': 'South Korea',
    'kor': 'South Korea',
    
    # Taiwan variations
    'taiwan': 'Taiwan',
    'twn': 'Taiwan',
    
    # Brazil variations
    'brazil': 'Brazil',
    'brasil': 'Brazil',
    'bra': 'Brazil',
    'sao paulo': 'Brazil',
    'são paulo': 'Brazil',
    
    # Mexico variations
    'mexico': 'Mexico',
    'méxico': 'Mexico',
    'mex': 'Mexico',
    'jalisco': 'Mexico',
    
    # UAE variations
    'uae': 'United Arab Emirates',
    'u.a.e.': 'United Arab Emirates',
    'united arab emirates': 'United Arab Emirates',
    
    # China variations
    'china': 'China',
    'chn': 'China',
    'prc': 'China',
    'guangdong': 'China',
    
    # Hong Kong variations
    'hong kong': 'Hong Kong',
    'hkg': 'Hong Kong',
    'central': 'Hong Kong',  # HK district
    
    # Costa Rica variations
    'costa rica': 'Costa Rica',
    'cri': 'Costa Rica',
    
    # Colombia variations
    'colombia': 'Colombia',
    'col': 'Colombia',
    
    # Argentina variations
    'argentina': 'Argentina',
    'arg': 'Argentina',
    
    # Other European countries
    'sweden': 'Sweden',
    'swe': 'Sweden',
    'switzerland': 'Switzerland',
    'che': 'Switzerland',
    'belgium': 'Belgium',
    'bel': 'Belgium',
    'austria': 'Austria',
    'aut': 'Austria',
    'denmark': 'Denmark',
    'dnk': 'Denmark',
    'hovedstaden': 'Denmark',
    'norway': 'Norway',
    'nor': 'Norway',
    'finland': 'Finland',
    'fin': 'Finland',
    'uusimaa': 'Finland',
    'north ostrobothnia': 'Finland',
    'portugal': 'Portugal',
    'prt': 'Portugal',
    'italy': 'Italy',
    'ita': 'Italy',
    'czech republic': 'Czech Republic',
    'czechia': 'Czech Republic',
    'cze': 'Czech Republic',
    'romania': 'Romania',
    'rou': 'Romania',
    'serbia': 'Serbia',
    'srb': 'Serbia',
    'south bačka': 'Serbia',
    'greece': 'Greece',
    'grc': 'Greece',
    'hungary': 'Hungary',
    'hun': 'Hungary',
    'ukraine': 'Ukraine',
    'ukr': 'Ukraine',
    
    # Asia Pacific
    'vietnam': 'Vietnam',
    'vnm': 'Vietnam',
    'thailand': 'Thailand',
    'tha': 'Thailand',
    'malaysia': 'Malaysia',
    'mys': 'Malaysia',
    'indonesia': 'Indonesia',
    'idn': 'Indonesia',
    'philippines': 'Philippines',
    'phl': 'Philippines',
    'new zealand': 'New Zealand',
    'nzl': 'New Zealand',
    'pakistan': 'Pakistan',
    'pak': 'Pakistan',
}


# ============================================
# MAIN NORMALIZATION FUNCTION
# ============================================

def normalize_location_to_country(
    location_country: Optional[str] = None,
    location_state: Optional[str] = None,
    location_raw: Optional[str] = None
) -> Optional[str]:
    """
    Given job location fields, return the canonical country name.
    Returns None if location cannot be determined.
    
    Priority:
    1. Direct alias match on location_country
    2. US/Canadian state detection in location_state
    3. Parse location_raw for embedded data
    4. Parse location_country as complex string
    """
    
    # Try location_raw FIRST since that often has the most complete info
    # when location_country is NULL
    if location_raw:
        country = _parse_location_string(location_raw)
        if country:
            return country
    
    # Try location_country
    if location_country:
        country = _normalize_single_value(location_country)
        if country:
            return country
        # Try parsing as complex string
        country = _parse_location_string(location_country)
        if country:
            return country
    
    # Try location_state
    if location_state:
        state_upper = location_state.upper().strip()
        state_title = location_state.strip().title()
        
        if state_upper in US_STATE_ABBREVS or state_title in US_STATE_NAMES:
            return 'United States'
        if state_upper in CANADIAN_PROVINCE_ABBREVS or state_title in CANADIAN_PROVINCE_NAMES:
            return 'Canada'
    
    return None


def _normalize_single_value(value: str) -> Optional[str]:
    """Try to normalize a single location value to a country."""
    if not value:
        return None
    
    cleaned = value.strip()
    cleaned_lower = cleaned.lower()
    
    # Skip generic/unparseable values
    unparseable = {'hybrid', 'remote', 'in-office', 'distributed', 'on-site', 'onsite', 'anywhere', 'worldwide', 'global'}
    if cleaned_lower in unparseable:
        return None
    
    # Remove common suffixes
    for suffix in [' (hybrid)', ' (remote)', ' - hybrid', ' - remote', ' hybrid', ' remote']:
        if cleaned_lower.endswith(suffix):
            cleaned_lower = cleaned_lower[:-len(suffix)].strip()
            cleaned = cleaned[:-len(suffix)].strip()
    
    # Direct alias match
    if cleaned_lower in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[cleaned_lower]
    
    # Check if it's a US state (full name or abbreviation)
    if cleaned.upper() in US_STATE_ABBREVS:
        return 'United States'
    if cleaned.title() in US_STATE_NAMES:
        return 'United States'
    
    # Check if it's a Canadian province
    if cleaned.upper() in CANADIAN_PROVINCE_ABBREVS:
        return 'Canada'
    if cleaned.title() in CANADIAN_PROVINCE_NAMES:
        return 'Canada'
    
    # Check if it's already a canonical country
    if cleaned in COUNTRY_TO_REGION:
        return cleaned
    if cleaned.title() in COUNTRY_TO_REGION:
        return cleaned.title()
    
    # Check city mapping
    if cleaned_lower in CITY_TO_COUNTRY:
        return CITY_TO_COUNTRY[cleaned_lower]
    
    return None


def _parse_location_string(location_str: str) -> Optional[str]:
    """
    Parse complex location strings like:
    - "Remote - USA"
    - "San Francisco, CA | New York City, NY"
    - "Remote - Canada: Select locations"
    - "United States (Remote)"
    """
    if not location_str:
        return None
    
    location_lower = location_str.lower().strip()
    
    # Skip generic/unparseable values
    unparseable = {'hybrid', 'remote', 'in-office', 'distributed', 'on-site', 'onsite'}
    if location_lower in unparseable:
        return None
    
    # Handle "Remote - [Country]" pattern first
    remote_patterns = [
        r'remote\s*-\s*(.+)',           # "Remote - USA"
        r'remote\s+(.+)',                # "Remote USA"
        r'(.+)\s*-\s*remote',            # "USA - Remote"
        r'(.+)\s*$remote$',            # "USA (Remote)"
        r'(.+)\s+remote$',               # "USA Remote"
    ]
    
    for pattern in remote_patterns:
        match = re.match(pattern, location_lower, re.IGNORECASE)
        if match:
            potential_country = match.group(1).strip()
            # Remove trailing junk like ": select locations"
            potential_country = re.sub(r':\s*.+$', '', potential_country).strip()
            # Try to normalize this
            result = _normalize_single_value(potential_country)
            if result:
                return result
    
    # Direct check in aliases (handles things like "United States")
    if location_lower in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[location_lower]
    
    # Check city mapping directly
    if location_lower in CITY_TO_COUNTRY:
        return CITY_TO_COUNTRY[location_lower]
    
    # Split by common delimiters and check each part
    parts = re.split(r'[,|•\-–—/;]', location_str)
    parts = [p.strip() for p in parts if p.strip()]
    
    for part in parts:
        result = _normalize_single_value(part)
        if result:
            return result
        
        # Check city mapping for this part
        part_lower = part.lower().strip()
        if part_lower in CITY_TO_COUNTRY:
            return CITY_TO_COUNTRY[part_lower]
    
    # Check if any known city name appears in the string
    for city, country in CITY_TO_COUNTRY.items():
        if city in location_lower:
            return country
    
    # Check if any country alias appears in the string (as whole word)
    for alias, country in COUNTRY_ALIASES.items():
        # Use word boundary to avoid false matches
        if re.search(rf'\b{re.escape(alias)}\b', location_lower):
            return country
    
    return None


def get_all_canonical_countries() -> List[str]:
    """Return list of all canonical country names."""
    return sorted(COUNTRY_TO_REGION.keys())


def get_region_for_country(country: str) -> Optional[str]:
    """Get the region for a canonical country name."""
    return COUNTRY_TO_REGION.get(country)


def get_country_match_patterns(country: str) -> List[str]:
    """
    Get all patterns that should match a given country.
    Used for building SQL filters.
    """
    patterns = [country]
    
    # Add all aliases that map to this country
    for alias, target in COUNTRY_ALIASES.items():
        if target == country:
            patterns.append(alias)
    
    # Add cities that map to this country
    for city, target in CITY_TO_COUNTRY.items():
        if target == country:
            patterns.append(city)
    
    return patterns