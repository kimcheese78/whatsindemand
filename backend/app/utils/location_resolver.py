# backend/app/utils/location_resolver.py

import geonamescache
import re
from functools import lru_cache

gc = geonamescache.GeonamesCache()

# Pre-load data
_countries_by_names = gc.get_countries_by_names()
_cities = gc.get_cities()
_us_states = gc.get_us_states()

# US state abbreviations
US_STATE_ABBREVS = {
    'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
    'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md',
    'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj',
    'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc',
    'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc'
}

# Canadian province abbreviations
CA_PROVINCE_ABBREVS = {'ab', 'bc', 'mb', 'nb', 'nl', 'ns', 'nt', 'nu', 'on', 'pe', 'qc', 'sk', 'yt'}

# Indian states (not in geonames)
INDIAN_STATES = {
    'karnataka', 'telangana', 'maharashtra', 'tamil nadu', 'andhra pradesh',
    'kerala', 'west bengal', 'rajasthan', 'uttar pradesh', 'gujarat',
    'madhya pradesh', 'haryana', 'punjab', 'bihar', 'odisha', 'jharkhand',
    'chhattisgarh', 'assam', 'goa', 'uttarakhand', 'himachal pradesh',
    'delhi', 'chandigarh', 'puducherry', 'pondicherry'
}

# Build city lookup - prioritize by population
_city_to_country = {}
for city_data in sorted(_cities.values(), key=lambda x: x.get('population', 0), reverse=True):
    name = city_data['name'].lower()
    if name not in _city_to_country:
        _city_to_country[name] = city_data['countrycode']

# Currency mapping
COUNTRY_CODE_TO_CURRENCY = {
    'US': 'USD', 'CA': 'CAD', 'GB': 'GBP', 'AU': 'AUD', 'NZ': 'NZD',
    'DE': 'EUR', 'FR': 'EUR', 'NL': 'EUR', 'ES': 'EUR', 'IT': 'EUR',
    'IE': 'EUR', 'BE': 'EUR', 'AT': 'EUR', 'PT': 'EUR', 'FI': 'EUR',
    'GR': 'EUR', 'CH': 'CHF', 'SE': 'SEK', 'NO': 'NOK', 'DK': 'DKK',
    'PL': 'PLN', 'CZ': 'CZK', 'JP': 'JPY', 'CN': 'CNY', 'IN': 'INR',
    'SG': 'SGD', 'HK': 'HKD', 'KR': 'KRW', 'TW': 'TWD', 'PH': 'PHP',
    'MY': 'MYR', 'TH': 'THB', 'ID': 'IDR', 'VN': 'VND', 'PK': 'PKR',
    'IL': 'ILS', 'AE': 'AED', 'SA': 'SAR', 'MX': 'MXN', 'BR': 'BRL',
    'AR': 'ARS', 'CL': 'CLP', 'CO': 'COP', 'ZA': 'ZAR', 'NG': 'NGN',
}


def resolve_location_to_country_code(location_raw: str) -> str | None:
    """Resolve location string to ISO country code."""
    if not location_raw:
        return None
    
    loc = location_raw.lower().strip()
    
    # Split on common delimiters
    segments = [s.strip() for s in re.split(r'[,;|/]', loc) if s.strip()]
    
    # Also get all individual words for abbreviation matching
    all_words = set(loc.replace(',', ' ').replace(';', ' ').replace('|', ' ').split())
    
    # 1. US STATE ABBREVIATIONS (highest priority)
    for word in all_words:
        if word in US_STATE_ABBREVS:
            return 'US'
    
    # 2. US state full names
    for state_data in _us_states.values():
        if state_data['name'].lower() in loc:
            return 'US'
    
    # 3. CANADIAN PROVINCE ABBREVIATIONS
    for word in all_words:
        if word in CA_PROVINCE_ABBREVS:
            return 'CA'
    
    # 4. INDIAN STATES
    for state in INDIAN_STATES:
        if state in loc:
            return 'IN'
    
    # 5. EXPLICIT COUNTRY NAMES
    for country_name, country_data in _countries_by_names.items():
        if country_name.lower() in loc:
            return country_data['iso']
    
    # 6. CITY NAMES (exact segment match)
    for segment in segments:
        if segment in _city_to_country:
            return _city_to_country[segment]
    
    return None


def get_currency_for_location(location_raw: str) -> str | None:
    """Get currency code for a location string."""
    country_code = resolve_location_to_country_code(location_raw)
    if country_code:
        return COUNTRY_CODE_TO_CURRENCY.get(country_code)
    return None


# Quick test when run directly
if __name__ == '__main__':
    tests = [
        "Karnataka",
        "Bengaluru, Karnataka",
        "San Francisco, CA",
        "Denver, CO",
        "Remote - Brazil",
        "Toronto, ON",
        "London",
        "London, ON",
        "Dublin, IE",
        "EMEA",
    ]
    
    for loc in tests:
        code = resolve_location_to_country_code(loc)
        curr = get_currency_for_location(loc)
        print(f"{loc:30} -> {code} -> {curr}")