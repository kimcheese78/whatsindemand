# app/scrapers/greenhouse/scraper.py

from app.scrapers.base_scraper import BaseScraper
from app.scrapers.greenhouse.parser import GreenhouseParser
from app.utils.role_normalizer_v2 import normalize_title
from typing import List, Dict, Optional
import requests

class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse ATS"""
    
    def __init__(self, verbose: bool = False):
        super().__init__()
        self.parser = GreenhouseParser()
        self.api_base_template = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
        self.verbose = verbose  # Control logging verbosity
    
    def get_company_jobs(self, company_slug: str) -> List[Dict]:
        """Fetch all jobs for a company using Greenhouse API"""
        self.rate_limit()
        
        api_url = self.api_base_template.format(company=company_slug)
        
        try:
            response = self.session.get(api_url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            raw_jobs = data.get('jobs', [])
            
            print(f"📋 Found {len(raw_jobs)} jobs for {company_slug}")
            
            if not raw_jobs:
                return []
            
            normalized_jobs = []
            failed_count = 0
            
            for i, raw_job in enumerate(raw_jobs):
                try:
                    # Get full job details from detail endpoint
                    job_with_description = self._get_job_details(company_slug, raw_job)
                    
                    normalized = self.normalize_job(job_with_description)
                    normalized['company_slug'] = company_slug
                    normalized_jobs.append(normalized)
                    
                except Exception as e:
                    failed_count += 1
                    if self.verbose:
                        print(f"  ⚠ Error processing job {raw_job.get('id')}: {e}")
                    continue
                
                # Progress indicator every 50 jobs
                if (i + 1) % 50 == 0:
                    print(f"  Processed {i + 1}/{len(raw_jobs)}...")
            
            # Final summary
            status = "✅" if failed_count == 0 else "⚠️"
            print(f"{status} Fetched {len(normalized_jobs)} jobs from {company_slug}" + 
                  (f" ({failed_count} failed)" if failed_count > 0 else ""))
            
            return normalized_jobs
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"❌ Company not found: {company_slug} (invalid slug?)")
            else:
                print(f"❌ HTTP error for {company_slug}: {e}")
            return []
        except requests.RequestException as e:
            print(f"❌ Failed to fetch jobs for {company_slug}: {e}")
            return []
    
    def _get_job_details(self, company_slug: str, raw_job: Dict) -> Dict:
        """Fetch full job details from Greenhouse detail API endpoint"""
        job_id = raw_job.get('id')
        
        if not job_id:
            return raw_job
        
        # Skip detail fetch if we already have substantial content
        existing_content = raw_job.get('content', '')
        if existing_content and len(existing_content) > 500:
            if self.verbose:
                print(f"    ⏭ {raw_job.get('title', 'Unknown')[:40]}: using cached content")
            return raw_job
        
        self.rate_limit()
        
        detail_url = f"{self.api_base_template.format(company=company_slug)}/{job_id}"
        
        try:
            response = self.session.get(detail_url, timeout=15)
            response.raise_for_status()
            
            job_details = response.json()
            
            if self.verbose:
                content_length = len(job_details.get('content', ''))
                title_preview = raw_job.get('title', 'Unknown')[:40]
                if content_length > 500:
                    print(f"    ✓ {title_preview}: {content_length} chars")
                else:
                    print(f"    ⚠ {title_preview}: only {content_length} chars")
            
            return job_details
            
        except requests.RequestException as e:
            if self.verbose:
                print(f"    ⚠ Failed to get details for job {job_id}: {e}")
            return raw_job
    
    def normalize_job(self, raw_job: Dict) -> Dict:
        """Convert Greenhouse JSON to standard format"""
        standard = self.get_standard_schema()
        
        # Parse location
        location_data = raw_job.get('location', {})
        location_name = location_data.get('name', '') if isinstance(location_data, dict) else str(location_data)
        location = self.parser.parse_location(location_name)
        
        # Get department (handle multiple)
        departments = raw_job.get('departments', [])
        department = departments[0].get('name', '') if departments else ''
        
        # Parse description
        description_html = raw_job.get('content', '')
        description_text = self.parser.html_to_text(description_html)
        
        # Normalize the job title
        title = raw_job.get('title', '')
        role_info = normalize_title(title)
        
        standard.update({
            'source_ats': 'greenhouse',
            'source_job_id': str(raw_job.get('id', '')),
            'source_url': raw_job.get('absolute_url', ''),
            'title': title,
            'location_raw': location_name,
            'location_city': location['city'],
            'location_state': location['state'],
            'location_country': location['country'],
            'location_is_remote': location['is_remote'],
            'department': department,
            'seniority_level': role_info['seniority_level'] or self.parser.infer_seniority(title),
            'description': description_html,
            'description_text': description_text,
            'posted_at': self.parser.parse_date(raw_job.get('updated_at')),
            'role_normalized_title': role_info['normalized_title'],
            'role_category': role_info['category'],
            'role_job_family': role_info['job_family'],
        })
        
        return standard
    
    def validate_company_slug(self, company_slug: str) -> Optional[int]:
        """
        Check if a company slug is valid and return job count.
        Returns None if invalid, job count if valid.
        """
        self.rate_limit()
        api_url = self.api_base_template.format(company=company_slug)
        
        try:
            response = self.session.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('jobs', []))
            return None
        except requests.RequestException:
            return None