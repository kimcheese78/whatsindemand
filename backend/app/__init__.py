# backend/app/__init__.py

from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.models import db
import os
from app.config import config

migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'development')
    
    app = Flask(__name__)
    cfg = config[config_name]
    app.config.from_object(cfg)
    if hasattr(cfg, 'init_app'):
        cfg.init_app(app)

    # Initialize database
    db.init_app(app)

    # Initialize Flask-Migrate
    migrate.init_app(app, db)

    # Initialize rate limiter
    limiter.init_app(app)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({'error': 'Too many requests. Please try again later.'}), 429

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
        return response

    # Enable CORS — origin allowlist comes from config (env-driven).
    CORS(app,
        origins=app.config['CORS_ORIGINS'],
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        supports_credentials=False)
    
    # ============================================
    # REGISTER BLUEPRINTS
    # ============================================

    # Auth & Payment
    from app.routes import auth, payment
    app.register_blueprint(auth.bp, url_prefix='/api/auth')
    app.register_blueprint(payment.bp, url_prefix='/api/payment')
    
    # Session persistence
    from app.routes import analysis
    app.register_blueprint(analysis.bp, url_prefix='/api/session')  # Renamed for clarity
    
    # Job data (existing)
    from app.routes import jobs
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    
    # Skill gap data (existing)
    from app.routes.skill_gap import skill_gap_bp
    app.register_blueprint(skill_gap_bp)
    
    # Locations data
    from app.routes.locations import locations_bp
    app.register_blueprint(locations_bp)

    # Matched jobs (personalized live postings by skill coverage)
    from app.routes.matched_jobs import matched_jobs_bp
    app.register_blueprint(matched_jobs_bp)

    # Position score (weekly-tracked standing vs. target role)
    from app.routes.position_score import position_score_bp
    app.register_blueprint(position_score_bp)

    # NEW: Career intelligence endpoints
    from app.routes.roles import roles_bp
    from app.routes.companies import companies_bp
    from app.routes.skills import skills_bp
    
    app.register_blueprint(roles_bp)       # /api/roles/*
    app.register_blueprint(companies_bp)   # /api/companies/*
    app.register_blueprint(skills_bp)      # /api/skills/*

    # Public server-rendered pages for SEO (/r/<slug>, /r/, /sitemap.xml)
    from app.routes.public import public_bp
    app.register_blueprint(public_bp)
    
    # Health check
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'message': 'WhatsInDemand API is running'}
    
    return app