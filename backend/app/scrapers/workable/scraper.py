from app.scrapers.base_scraper import BaseScraper, BoardUnavailableError
from app.scrapers.workable.parser import WorkableParser
from app.utils.role_normalizer_v2 import normalize_title
from typing import List, Dict
import requests

JOBS_ENDPOINT = 'https://apply.workable.com/api/v3/accounts/{slug}/jobs'
DETAIL_ENDPOINT = 'https://apply.workable.com/api/v3/accounts/{slug}/jobs/{shortcode}'
POST_BODY = {'query': '', 'location': [], 'department': [], 'worktype': [], 'remote': []}


class WorkableScraper(BaseScraper):
    """Scraper for Workable ATS (POST-based public API)"""

    def __init__(self, verbose: bool = False):
        super().__init__()
        self.parser = WorkableParser()
        self.verbose = verbose

    def get_company_jobs(self, company_slug: str) -> List[Dict]:
        self.rate_limit()

        url = JOBS_ENDPOINT.format(slug=company_slug)

        try:
            response = self.session.post(
                url,
                json=POST_BODY,
                headers={'Content-Type': 'application/json'},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            raw_jobs = data.get('results', [])
            total = data.get('total', len(raw_jobs))
            print(f'📋 Found {total} jobs for {company_slug}')

            if not raw_jobs:
                return []

            normalized_jobs = []
            failed = 0

            for i, raw_job in enumerate(raw_jobs):
                try:
                    shortcode = raw_job.get('shortcode', '')
                    if shortcode:
                        raw_job = self._get_job_details(company_slug, shortcode, raw_job)

                    normalized = self.normalize_job(raw_job)
                    normalized['company_slug'] = company_slug
                    normalized_jobs.append(normalized)
                except Exception as e:
                    failed += 1
                    if self.verbose:
                        print(f'  ⚠ Error processing job {raw_job.get("shortcode")}: {e}')

                if (i + 1) % 50 == 0:
                    print(f'  Processed {i + 1}/{len(raw_jobs)}...')

            status = '✅' if failed == 0 else '⚠️'
            print(f'{status} Fetched {len(normalized_jobs)} jobs from {company_slug}' +
                  (f' ({failed} failed)' if failed else ''))

            return normalized_jobs

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else None
            if code == 404:
                print(f'❌ Company not found: {company_slug}')
            elif code == 429:
                print(f'⏳ Rate limited for {company_slug} — try again later')
            else:
                print(f'❌ HTTP {code} for {company_slug}: {e}')
            raise BoardUnavailableError(company_slug, code, str(e))
        except requests.RequestException as e:
            print(f'❌ Request failed for {company_slug}: {e}')
            raise BoardUnavailableError(company_slug, None, str(e))

    def _get_job_details(self, company_slug: str, shortcode: str, raw_job: Dict) -> Dict:
        """Fetch full description from detail endpoint"""
        self.rate_limit()
        url = DETAIL_ENDPOINT.format(slug=company_slug, shortcode=shortcode)
        try:
            r = self.session.get(url, timeout=15)
            if r.status_code == 200:
                detail = r.json()
                raw_job = {**raw_job, **detail}
        except requests.RequestException:
            pass
        return raw_job

    def normalize_job(self, raw_job: Dict) -> Dict:
        standard = self.get_standard_schema()

        location_data = raw_job.get('location', '')
        location = self.parser.parse_location(location_data)

        is_remote = raw_job.get('remote', False) or location['is_remote']

        title = raw_job.get('title', '')
        role_info = normalize_title(title)

        description_html = raw_job.get('description', '')
        description_text = self.parser.html_to_text(description_html)

        posted_at = self.parser.parse_date(
            raw_job.get('published_on') or raw_job.get('created_at')
        )

        standard.update({
            'source_ats': 'workable',
            'source_job_id': raw_job.get('shortcode', str(raw_job.get('id', ''))),
            'source_url': raw_job.get('url', raw_job.get('application_url', '')),
            'title': title,
            'location_raw': location['raw'],
            'location_city': location['city'],
            'location_state': location['state'],
            'location_country': location['country'],
            'location_is_remote': is_remote,
            'department': raw_job.get('department', ''),
            'seniority_level': role_info['seniority_level'] or self.parser.infer_seniority(title),
            'employment_type': self.parser.parse_employment_type(raw_job.get('worktype', '')),
            'description': description_html,
            'description_text': description_text,
            'posted_at': posted_at,
            'role_normalized_title': role_info['normalized_title'],
            'role_category': role_info['category'],
            'role_job_family': role_info['job_family'],
        })

        return standard
