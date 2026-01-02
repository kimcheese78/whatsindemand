# app/scrapers/base_scraper.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

class BaseScraper(ABC):
    """Abstract base class for all ATS/job board scrapers"""
    
    def __init__(self):
        self.session = self._create_session()
        self.name = self.__class__.__name__
        self.rate_limit_delay = 1.0  # seconds between requests
        self.last_request_time = None
        
    def _create_session(self):
        """Create requests session with retry logic"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'User-Agent': 'WhatsInDemand/1.0 (Job Aggregator; +https://whatsindemand.com)'
        })
        return session
    
    @abstractmethod
    def get_company_jobs(self, company_identifier: str) -> List[Dict]:
        """Fetch all jobs for a specific company"""
        pass
    
    @abstractmethod
    def normalize_job(self, raw_job: Dict) -> Dict:
        """Convert ATS-specific format to standardized format"""
        pass
    
    def rate_limit(self):
        """Enforce rate limiting between requests"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    def get_standard_schema(self) -> Dict:
        """Return the standard job schema"""
        return {
            'source_ats': '',
            'source_job_id': '',
            'source_url': '',
            'company_name': '',
            'title': '',
            'location_raw': '',
            'location_city': '',
            'location_state': '',
            'location_country': '',
            'location_is_remote': False,
            'department': '',
            'seniority_level': '',
            'employment_type': '',
            'description': '',
            'description_text': '',
            'posted_at': None,
            'scraped_at': datetime.utcnow(),
            # === NEW: Role normalization fields ===
            'role_normalized_title': '',
            'role_category': '',
            'role_job_family': '',
        }