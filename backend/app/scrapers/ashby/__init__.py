# backend/app/scrapers/ashby/__init__.py
from app.scrapers.ashby.scraper import AshbyScraper
from app.scrapers.ashby.parser import AshbyParser

__all__ = ['AshbyScraper', 'AshbyParser']