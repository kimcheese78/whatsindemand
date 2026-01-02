# backend/scripts/batch_scrape.py

"""
Batch scrape using scrape_single.py and companies registry.
Usage: python scripts/batch_scrape.py
"""

import subprocess
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.scrapers.greenhouse.companies import GREENHOUSE_COMPANIES

if __name__ == "__main__":
    print(f"\n🚀 Batch scraping {len(GREENHOUSE_COMPANIES)} companies\n")
    
    for i, company in enumerate(GREENHOUSE_COMPANIES, 1):
        slug = company["slug"]
        name = company["name"]
        
        print(f"\n[{i}/{len(GREENHOUSE_COMPANIES)}] {name}")
        print("=" * 50)
        
        subprocess.run(["python", "scripts/scrape_single.py", slug, name])
        
        time.sleep(2)  # Rate limit
    
    print(f"\n✅ Batch complete!")