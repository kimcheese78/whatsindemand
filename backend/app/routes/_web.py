# backend/app/routes/_web.py
"""Shared helpers for server-rendered public pages (/r, /blog, sitemap)."""

WEB_URL = 'https://www.whatsindemand.com'
CACHE_HEADER = 'public, max-age=86400, stale-while-revalidate=604800'


def _esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def _slugify(title: str) -> str:
    return '-'.join(title.lower().replace('/', ' ').replace('&', ' ').split())
