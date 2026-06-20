import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY')
    FLASK_APP = os.getenv('FLASK_APP', 'run.py')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Database
    database_url = os.getenv('DATABASE_URL')
    # Fix for psycopg (version 3) - replace postgresql:// with postgresql+psycopg://
    if database_url and database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    
    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './uploads')
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 5242880))  # 5MB default
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
    
    # Stripe
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID', 'price_xxxxx')  # Update with real price ID
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')
    
    # URLs
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5001')

    # CORS — comma-separated origin allowlist. Subclasses set defaults.
    CORS_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Scraping
    SCRAPER_USER_AGENT = 'WhatsInDemand/1.0 (Job Aggregator; +https://whatsindemand.com)'
    SCRAPER_RATE_LIMIT = 1.0  # seconds between requests
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-secret-not-for-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-only-jwt-secret-not-for-production')
    # In dev, allow any origin so localhost:3000, 127.0.0.1, etc. all work.
    CORS_ORIGINS = Config.CORS_ORIGINS or ['*']

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    # In prod, required secrets must be set explicitly via env. Refuse to boot otherwise.
    @classmethod
    def init_app(cls, app):
        missing = [v for v in ('SECRET_KEY', 'JWT_SECRET_KEY', 'CORS_ORIGINS') if not app.config.get(v)]
        if missing:
            raise RuntimeError(
                f'Missing required env vars for production: {", ".join(missing)}'
            )

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg://postgres:password@localhost:5432/whatsindemand_test'
    CORS_ORIGINS = ['*']

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
