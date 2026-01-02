#!/usr/bin/env python3
"""
Convert all salaries to USD equivalent using live exchange rates.

Usage:
    python scripts/convert_salaries_to_usd.py --dry-run
    python scripts/convert_salaries_to_usd.py
    python scripts/convert_salaries_to_usd.py --show-rates
    python scripts/convert_salaries_to_usd.py --reprocess  # Re-convert ALL jobs
"""

import sys
import os
import requests
from datetime import datetime

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)

from app import create_app
from app.models import db, Job

app = create_app()


# Fallback rates (updated January 2025) - 1 foreign unit = X USD
FALLBACK_RATES = {
    'USD': 1.0,
    # Major currencies
    'EUR': 1.04,
    'GBP': 1.25,
    'CAD': 0.70,
    'AUD': 0.62,
    'NZD': 0.56,
    'CHF': 1.11,
    # Asian currencies
    'JPY': 0.0064,
    'CNY': 0.137,
    'HKD': 0.128,
    'SGD': 0.74,
    'KRW': 0.00069,
    'TWD': 0.030,
    'INR': 0.0118,
    'PKR': 0.0036,
    'BDT': 0.0083,
    'PHP': 0.017,
    'MYR': 0.22,
    'THB': 0.029,
    'IDR': 0.000061,
    'VND': 0.000039,
    # European currencies (non-EUR)
    'SEK': 0.092,
    'NOK': 0.088,
    'DKK': 0.14,
    'PLN': 0.24,
    'CZK': 0.042,
    'HUF': 0.0026,
    'RON': 0.22,
    'RUB': 0.010,
    'TRY': 0.028,
    # Middle East
    'ILS': 0.27,
    'AED': 0.27,
    'SAR': 0.27,
    'QAR': 0.27,
    # Americas
    'BRL': 0.17,
    'MXN': 0.049,
    'ARS': 0.00097,
    'CLP': 0.00098,
    'COP': 0.00024,
    # Africa
    'ZAR': 0.053,
    'NGN': 0.00061,
    'EGP': 0.020,
    'KES': 0.0077,
}


def fetch_rates_from_api():
    """Fetch exchange rates from exchangerate-api.com (free, no key needed)."""
    print("Fetching live exchange rates...")
    
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # API returns: 1 USD = X foreign. We need inverse: 1 foreign = X USD
        rates = {'USD': 1.0}
        for currency, rate in data.get('rates', {}).items():
            if rate > 0:
                rates[currency] = round(1.0 / rate, 8)
        
        print(f"✓ Fetched {len(rates)} rates (as of {data.get('date', 'unknown')})")
        return rates
        
    except Exception as e:
        print(f"✗ Failed to fetch live rates: {e}")
        print("  Using fallback rates")
        return FALLBACK_RATES


def convert_to_usd(amount, currency, rates):
    """Convert an amount to USD."""
    if not amount or amount <= 0:
        return None
    
    currency = currency or 'USD'
    rate = rates.get(currency) or FALLBACK_RATES.get(currency)
    
    if rate is None:
        return None
    
    converted = int(amount * rate)
    
    # Sanity check: $10K - $3M USD range
    if converted < 10000 or converted > 3000000:
        return None
    
    return converted


def show_rates():
    """Display current exchange rates."""
    rates = fetch_rates_from_api()
    
    print(f"\n{'=' * 70}")
    print(f"EXCHANGE RATES (1 foreign unit = X USD)")
    print(f"{'=' * 70}")
    
    # Group by region
    groups = {
        'Major': ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NZD', 'CHF'],
        'Asia': ['JPY', 'CNY', 'HKD', 'SGD', 'INR', 'KRW', 'TWD', 'PHP', 'MYR', 'THB', 'IDR', 'VND'],
        'Europe (other)': ['SEK', 'NOK', 'DKK', 'PLN', 'CZK'],
        'Middle East': ['ILS', 'AED', 'SAR'],
        'Americas': ['BRL', 'MXN'],
        'Africa': ['ZAR', 'NGN', 'EGP'],
    }
    
    for group_name, currencies in groups.items():
        print(f"\n{group_name}:")
        for curr in currencies:
            if curr in rates:
                rate = rates[curr]
                # Show example conversion
                if curr == 'INR':
                    example = f"10L INR = ${int(1000000 * rate):,}"
                elif rate < 0.001:
                    example = f"1M {curr} = ${int(1000000 * rate):,}"
                else:
                    example = f"100K {curr} = ${int(100000 * rate):,}"
                print(f"  {curr:5} = ${rate:<12.8f}  ({example})")


def convert_all_salaries(dry_run=False, reprocess=False, batch_size=500):
    """Convert all salaries to USD equivalent."""
    
    rates = fetch_rates_from_api()
    
    # Merge with fallback for complete coverage
    for curr, rate in FALLBACK_RATES.items():
        if curr not in rates:
            rates[curr] = rate
    
    with app.app_context():
        if reprocess:
            jobs = Job.query.filter(
                Job.salary_min.isnot(None),
                Job.is_active == True
            ).all()
            print(f"\n*** REPROCESS MODE: Re-converting ALL jobs ***\n")
        else:
            jobs = Job.query.filter(
                Job.salary_min.isnot(None),
                Job.salary_min_usd.is_(None),
                Job.is_active == True
            ).all()
        
        total_jobs = len(jobs)
        
        print(f"{'=' * 70}")
        print(f"Salary USD Conversion")
        print(f"{'=' * 70}")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        print(f"Jobs to process: {total_jobs:,}")
        print(f"{'=' * 70}\n")
        
        if total_jobs == 0:
            print("No jobs to process.")
            return
        
        converted = 0
        skipped = 0
        by_currency = {}
        missing_rates = {}
        examples = []
        
        for i, job in enumerate(jobs):
            currency = job.salary_currency or 'USD'
            by_currency[currency] = by_currency.get(currency, 0) + 1
            
            if currency not in rates:
                missing_rates[currency] = missing_rates.get(currency, 0) + 1
                skipped += 1
                continue
            
            usd_min = convert_to_usd(job.salary_min, currency, rates)
            usd_max = convert_to_usd(job.salary_max, currency, rates)
            
            if usd_min is None:
                skipped += 1
                continue
            
            if not dry_run:
                job.salary_min_usd = usd_min
                job.salary_max_usd = usd_max
            
            converted += 1
            
            # Collect examples
            if currency != 'USD' and len([e for e in examples if e['curr'] == currency]) < 2:
                examples.append({
                    'title': job.title[:40],
                    'curr': currency,
                    'orig': job.salary_min,
                    'usd': usd_min,
                    'rate': rates[currency]
                })
            
            if not dry_run and converted % batch_size == 0:
                db.session.commit()
                print(f"Progress: {converted:,} converted...")
        
        if not dry_run:
            db.session.commit()
        
        # Results
        print(f"\n{'=' * 70}")
        print(f"RESULTS")
        print(f"{'=' * 70}")
        print(f"Processed: {total_jobs:,}")
        print(f"Converted: {converted:,}")
        print(f"Skipped: {skipped:,}")
        
        if missing_rates:
            print(f"\nMissing rates:")
            for curr, count in sorted(missing_rates.items(), key=lambda x: -x[1]):
                print(f"  {curr}: {count} jobs")
        
        print(f"\n{'=' * 70}")
        print(f"BY CURRENCY")
        print(f"{'=' * 70}")
        for curr, count in sorted(by_currency.items(), key=lambda x: -x[1]):
            rate = rates.get(curr, 0)
            print(f"  {curr:5} | {count:>6,} jobs | rate: {rate:.8f}")
        
        if examples:
            print(f"\n{'=' * 70}")
            print(f"CONVERSION EXAMPLES")
            print(f"{'=' * 70}")
            for ex in examples:
                if ex['curr'] == 'INR' and ex['orig'] >= 100000:
                    orig_str = f"{ex['orig']/100000:.1f}L INR"
                else:
                    orig_str = f"{ex['curr']} {ex['orig']:,}"
                print(f"  {ex['title']}")
                print(f"    {orig_str} → ${ex['usd']:,} (rate: {ex['rate']:.8f})\n")
        
        if not dry_run:
            total_active = Job.query.filter(Job.is_active == True).count()
            with_usd = Job.query.filter(Job.is_active == True, Job.salary_min_usd.isnot(None)).count()
            
            print(f"{'=' * 70}")
            print(f"DATABASE STATUS")
            print(f"{'=' * 70}")
            print(f"Total active: {total_active:,}")
            print(f"With USD salary: {with_usd:,} ({round(with_usd/total_active*100, 1)}%)")
            print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Convert salaries to USD')
    parser.add_argument('--dry-run', action='store_true', help='Preview without updating')
    parser.add_argument('--show-rates', action='store_true', help='Show current rates')
    parser.add_argument('--reprocess', action='store_true', help='Re-convert ALL jobs')
    args = parser.parse_args()
    
    if args.show_rates:
        show_rates()
    else:
        convert_all_salaries(dry_run=args.dry_run, reprocess=args.reprocess)