from bs4 import BeautifulSoup
from datetime import datetime
import re


class WorkableParser:

    US_STATES = {
        'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN',
        'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV',
        'NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN',
        'TX','UT','VT','VA','WA','WV','WI','WY','DC'
    }

    def parse_location(self, location_data) -> dict:
        result = {'raw': '', 'city': '', 'state': '', 'country': '', 'is_remote': False}

        if not location_data:
            return result

        if isinstance(location_data, dict):
            location_str = (location_data.get('location') or
                            location_data.get('name') or
                            location_data.get('city', ''))
            country = location_data.get('country', '')
            if country:
                result['country'] = country
        elif isinstance(location_data, str):
            location_str = location_data
        else:
            return result

        result['raw'] = location_str

        if not location_str:
            return result

        if re.search(r'\b(remote|anywhere|distributed|worldwide|work from home|wfh)\b',
                     location_str, re.IGNORECASE):
            result['is_remote'] = True
            if ' - ' in location_str:
                result['country'] = location_str.split(' - ', 1)[1].strip()
            return result

        parts = [p.strip() for p in location_str.split(',')]
        if parts:
            result['city'] = parts[0]
        if len(parts) == 2:
            second = parts[1].strip().upper()
            if second in self.US_STATES:
                result['state'] = second
                result['country'] = result['country'] or 'US'
            else:
                result['country'] = result['country'] or parts[1].strip()
        elif len(parts) >= 3:
            result['state'] = parts[1].strip()
            result['country'] = result['country'] or parts[2].strip()

        return result

    def html_to_text(self, html: str) -> str:
        if not html:
            return ''
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text(separator='\n', strip=True)

    def parse_employment_type(self, worktype: str) -> str:
        if not worktype:
            return ''
        wt = worktype.lower()
        if 'full' in wt:
            return 'full-time'
        elif 'part' in wt:
            return 'part-time'
        elif 'contract' in wt or 'freelance' in wt:
            return 'contract'
        elif 'intern' in wt:
            return 'internship'
        elif 'temp' in wt:
            return 'temporary'
        return worktype

    def infer_seniority(self, title: str) -> str:
        from app.utils.seniority import infer_seniority
        return infer_seniority(title)

    def parse_date(self, date_string: str):
        if not date_string:
            return None
        try:
            if 'T' in str(date_string):
                return datetime.fromisoformat(str(date_string).replace('Z', '+00:00'))
            return datetime.strptime(str(date_string), '%Y-%m-%d')
        except Exception:
            return None
