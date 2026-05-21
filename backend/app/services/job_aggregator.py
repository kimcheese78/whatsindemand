# app/services/job_aggregator.py

from app.models import db, Company, Job, JobSkill, Skill, Role, RoleTitleVariation, UnmatchedTitle
from app.scrapers.greenhouse.scraper import GreenhouseScraper
from app.scrapers.lever.scraper import LeverScraper
from app.scrapers.ashby.scraper import AshbyScraper
from app.scrapers.workable.scraper import WorkableScraper
from app.services.skill_extractor import SkillExtractor
from app.utils.role_normalizer_v2 import normalize_title, _should_skip as _is_placeholder_title
from datetime import datetime


class JobAggregator:
    """Aggregate and store jobs from various sources"""
    
    def __init__(self):
        self.scrapers = {
            'greenhouse': GreenhouseScraper(),
            'lever': LeverScraper(),
            'ashby': AshbyScraper(),
            'workable': WorkableScraper(),
        }
        self.skill_extractor = SkillExtractor()
    
    def scrape_company_jobs(self, company_name: str, company_slug: str, ats_type: str = 'greenhouse', industry: str = None):
        """
        Scrape jobs from a company and save to database.
        Also marks jobs as inactive if they're no longer in the ATS.
        """
        if ats_type not in self.scrapers:
            raise ValueError(f"Unsupported ATS type: {ats_type}. Supported: {list(self.scrapers.keys())}")
        
        # Get or create company
        company = Company.query.filter_by(
            ats_type=ats_type,
            greenhouse_slug=company_slug
        ).first()
        
        if not company:
            company = Company(
                name=company_name,
                ats_type=ats_type,
                greenhouse_slug=company_slug,
                industry=industry
            )
            db.session.add(company)
            db.session.commit()
            print(f"  📝 Created new company: {company_name}")
        elif industry and not company.industry:
            company.industry = industry
            db.session.commit()
        
        # Fresh scraper per call — safe for concurrent use
        _scraper_classes = {
            'greenhouse': GreenhouseScraper,
            'lever': LeverScraper,
            'ashby': AshbyScraper,
            'workable': WorkableScraper,
        }
        scraper = _scraper_classes[ats_type]()
        raw_jobs = scraper.get_company_jobs(company_slug)
        
        # Track which source_job_ids we found in this scrape
        scraped_job_ids = set()
        
        saved_count = 0
        for job_data in raw_jobs:
            scraped_job_ids.add(job_data['source_job_id'])
            saved = self._save_job(company.id, job_data)
            if saved:
                saved_count += 1
        # Commit once per company instead of once per job
        db.session.commit()

        # === NEW: Mark jobs as inactive if not in scrape results ===
        closed_count = self._mark_inactive_jobs(company.id, ats_type, scraped_job_ids)
        if closed_count > 0:
            print(f"  📴 Marked {closed_count} jobs as inactive (no longer on ATS)")
        
        # Update company stats
        company.last_scraped_at = datetime.utcnow()
        company.total_jobs_scraped = Job.query.filter_by(company_id=company.id, is_active=True).count()
        db.session.commit()
        
        return saved_count
    
    def _mark_inactive_jobs(self, company_id: int, ats_type: str, scraped_job_ids: set) -> int:
        """
        Mark jobs as inactive if they were not found in the latest scrape.
        """
        # Safety check: don't mark jobs inactive if scrape returned nothing
        # (likely an API error, not all jobs being removed)
        if not scraped_job_ids:
            print(f"  ⚠️ Scrape returned 0 jobs - skipping inactive marking (possible API error)")
            return 0
        
        jobs_to_close = Job.query.filter(
            Job.company_id == company_id,
            Job.source_ats == ats_type,
            Job.is_active == True,
            ~Job.source_job_id.in_(scraped_job_ids)
        ).all()
        
        closed_count = 0
        now = datetime.utcnow()
        
        for job in jobs_to_close:
            job.is_active = False
            job.closed_at = now
            closed_count += 1
        
        if closed_count > 0:
            db.session.commit()
        
        return closed_count
    
    def scrape_from_db(self, ats_type: str = None, resume_after: datetime = None, max_workers: int = 5):
        """
        Scrape every Company row in the DB that has scrape_enabled=True and a slug.
        This is the full-coverage variant (vs. the static registry).

        resume_after: if provided, skip companies already scraped at or after this datetime.
        max_workers: number of parallel threads (default 5, use 1 for sequential).
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from flask import current_app
        from app.models import Company

        q = Company.query.filter(
            Company.scrape_enabled.is_(True),
            Company.ats_type.isnot(None),
            Company.greenhouse_slug.isnot(None),
        )
        if ats_type:
            q = q.filter(Company.ats_type == ats_type)
        if resume_after:
            q = q.filter(
                (Company.last_scraped_at == None) | (Company.last_scraped_at < resume_after)
            )
        companies = q.order_by(Company.name.asc()).all()

        results = {
            'total_companies': len(companies),
            'successful': 0,
            'failed': 0,
            'total_jobs': 0,
            'errors': [],
        }

        print(f"\n{'=' * 60}")
        print(f"Scraping {len(companies)} companies (from DB, workers={max_workers})")
        print(f"{'=' * 60}\n")

        app = current_app._get_current_object()

        def _scrape_one(company):
            with app.app_context():
                try:
                    count = self.scrape_company_jobs(
                        company_name=company.name,
                        company_slug=company.greenhouse_slug,
                        ats_type=company.ats_type,
                        industry=company.industry,
                    )
                    return company.name, count, None
                except Exception as e:
                    return company.name, 0, str(e)
                finally:
                    db.session.remove()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_scrape_one, c): c for c in companies}
            for i, future in enumerate(as_completed(futures), 1):
                name, count, error = future.result()
                if error:
                    results['failed'] += 1
                    results['errors'].append({'company': name, 'error': error})
                    print(f"[{i}/{len(companies)}] {name}: ❌ {error}")
                elif count > 0:
                    results['successful'] += 1
                    results['total_jobs'] += count
                    print(f"[{i}/{len(companies)}] {name}: ✅ {count} jobs")
                else:
                    results['failed'] += 1
                    print(f"[{i}/{len(companies)}] {name}: 0 jobs")

        print("\n── Updating role counts ──")
        self._update_role_counts()

        return results

    def scrape_from_registry(self, ats_type: str = None, industry: str = None):
        """
        Scrape all companies from the central registry.
        
        Args:
            ats_type: Filter by ATS type (None = all)
            industry: Filter by industry (None = all)
            
        Returns:
            Dict with scraping results
        """
        from app.scrapers.companies import get_all_companies, get_companies_by_ats
        
        if ats_type:
            companies = get_companies_by_ats(ats_type)
        else:
            companies = get_all_companies()
        
        if industry:
            companies = [c for c in companies if c['industry'] == industry]
        
        results = {
            'total_companies': len(companies),
            'successful': 0,
            'failed': 0,
            'total_jobs': 0,
            'errors': []
        }
        
        print(f"\n{'=' * 60}")
        print(f"Scraping {len(companies)} companies")
        print(f"{'=' * 60}\n")
        
        for i, company in enumerate(companies):
            slug = company['slug']
            name = company['name']
            ats = company['ats']
            ind = company['industry']
            
            print(f"\n[{i+1}/{len(companies)}] {name} ({ats})")
            
            try:
                count = self.scrape_company_jobs(
                    company_name=name,
                    company_slug=slug,
                    ats_type=ats,
                    industry=ind
                )
                
                if count > 0:
                    results['successful'] += 1
                    results['total_jobs'] += count
                    print(f"  ✅ Saved {count} jobs")
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({'company': name, 'error': str(e)})
                print(f"  ❌ Error: {e}")
        
        return results
    
    def _get_or_create_role(self, job_data: dict) -> Role:
        """Get existing role or queue as candidate if unmatched."""
        normalized_title = job_data.get('role_normalized_title', '')

        if not normalized_title or normalized_title == 'Unknown':
            # Queue raw title for manual review, but not junk/placeholder titles
            role_category = job_data.get('role_category', '')
            raw_title = job_data.get('title', '').strip()
            if raw_title and role_category != 'Skip':
                self._queue_role_candidate(raw_title)
            return None

        role = Role.query.filter_by(normalized_title=normalized_title).first()
        if not role:
            role = Role(
                normalized_title=normalized_title,
                category=job_data.get('role_category', 'Other'),
                seniority_level=job_data.get('seniority_level'),
                job_family=job_data.get('role_job_family', 'Other'),
                total_active_jobs=0
            )
            db.session.add(role)
            db.session.flush()
            print(f"    📌 Created new role: {normalized_title}")

        return role

    def _queue_role_candidate(self, raw_title: str):
        """Upsert an unmatched raw title into unmatched_titles for manual review."""
        from datetime import date
        today = date.today()
        existing = UnmatchedTitle.query.filter_by(raw_title=raw_title).first()
        if existing:
            if existing.status == 'pending':
                existing.job_count += 1
                existing.last_seen = today
        else:
            db.session.add(UnmatchedTitle(
                raw_title=raw_title,
                job_count=1,
                company_count=1,
                first_seen=today,
                last_seen=today,
                status='pending',
            ))
    
    def _track_title_variation(self, role: Role, original_title: str):
        """Track the original title as a variation of the role"""
        if not role or not original_title:
            return
        
        existing = RoleTitleVariation.query.filter_by(
            original_title=original_title
        ).first()
        
        if existing:
            existing.frequency += 1
        else:
            variation = RoleTitleVariation(
                role_id=role.id,
                original_title=original_title,
                frequency=1
            )
            db.session.add(variation)
    
    def _save_job(self, company_id: int, job_data: dict) -> bool:
        """Save a single job to database"""
        try:
            if _is_placeholder_title(job_data.get('title', '')):
                return False

            role = self._get_or_create_role(job_data)
            role_id = role.id if role else None
            
            if role:
                self._track_title_variation(role, job_data['title'])
            
            existing = Job.query.filter_by(
                source_ats=job_data['source_ats'],
                source_job_id=job_data['source_job_id']
            ).first()
            
            if existing:
                description_unchanged = (
                    existing.description_text == job_data['description_text']
                )
                # Update existing job - but PRESERVE posted_at and scraped_at
                existing.title = job_data['title']
                existing.source_url = job_data['source_url']
                existing.location_raw = job_data['location_raw']
                existing.location_city = job_data['location_city']
                existing.location_state = job_data['location_state']
                existing.location_country = job_data['location_country']
                existing.location_is_remote = job_data['location_is_remote']
                existing.department = job_data['department']
                existing.seniority_level = job_data['seniority_level']
                existing.employment_type = job_data.get('employment_type')
                existing.description = job_data['description']
                existing.description_text = job_data['description_text']
                existing.is_active = True
                existing.closed_at = None  # Re-opened if it was closed
                existing.role_id = role_id
                existing.last_seen_at = datetime.utcnow()
                job = existing

                # Skip skill re-extraction when description hasn't changed.
                # That's the slowest step in the scrape (spaCy + regex over the
                # full description text), and there's nothing to update.
                if description_unchanged:
                    db.session.flush()
                    return True
            else:
                # Create new job - set posted_at and scraped_at only here
                job = Job(
                    company_id=company_id,
                    role_id=role_id,
                    source_ats=job_data['source_ats'],
                    source_job_id=job_data['source_job_id'],
                    source_url=job_data['source_url'],
                    title=job_data['title'],
                    location_raw=job_data['location_raw'],
                    location_city=job_data['location_city'],
                    location_state=job_data['location_state'],
                    location_country=job_data['location_country'],
                    location_is_remote=job_data['location_is_remote'],
                    department=job_data['department'],
                    seniority_level=job_data['seniority_level'],
                    employment_type=job_data.get('employment_type'),
                    description=job_data['description'],
                    description_text=job_data['description_text'],
                    posted_at=job_data['posted_at'],  # ← Only set on INSERT
                    scraped_at=job_data['scraped_at'],  # ← Only set on INSERT
                    is_active=True
                )
                db.session.add(job)
                db.session.flush()
            
            job.skills_dirty = True
            db.session.flush()
            return True

        except Exception as e:
            print(f"Error saving job: {e}")
            db.session.rollback()
            return False
    
    def _extract_job_skills(self, job: Job):
        """Extract skills from job description and save to job_skills table"""
        # Extract skills from description
        skills_found = self.skill_extractor.extract_skills(job.description_text)
        
        for skill_data in skills_found:
            job_skill = JobSkill(
                job_id=job.id,
                skill_id=skill_data['skill_id'],
                is_required=skill_data['confidence'] >= 80
            )
            db.session.add(job_skill)
    
    def extract_dirty_jobs(self, batch_size: int = 500):
        """Extract skills for all jobs flagged skills_dirty=True.

        Called after incremental discovery so the SkillExtractor loads a fresh
        copy of the taxonomy (which may include skills just auto-promoted).
        Commits every batch_size jobs so progress survives interruption.
        """
        from app.services.skill_extractor import SkillExtractor
        extractor = SkillExtractor()  # fresh instance — picks up newly promoted skills

        total = Job.query.filter_by(skills_dirty=True).filter(
            Job.description_text.isnot(None),
            Job.description_text != '',
        ).count()

        if not total:
            return 0

        print(f"  Extracting skills for {total:,} jobs (batch_size={batch_size})...", flush=True)
        processed = 0
        start = datetime.utcnow()

        while True:
            batch = Job.query.filter_by(skills_dirty=True).filter(
                Job.description_text.isnot(None),
                Job.description_text != '',
            ).limit(batch_size).all()

            if not batch:
                break

            for job in batch:
                skills_found = extractor.extract_skills(job.description_text)
                for skill_data in skills_found:
                    db.session.add(JobSkill(
                        job_id=job.id,
                        skill_id=skill_data['skill_id'],
                        is_required=skill_data['confidence'] >= 80,
                    ))
                job.skills_dirty = False

            db.session.commit()
            processed += len(batch)
            elapsed = (datetime.utcnow() - start).total_seconds()
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = (total - processed) / rate / 60 if rate > 0 else 0
            print(f"  {processed:,}/{total:,} jobs  ({rate:.1f}/s  ~{remaining:.0f} min left)", flush=True)

        return processed

    def _update_role_counts(self, role_ids: set = None):
        """Update total_active_jobs count for specified roles (or all if none specified)."""
        if role_ids:
            db.session.execute(db.text("""
                UPDATE roles
                SET total_active_jobs = (
                    SELECT COUNT(*) FROM jobs j
                    WHERE j.role_id = roles.id AND j.is_active = TRUE
                )
                WHERE id = ANY(:ids)
            """), {'ids': list(role_ids)})
        else:
            db.session.execute(db.text("""
                UPDATE roles
                SET total_active_jobs = (
                    SELECT COUNT(*) FROM jobs j
                    WHERE j.role_id = roles.id AND j.is_active = TRUE
                )
            """))
        db.session.commit()
    
    def get_jobs_count_by_company(self, company_name: str) -> int:
        """Get number of jobs for a company"""
        company = Company.query.filter_by(name=company_name).first()
        if not company:
            return 0
        return Job.query.filter_by(company_id=company.id, is_active=True).count()