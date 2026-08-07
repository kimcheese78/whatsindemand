# backend/app/blog/feed.py
"""Pure builders: RSS 2.0 feed and blog sitemap URLs."""

from email.utils import format_datetime
from datetime import datetime, timezone

from app.routes._web import WEB_URL, _esc


def _rfc822(date):
    return format_datetime(datetime(date.year, date.month, date.day, tzinfo=timezone.utc))


def render_rss(posts) -> str:
    items = ''.join(
        f'<item>'
        f'<title>{_esc(p.title)}</title>'
        f'<link>{WEB_URL}/blog/{_esc(p.slug)}</link>'
        f'<guid>{WEB_URL}/blog/{_esc(p.slug)}</guid>'
        f'<pubDate>{_rfc822(p.date)}</pubDate>'
        f'<description>{_esc(p.description)}</description>'
        f'</item>'
        for p in posts
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<rss version="2.0"><channel>'
            '<title>WhatsInDemand Blog</title>'
            f'<link>{WEB_URL}/blog</link>'
            '<description>Job-market intelligence: skills, roles, and hiring trends.</description>'
            f'{items}</channel></rss>')


def blog_sitemap_urls(posts) -> list:
    today = datetime.utcnow().strftime('%Y-%m-%d')
    urls = [f'<url><loc>{WEB_URL}/blog</loc><lastmod>{today}</lastmod></url>']
    tags = set()
    for p in posts:
        urls.append(
            f'<url><loc>{WEB_URL}/blog/{_esc(p.slug)}</loc>'
            f'<lastmod>{p.date.isoformat()}</lastmod></url>'
        )
        tags.update(p.tags)
    for t in sorted(tags):
        urls.append(f'<url><loc>{WEB_URL}/blog/tag/{_esc(t)}</loc><lastmod>{today}</lastmod></url>')
    return urls
