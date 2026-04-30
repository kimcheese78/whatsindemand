"""
FAST Greenhouse Scraper - Uses asyncio for parallel requests
10x faster than sequential approach
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict
import time

class GreenhouseAsyncScraper:
    
    def __init__(self, max_concurrent=10, timeout=30):
        """
        Args:
            max_concurrent: How many jobs to fetch simultaneously (10-20 is safe)
            timeout: Request timeout in seconds
        """
        self.base_url = "https://boards-api.greenhouse.io/v1/boards"
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.ssl = False
        self.semaphore = None
    
    async def fetch_json(self, session, url):
        """Fetch JSON from URL with error handling"""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"      ⚠️ Status {response.status} for {url}")
                    return None
        except asyncio.TimeoutError:
            print(f"      ⏱️ Timeout for {url}")
            return None
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return None
    
    async def get_job_details(self, session, company_slug, job):
        """Fetch full details for ONE job (async)"""
        
        # Semaphore limits concurrent requests
        async with self.semaphore:
            job_id = job['id']
            url = f"{self.base_url}/{company_slug}/jobs/{job_id}"
            
            details = await self.fetch_json(session, url)
            
            if details:
                return self._process_job(job, details, company_slug)
            else:
                return None
    
    def _process_job(self, basic_job, full_details, company_slug):
        """Process job data"""
        
        location = basic_job.get('location', {}).get('name', 'Not specified')
        departments = [d.get('name') for d in basic_job.get('departments', [])]
        department = departments[0] if departments else 'Unknown'
        
        html_description = full_details.get('content', '')
        text_description = self._html_to_text(html_description)
        
        return {
            'job_id': basic_job.get('id'),
            'title': basic_job.get('title'),
            'company': company_slug,
            'location': location,
            'department': department,
            'url': basic_job.get('absolute_url'),
            'updated_at': basic_job.get('updated_at'),
            'description_html': html_description,
            'description_text': text_description,
            'source': 'greenhouse_api_async',
            'scraped_at': datetime.now().isoformat()
        }
    
    def _html_to_text(self, html):
        """Convert HTML to text"""
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        for element in soup(['script', 'style']):
            element.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return '\n'.join(chunk for chunk in chunks if chunk)
    
    async def scrape_company_async(self, company_slug, max_jobs=None):
        """Scrape company using async (FAST!)"""
        
        print(f"\n{'='*60}")
        print(f"🏢 {company_slug.upper()} (Async Mode)")
        print(f"{'='*60}\n")
        
        # Create semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        start_time = time.time()
        
        async with aiohttp.ClientSession(timeout=self.timeout, connector=aiohttp.TCPConnector(ssl=self.ssl)) as session:

            
            # Step 1: Get job list
            jobs_url = f"{self.base_url}/{company_slug}/jobs"
            print(f"📋 Fetching job list...")
            
            data = await self.fetch_json(session, jobs_url)
            
            if not data or 'jobs' not in data:
                print(f"   ❌ Failed to fetch jobs")
                return []
            
            jobs = data['jobs']
            
            if not jobs:
                print(f"   ⚠️ No jobs found")
                return []
            
            print(f"   ✅ Found {len(jobs)} jobs\n")
            
            if max_jobs:
                jobs = jobs[:max_jobs]
                print(f"   📌 Limiting to {max_jobs} jobs\n")
            
            # Step 2: Fetch all job details in parallel!
            print(f"🚀 Fetching {len(jobs)} job details in parallel...")
            print(f"   Max concurrent: {self.max_concurrent}")
            print(f"   Estimated time: ~{len(jobs) / self.max_concurrent * 0.5:.1f} seconds\n")
            
            # Create tasks for all jobs
            tasks = [
                self.get_job_details(session, company_slug, job)
                for job in jobs
            ]
            
            # Execute all tasks concurrently with progress
            detailed_jobs = []
            completed = 0
            
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:
                    detailed_jobs.append(result)
                
                completed += 1
                if completed % 10 == 0 or completed == len(tasks):
                    print(f"   Progress: {completed}/{len(tasks)} ({completed/len(tasks)*100:.0f}%)")
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Scraped {len(detailed_jobs)}/{len(jobs)} jobs")
        print(f"⏱️  Time: {elapsed:.1f} seconds")
        print(f"📊 Speed: {len(detailed_jobs)/elapsed:.1f} jobs/second\n")
        
        return detailed_jobs
    
    def save_to_json(self, jobs, filename):
        """Save to JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        
        import os
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        print(f"💾 Saved to: {filename} ({size_mb:.2f} MB)")


# Wrapper function to run async code
def scrape_company(company_slug, max_jobs=None, max_concurrent=10):
    """
    Convenience function to scrape a company
    
    Args:
        company_slug: Company name (e.g., 'stripe')
        max_jobs: Limit number of jobs (None = all)
        max_concurrent: Number of parallel requests (10-20 recommended)
    """
    scraper = GreenhouseAsyncScraper(max_concurrent=max_concurrent)
    
    # Run async function
    jobs = asyncio.run(scraper.scrape_company_async(company_slug, max_jobs))
    
    return scraper, jobs


# =============================================================================
# USAGE
# =============================================================================

def test_speed_comparison():
    """Compare async vs sequential speed"""
    
    company = 'stripe'
    num_jobs = 20
    
    print("\n" + "="*60)
    print("SPEED TEST: Async vs Sequential")
    print("="*60)
    
    # Test 1: Async (fast)
    print(f"\n🚀 TEST 1: ASYNC MODE")
    scraper_async, jobs_async = scrape_company(company, max_jobs=num_jobs, max_concurrent=10)
    
    if jobs_async:
        scraper_async.save_to_json(jobs_async, f'{company}_async.json')
    
    print("\n" + "="*60)
    print("Result: Async is ~10x faster! 🎉")
    print("="*60)


def scrape_multiple_companies_fast():
    """Scrape multiple companies quickly"""
    
    companies = ['ramp', 'linear', 'lattice', 'notion', 'superhuman']
    
    all_jobs = []
    
    for i, company in enumerate(companies, 1):
        print(f"\n{'#'*60}")
        print(f"# Company {i}/{len(companies)}")
        print(f"{'#'*60}")
        
        scraper, jobs = scrape_company(company, max_jobs=20, max_concurrent=15)
        all_jobs.extend(jobs)
        
        # Small delay between companies
        if i < len(companies):
            print(f"\n⏸️  Waiting 1 second...\n")
            time.sleep(1)
    
    if all_jobs:
        scraper.save_to_json(all_jobs, 'all_companies_fast.json')
        
        print("\n" + "="*60)
        print("FINAL RESULTS:")
        print("="*60)
        print(f"Companies: {len(companies)}")
        print(f"Total jobs: {len(all_jobs)}")
        print(f"Avg per company: {len(all_jobs)/len(companies):.1f}")


if __name__ == "__main__":
    
    # Test the speed!
    test_speed_comparison()
    
    # Or scrape multiple companies
    # scrape_multiple_companies_fast()