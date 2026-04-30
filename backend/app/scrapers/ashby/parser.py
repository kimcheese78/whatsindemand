# backend/app/scrapers/ashby/parser.py

from bs4 import BeautifulSoup
from datetime import datetime
import re


class AshbyParser:
    """Helper class for parsing Ashby-specific data"""
    
    # US State abbreviations for detection
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }
    
    def parse_location(self, location_data) -> dict:
        """Parse location from Ashby format (can be string or object)"""
        location = {
            'raw': '',
            'city': '',
            'state': '',
            'country': '',
            'is_remote': False
        }
        
        if not location_data:
            return location
        
        # Handle string format
        if isinstance(location_data, str):
            location_string = location_data.strip()
        # Handle object format
        elif isinstance(location_data, dict):
            location_string = location_data.get('name', '') or location_data.get('locationName', '')
        else:
            return location
        
        location['raw'] = location_string
        
        if not location_string:
            return location
        
        # Check for remote
        if re.search(r'\b(remote|anywhere|distributed|worldwide|work from home|wfh)\b', 
                     location_string, re.IGNORECASE):
            location['is_remote'] = True
            # Still try to parse country if it's "Remote - US" style
            if ' - ' in location_string:
                parts = location_string.split(' - ')
                if len(parts) > 1:
                    location['country'] = parts[1].strip()
            return location
        
        # Parse "City, State" or "City, State, Country" or "City, Country"
        parts = [p.strip() for p in location_string.split(',')]
        
        if len(parts) >= 1:
            location['city'] = parts[0]
        
        if len(parts) >= 2:
            second_part = parts[1].strip().upper()
            if second_part in self.US_STATES:
                location['state'] = second_part
                location['country'] = 'US'
            elif len(parts) == 2:
                location['country'] = parts[1].strip()
        
        if len(parts) >= 3:
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
        from app.utils.seniority import infer_seniority
        return infer_seniority(title)
    
    def parse_date(self, date_string: str) -> datetime:
        """Parse ISO date string to datetime"""
        if not date_string:
            return None
        try:
            # Handle various ISO formats
            if 'T' in date_string:
                return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            else:
                return datetime.strptime(date_string, '%Y-%m-%d')
        except:
            return None
    
    def parse_employment_type(self, employment_type: str) -> str:
        """Parse employment type"""
        if not employment_type:
            return ''
        
        et_lower = employment_type.lower()
        
        if 'full' in et_lower:
            return 'full-time'
        elif 'part' in et_lower:
            return 'part-time'
        elif 'contract' in et_lower:
            return 'contract'
        elif 'intern' in et_lower:
            return 'internship'
        elif 'temp' in et_lower:
            return 'temporary'
        else:
            return employment_type