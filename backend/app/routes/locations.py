# backend/app/routes/locations.py

from flask import Blueprint, jsonify
from app.models import db, Job
from sqlalchemy import func
from collections import defaultdict

# Import the shared normalizer
from app.utils.location_normalizer import (
    normalize_location_to_country,
    COUNTRY_TO_REGION,
    US_STATE_ABBREVS,
    US_STATE_NAMES,
    CANADIAN_PROVINCE_ABBREVS,
    CANADIAN_PROVINCE_NAMES,
)

locations_bp = Blueprint('locations', __name__, url_prefix='/api/locations')

# Preferred region order
REGION_ORDER = [
    'North America',
    'Europe',
    'Asia Pacific',
    'Latin America',
    'Middle East & Africa',
]


@locations_bp.route('', methods=['GET'])
def get_locations():
    """
    Get all locations grouped by region, with accurate job counts.
    Normalizes messy location data to canonical country names.
    """
    
    # Stream active jobs in chunks — avoids loading 200K+ rows into RAM at once
    query = db.session.query(
        Job.location_country,
        Job.location_state,
        Job.location_raw
    ).filter(
        Job.is_active == True
    ).yield_per(2000)

    # Count jobs per normalized country
    country_job_counts = defaultdict(int)
    unmatched_count = 0

    for loc_country, loc_state, loc_raw in query:
        # Normalize to canonical country
        country = normalize_location_to_country(loc_country, loc_state, loc_raw)
        
        if country and country in COUNTRY_TO_REGION:
            country_job_counts[country] += 1
        else:
            unmatched_count += 1
    
    # Log unmatched for debugging
    if unmatched_count > 0:
        print(f"[Locations] {unmatched_count} jobs could not be matched to a country")
    
    # Group countries by region
    regions = defaultdict(list)
    
    for country, job_count in country_job_counts.items():
        region = COUNTRY_TO_REGION.get(country)
        if region:
            regions[region].append({
                'name': country,
                'value': country,
                'job_count': job_count
            })
    
    # Sort countries within each region by job count (descending)
    for region in regions:
        regions[region].sort(key=lambda x: x['job_count'], reverse=True)
    
    # Build ordered response
    grouped_locations = []
    
    for region_name in REGION_ORDER:
        if region_name in regions and regions[region_name]:
            grouped_locations.append({
                'region': region_name,
                'countries': regions[region_name]
            })
    
    # Calculate totals
    total_matched = sum(country_job_counts.values())
    total_jobs = total_matched + unmatched_count
    
    return jsonify({
        'success': True,
        'locations': grouped_locations,
        'total_jobs': total_jobs,
        'matched_jobs': total_matched,
        'unmatched_jobs': unmatched_count  # Jobs only visible with "All Locations"
    })