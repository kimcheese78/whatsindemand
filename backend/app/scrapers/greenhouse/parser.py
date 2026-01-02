# backend/app/scrapers/greenhouse/parser.py

from bs4 import BeautifulSoup
from datetime import datetime
import re


class GreenhouseParser:
    """Helper class for parsing Greenhouse-specific data"""
    
    # US State abbreviations for detection
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }
    
    def parse_location(self, location_string: str) -> dict:
        """Parse location string into structured format"""
        location = {
            'raw': location_string,
            'city': '',
            'state': '',
            'country': '',
            'is_remote': False
        }
        
        if not location_string:
            return location
        
        location_string = location_string.strip()
        
        # Check for remote
        if re.search(r'\b(remote|anywhere|distributed|worldwide)\b', location_string, re.IGNORECASE):
            location['is_remote'] = True
            # Still try to parse location if it's "Remote - US" style
            if ' - ' in location_string:
                parts = location_string.split(' - ')
                if len(parts) > 1:
                    location['country'] = parts[1].strip()
            elif ', ' in location_string:
                # Handle "Remote, US" format
                parts = location_string.split(', ')
                if len(parts) > 1:
                    location['country'] = parts[-1].strip()
            return location
        
        # Parse "City, State" or "City, State, Country" or "City, Country"
        parts = [p.strip() for p in location_string.split(',')]
        
        if len(parts) >= 1:
            location['city'] = parts[0]
        
        if len(parts) >= 2:
            second_part = parts[1].strip().upper()
            # FIX: Check against actual US state codes, not just length
            if second_part in self.US_STATES:
                location['state'] = second_part
                location['country'] = 'US'
            elif len(parts) == 2:
                # Assume it's a country
                location['country'] = parts[1].strip()
        
        if len(parts) >= 3:
            # City, State, Country format
            location['state'] = parts[1].strip()
            location['country'] = parts[2].strip()
        
        return location
    
    def html_to_text(self, html: str) -> str:
        """Convert HTML to plain text"""
        if not html:
            return ''
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    
    def infer_seniority(self, title: str) -> str:
        """Infer seniority level from job title"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['principal', 'staff', 'distinguished', 'fellow', 'vp', 
                                                  'head of', 'director', 'chief', 'founding']):
            return 'principal'
        elif any(word in title_lower for word in ['lead', 'senior', 'sr.', 'sr ', 'iii', ' 3']):
            return 'senior'
        elif any(word in title_lower for word in ['junior', 'jr.', 'jr ', 'associate', 'entry', ' i', ' 1']):
            return 'entry'
        elif any(word in title_lower for word in ['intern', 'internship', 'co-op', 'coop']):
            return 'intern'
        else:
            return 'mid'
    
    def parse_date(self, date_string: str) -> datetime:
        """Parse ISO date string to datetime"""
        if not date_string:
            return None
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            return None