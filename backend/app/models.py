# backend/app/models.py

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ============================================
# USER & AUTHENTICATION MODELS
# ============================================

class User(db.Model):
    """User account model"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    full_name = db.Column(db.String(255))
    auth_provider = db.Column(db.String(50), default='email')
    oauth_provider_id = db.Column(db.String(255))
    has_pro_access = db.Column(db.Boolean, default=False)
    stripe_customer_id = db.Column(db.String(255))
    token_version = db.Column(db.Integer, default=0, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verified_at = db.Column(db.DateTime)
    pending_email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    skills = db.relationship('UserSkill', backref='user', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='user', cascade='all, delete-orphan')
    auth_tokens = db.relationship('AuthToken', backref='user', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'auth_provider': self.auth_provider,
            'has_pro_access': self.has_pro_access,
            'email_verified': bool(self.email_verified),
            'pending_email': self.pending_email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AuthToken(db.Model):
    """Single-use, short-lived tokens for password reset, email verification, email change."""
    __tablename__ = 'auth_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    purpose = db.Column(db.String(32), nullable=False)  # 'password_reset' | 'email_verify' | 'email_change'
    payload = db.Column(db.JSON, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    consumed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserProfile(db.Model):
    """User profile with job search preferences"""
    __tablename__ = 'user_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    target_role = db.Column(db.String(255))
    seniority_level = db.Column(db.String(50))
    location = db.Column(db.String(255))
    resume_file_path = db.Column(db.String(500))
    resume_text = db.Column(db.Text)
    resume_uploaded_at = db.Column(db.DateTime)
    last_analysis_json = db.Column(db.Text)  # Store as JSON string
    last_analysis_at = db.Column(db.DateTime)
    weekly_digest = db.Column(db.Boolean, default=True, nullable=False, server_default='true')

    def to_dict(self):
        return {
            'id': self.id,
            'target_role': self.target_role,
            'seniority_level': self.seniority_level,
            'location': self.location,
            'resume_uploaded_at': self.resume_uploaded_at.isoformat() if self.resume_uploaded_at else None
        }


class UserWeekSnapshot(db.Model):
    """Per-user weekly snapshot of Position Score + its drivers. Written by
    scripts/compute_week_snapshots.py each Friday; read by the dashboard hero
    module and the weekly digest. One row per user per ISO week."""
    __tablename__ = 'user_week_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('org_clients.id', ondelete='CASCADE'), nullable=True, index=True)
    week_start = db.Column(db.Date, nullable=False)  # Monday of the ISO week
    position_score = db.Column(db.Integer)           # 0-100
    match_pct = db.Column(db.Float)                  # skill coverage vs target role (0-1)
    market_momentum = db.Column(db.Float)            # postings_growth_pct for the role
    ai_exposure = db.Column(db.Float)                # role's AI-skill share, current_pct
    matched_jobs_count = db.Column(db.Integer)
    new_matched_jobs = db.Column(db.Integer)
    details_json = db.Column(db.Text)                # components + drivers for the score
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'week_start', name='uq_user_week_snapshot'),)


# ============================================
# B2B ORG MODELS (coach console tier)
# ============================================

class Organization(db.Model):
    """A B2B account: bootcamp career-services team or recruiting agency.
    Tier gating is the `plan` flag — design partners are enabled manually."""
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    org_type = db.Column(db.String(30), default='bootcamp')  # 'bootcamp' | 'agency'
    plan = db.Column(db.String(30), nullable=False, default='trial', server_default='trial')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship('OrgMembership', backref='organization', cascade='all, delete-orphan')
    cohorts = db.relationship('Cohort', backref='organization', cascade='all, delete-orphan')
    clients = db.relationship('Client', backref='organization', cascade='all, delete-orphan')

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'org_type': self.org_type,
                'plan': self.plan}


class OrgMembership(db.Model):
    """Links a login (User) to an Organization with a role."""
    __tablename__ = 'org_memberships'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default='coach')  # 'admin' | 'coach'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('org_id', 'user_id', name='uq_org_membership'),)


class Cohort(db.Model):
    """A group of clients trained together toward a target role, with the
    program's curriculum captured as skill ids (drives curriculum-vs-market)."""
    __tablename__ = 'cohorts'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    target_role = db.Column(db.String(255))
    curriculum_skill_ids = db.Column(db.ARRAY(db.Integer), default=list)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clients = db.relationship('Client', backref='cohort')

    def to_dict(self):
        return {'id': self.id, 'org_id': self.org_id, 'name': self.name,
                'target_role': self.target_role,
                'curriculum_skill_ids': self.curriculum_skill_ids or [],
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None}


class Client(db.Model):
    """A person managed by an org (bootcamp student / coachee). Shaped like a
    consumer user's profile so the shipped per-user analytics (skills, weekly
    snapshots, matched jobs, gap) run against client_id rows unchanged."""
    __tablename__ = 'org_clients'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    cohort_id = db.Column(db.Integer, db.ForeignKey('cohorts.id', ondelete='SET NULL'), nullable=True, index=True)
    coach_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    display_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    target_role = db.Column(db.String(255))
    seniority = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'org_id': self.org_id, 'cohort_id': self.cohort_id,
                'display_name': self.display_name, 'email': self.email,
                'target_role': self.target_role, 'seniority': self.seniority}


# ============================================
# SKILLS MODELS
# ============================================

class Skill(db.Model):
    """Master skills table"""
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    category = db.Column(db.String(50))        # 'technical', 'soft', 'domain'
    subcategory = db.Column(db.String(100))    # e.g. 'AI & Machine Learning'
    industry = db.Column(db.String(100))       # sector tag, e.g. 'Healthcare' (NULL = universal)
    aliases = db.Column(db.ARRAY(db.String))
    is_verified = db.Column(db.Boolean, default=False)

    # Aggregated stats for performance
    total_job_count = db.Column(db.Integer, default=0)
    trending_score = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'skill_id': self.id,
            'name': self.name,
            'category': self.category,
            'subcategory': self.subcategory,
            'industry': self.industry,
            'total_job_count': self.total_job_count,
            'trending_score': self.trending_score
        }


class UserSkill(db.Model):
    """Skills for a person — either a consumer user (user_id) or an org-managed
    client (client_id). Exactly one of the two is set."""
    __tablename__ = 'user_skills'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('org_clients.id', ondelete='CASCADE'), nullable=True, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    confidence_score = db.Column(db.Integer)  # 0-100
    is_custom = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), nullable=False, default='have', server_default='have')  # 'have' | 'learning'
    status_changed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to get skill details
    skill = db.relationship('Skill', backref='user_skills')

    def to_dict(self):
        return {
            'id': self.id,
            'skill_id': self.skill_id,
            'skill_name': self.skill.name,
            'skill_category': self.skill.category,
            'confidence_score': self.confidence_score,
            'is_custom': self.is_custom,
            'status': self.status,
            'status_changed_at': self.status_changed_at.isoformat() if self.status_changed_at else None
        }

# ============================================
# COMPANY & ROLES MODELS
# ============================================

class Company(db.Model):
    """Companies using various ATS systems"""
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(100))  # ADD THIS LINE
    ats_type = db.Column(db.String(50))  # 'greenhouse', 'lever', etc.
    greenhouse_slug = db.Column(db.String(255))
    website = db.Column(db.String(500))
    logo_url = db.Column(db.String(500))
    last_scraped_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    # Company profile fields
    location = db.Column(db.String(255))        # e.g. "San Francisco, CA"
    founded_year = db.Column(db.Integer)         # e.g. 2012
    company_type = db.Column(db.String(50))      # "Public", "Private", "Nonprofit", etc.
    valuation = db.Column(db.String(100))        # e.g. "$4.5B", "Public (NYSE: X)"
    
    # NEW: Scraping configuration
    scrape_enabled = db.Column(db.Boolean, default=True)
    scrape_frequency_hours = db.Column(db.Integer, default=24)
    total_jobs_scraped = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', backref='company', cascade='all, delete-orphan')
    scraper_logs = db.relationship('ScraperLog', backref='company', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'ats_type': self.ats_type,
            'website': self.website,
            'logo_url': self.logo_url,
            'total_jobs_scraped': self.total_jobs_scraped,
            'last_scraped_at': self.last_scraped_at.isoformat() if self.last_scraped_at else None
        }


class Role(db.Model):
    """Normalized job roles/titles"""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    normalized_title = db.Column(db.String(255), unique=True, nullable=False, index=True)
    category = db.Column(db.String(100), index=True)  # Engineering, Design, Product, Sales, Marketing, etc.
    seniority_level = db.Column(db.String(50), index=True)  # entry, mid, senior, lead, principal
    job_family = db.Column(db.String(100))  # Software Engineer, Product Manager, Designer, etc.
    
    # Search aliases for autocomplete (curated, distinct from RoleTitleVariation normalizer mappings)
    search_aliases = db.Column(db.ARRAY(db.String), default=list)

    # Aggregated stats (updated by background job)
    total_active_jobs = db.Column(db.Integer, default=0)
    avg_salary_min = db.Column(db.Integer)
    avg_salary_max = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', backref='role', lazy='dynamic')
    title_variations = db.relationship('RoleTitleVariation', backref='role', lazy=True, cascade='all, delete-orphan')
    skill_demands = db.relationship('SkillDemand', backref='role', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'normalized_title': self.normalized_title,
            'category': self.category,
            'seniority_level': self.seniority_level,
            'job_family': self.job_family,
            'total_active_jobs': self.total_active_jobs,
            'avg_salary_range': f"${self.avg_salary_min:,}-${self.avg_salary_max:,}" if self.avg_salary_min and self.avg_salary_max else None
        }


class RoleTitleVariation(db.Model):
    """Maps job title variations to normalized roles"""
    __tablename__ = 'role_title_variations'
    
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False, index=True)
    original_title = db.Column(db.String(255), unique=True, nullable=False, index=True)
    frequency = db.Column(db.Integer, default=1)  # How often this variation appears
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'original_title': self.original_title,
            'normalized_title': self.role.normalized_title if self.role else None,
            'frequency': self.frequency
        }


# ============================================
# JOB POSTINGS MODEL
# ============================================

class Job(db.Model):
    """Job postings from various sources"""
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), index=True)  # NEW: Link to normalized role
    
    source_ats = db.Column(db.String(50))
    source_job_id = db.Column(db.String(255))
    source_url = db.Column(db.String(1000))
    title = db.Column(db.String(500), nullable=False)
    location_raw = db.Column(db.String(512))
    location_city = db.Column(db.String(255))
    location_state = db.Column(db.String(100))
    location_country = db.Column(db.String(100))
    location_is_remote = db.Column(db.Boolean, default=False)
    department = db.Column(db.String(255))
    seniority_level = db.Column(db.String(50))
    employment_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    description_text = db.Column(db.Text)
    requirements_text = db.Column(db.Text)
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    salary_currency = db.Column(db.String(10), default='USD')
    salary_min_usd = db.Column(db.Integer)
    salary_max_usd = db.Column(db.Integer)
    posted_at = db.Column(db.DateTime)
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    skills_dirty = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (
        db.UniqueConstraint('source_ats', 'source_job_id', name='uq_jobs_source_job'),
    )

    # Relationships
    required_skills = db.relationship('JobSkill', backref='job', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'company': self.company.to_dict() if self.company else None,
            'role': self.role.to_dict() if self.role else None,
            'title': self.title,
            'location': {
                'raw': self.location_raw,
                'city': self.location_city,
                'state': self.location_state,
                'country': self.location_country,
                'is_remote': self.location_is_remote
            },
            'department': self.department,
            'seniority_level': self.seniority_level,
            'salary_range': f"${self.salary_min:,}-${self.salary_max:,}" if self.salary_min and self.salary_max else None,
            'source_url': self.source_url,
            'posted_at': self.posted_at.isoformat() if self.posted_at else None
        }


class JobSkill(db.Model):
    """Skills required by jobs"""
    __tablename__ = 'job_skills'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    is_required = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('job_id', 'skill_id', name='uq_job_skills_job_skill'),
    )

    # Relationship
    skill = db.relationship('Skill', backref='job_skills')


# ============================================
# SKILLS DEMAND TRACKING (NEW)
# ============================================

class SkillDemand(db.Model):
    """Time-series data for skill demand by role"""
    __tablename__ = 'skills_demand'
    
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), index=True)  # Optional: demand per role
    
    # Time period
    period_date = db.Column(db.Date, nullable=False, index=True)  # Start of period (e.g., Monday for weekly)
    period_type = db.Column(db.String(20), default='week')  # day, week, month
    
    # Demand metrics
    job_count = db.Column(db.Integer, default=0)  # Jobs requiring this skill
    required_count = db.Column(db.Integer, default=0)  # Jobs where skill is marked required
    company_count = db.Column(db.Integer, default=0)  # Unique companies
    
    # Salary data
    avg_salary_min = db.Column(db.Integer)
    avg_salary_max = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    skill = db.relationship('Skill', backref='demand_history')
    
    __table_args__ = (
        db.UniqueConstraint('skill_id', 'role_id', 'period_date', 'period_type', name='unique_skill_demand_period'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'skill_name': self.skill.name if self.skill else None,
            'role_title': self.role.normalized_title if self.role else None,
            'period_date': self.period_date.isoformat(),
            'period_type': self.period_type,
            'job_count': self.job_count,
            'required_count': self.required_count,
            'company_count': self.company_count,
            'avg_salary_min': self.avg_salary_min,
            'avg_salary_max': self.avg_salary_max
        }


# ============================================
# SCRAPER LOGS (NEW)
# ============================================

class ScraperLog(db.Model):
    """Track scraping operations"""
    __tablename__ = 'scraper_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), index=True)
    
    # Scrape details
    scrape_type = db.Column(db.String(50), default='full')  # full, incremental
    status = db.Column(db.String(20), nullable=False, index=True)  # success, partial, failed
    
    # Metrics
    jobs_found = db.Column(db.Integer, default=0)
    jobs_new = db.Column(db.Integer, default=0)
    jobs_updated = db.Column(db.Integer, default=0)
    jobs_removed = db.Column(db.Integer, default=0)
    
    # Timing
    started_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Float)
    
    # Error tracking
    error_message = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'company_name': self.company.name if self.company else None,
            'status': self.status,
            'jobs_found': self.jobs_found,
            'jobs_new': self.jobs_new,
            'jobs_updated': self.jobs_updated,
            'jobs_removed': self.jobs_removed,
            'duration_seconds': self.duration_seconds,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


# ============================================
# SKILL DISCOVERY MODELS
# ============================================

class UnmatchedTitle(db.Model):
    """Raw job titles that couldn't be mapped to a canonical role, pending manual review."""
    __tablename__ = 'unmatched_titles'

    id = db.Column(db.Integer, primary_key=True)
    raw_title = db.Column(db.String(500), unique=True, nullable=False, index=True)
    job_count = db.Column(db.Integer, default=1)
    company_count = db.Column(db.Integer, default=1)
    first_seen = db.Column(db.Date)
    last_seen = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending', index=True)  # pending/approved/rejected
    mapped_role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    rejected_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SkillCandidate(db.Model):
    """Skill candidates discovered from job descriptions, pending promotion review."""
    __tablename__ = 'skill_candidates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    job_count = db.Column(db.Integer, default=0)
    company_count = db.Column(db.Integer, default=0)
    first_seen = db.Column(db.Date)
    last_seen = db.Column(db.Date)
    methods = db.Column(db.ARRAY(db.String))
    example_contexts = db.Column(db.ARRAY(db.String))
    status = db.Column(db.String(20), default='pending', index=True)  # pending/approved/rejected
    promoted_skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=True)
    promoted_at = db.Column(db.DateTime, nullable=True)
    rejected_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs = db.relationship('SkillCandidateJob', backref='candidate', cascade='all, delete-orphan')


class SkillCandidateJob(db.Model):
    """Tracks which jobs mentioned each skill candidate (for targeted backfill on promotion)."""
    __tablename__ = 'skill_candidate_jobs'

    candidate_id = db.Column(db.Integer, db.ForeignKey('skill_candidates.id', ondelete='CASCADE'), primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id', ondelete='CASCADE'), primary_key=True)


class DiscoveryRun(db.Model):
    """Audit log for incremental discovery runs."""
    __tablename__ = 'discovery_runs'

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime)
    jobs_processed = db.Column(db.Integer, default=0)
    candidates_upserted = db.Column(db.Integer, default=0)
    candidates_promoted = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='running')  # running/completed/failed
    error = db.Column(db.Text)


# ============================================
# PAYMENT MODEL
# ============================================

class Payment(db.Model):
    """Payment transactions"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(255))
    amount = db.Column(db.Integer)  # in cents
    currency = db.Column(db.String(10), default='USD')
    status = db.Column(db.String(50))  # 'pending', 'succeeded', 'failed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount / 100,  # convert cents to dollars
            'currency': self.currency,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }