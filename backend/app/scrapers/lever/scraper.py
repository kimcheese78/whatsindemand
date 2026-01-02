# backend/app/scrapers/lever/scraper.py

from app.scrapers.base_scraper import BaseScraper
from app.scrapers.lever.parser import LeverParser
from app.utils.role_normalizer import normalize_title
from typing import List, Dict, Optional
import requests


class LeverScraper(BaseScraper):
    """Scraper for Lever ATS"""
    
    def __init__(self, verbose: bool = False):
        super().__init__()
        self.parser = LeverParser()
        self.api_base_template = "https://api.lever.co/v0/postings/{company}?mode=json"
        self.verbose = verbose
    
    def get_company_jobs(self, company_slug: str) -> List[Dict]:
        """Fetch all jobs for a company using Lever API"""
        self.rate_limit()
        
        api_url = self.api_base_template.format(company=company_slug)
        
        try:
            response = self.session.get(api_url, timeout=15)
            response.raise_for_status()
            
            raw_jobs = response.json()
            
            # Lever returns array directly (not wrapped in object)
            if not isinstance(raw_jobs, list):
                print(f"❌ Unexpected response format for {company_slug}")
                return []
            
            print(f"📋 Found {len(raw_jobs)} jobs for {company_slug}")
            
            if not raw_jobs:
                return []
            
            normalized_jobs = []
            failed_count = 0
            
            for i, raw_job in enumerate(raw_jobs):
                try:
                    normalized = self.normalize_job(raw_job)
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
    
    def normalize_job(self, raw_job: Dict) -> Dict:
        """Convert Lever JSON to standard format"""
        standard = self.get_standard_schema()
        
        # Categories contain location, team, commitment
        categories = raw_job.get('categories', {})
        location_string = categories.get('location', '')
        department = categories.get('team', '')
        commitment = categories.get('commitment', '')
        
        # Parse location
        location = self.parser.parse_location(location_string)
        
        # Build full description
        description_html = self.parser.build_description_html(raw_job)
        description_text = self.parser.html_to_text(description_html)
        
        # Normalize the job title
        title = raw_job.get('text', '')
        role_info = normalize_title(title)
        
        standard.update({
            'source_ats': 'lever',
            'source_job_id': str(raw_job.get('id', '')),
            'source_url': raw_job.get('hostedUrl', ''),
            'title': title,
            'location_raw': location_string,
            'location_city': location['city'],
            'location_state': location['state'],
            'location_country': location['country'],
            'location_is_remote': location['is_remote'],
            'department': department,
            'seniority_level': role_info['seniority_level'] or self.parser.infer_seniority(title),
            'employment_type': self.parser.parse_commitment(commitment),
            'description': description_html,
            'description_text': description_text,
            'posted_at': self.parser.parse_date(raw_job.get('createdAt')),
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
                if isinstance(data, list):
                    return len(data)
            return None
        except requests.RequestException:
            return None