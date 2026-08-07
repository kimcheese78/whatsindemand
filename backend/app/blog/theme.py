# backend/app/blog/theme.py
"""Light reading theme, page shell, and config-gated AdSense for the blog."""

import os

from app.routes._web import WEB_URL, _esc

BLOG_CSS = """
:root{--ink:#1a1c22;--muted:#5b6472;--border:#e6e8ec;--accent:#0c7489;--bg:#fbfcfd}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.75;
font-family:Georgia,'Iowan Old Style',ui-serif,serif;font-size:19px}
.nav{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:.8rem;
letter-spacing:.04em;text-transform:uppercase;color:var(--muted);
max-width:720px;margin:0 auto;padding:22px 24px 0}
.nav a{color:var(--muted)}
main{max-width:680px;margin:0 auto;padding:24px}
h1{font-size:2.3rem;line-height:1.15;letter-spacing:-.02em;margin:.4em 0 .1em;text-wrap:balance}
h2{font-size:1.5rem;margin:1.6em 0 .3em}h3{font-size:1.2rem}
.meta{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
color:var(--muted);font-size:.9rem;margin:0 0 1.4em}
a{color:var(--accent)}img{max-width:100%;height:auto;border-radius:8px}
pre{background:#0f1620;color:#dbe3ec;padding:16px 18px;border-radius:10px;overflow-x:auto;font-size:.8rem}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85em}
blockquote{margin:1.4em 0;padding-left:18px;border-left:3px solid var(--accent);color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.92rem}
td,th{border-bottom:1px solid var(--border);padding:8px 6px;text-align:left}
.ad-slot{margin:32px 0;min-height:90px;display:flex;align-items:center;justify-content:center}
.related{margin:40px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.related a{display:block;border:1px solid var(--border);border-radius:10px;padding:12px 16px;
margin:8px 0;text-decoration:none;background:#fff}
.postlist{list-style:none;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.postlist li{border-bottom:1px solid var(--border);padding:20px 0}
.postlist h2{font-size:1.35rem;margin:0 0 .2em}
.chips a{display:inline-block;font-size:.78rem;color:var(--muted);border:1px solid var(--border);
border-radius:999px;padding:3px 11px;margin:2px 4px 2px 0;text-decoration:none}
footer{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
color:var(--muted);font-size:.82rem;border-top:1px solid var(--border);margin-top:56px;padding:20px 0 60px}
.subscribe{background:#fff;border:1px solid var(--border);border-radius:12px;padding:20px;margin:40px 0}
.subscribe input{font:inherit;padding:10px 12px;border:1px solid var(--border);border-radius:8px;width:60%}
.subscribe button{font:inherit;padding:10px 16px;border:0;border-radius:8px;background:var(--accent);color:#fff}
"""


def adsense_head() -> str:
    cid = os.environ.get('ADSENSE_CLIENT_ID')
    if not cid:
        return ''
    return (f'<script async crossorigin="anonymous" '
            f'src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={_esc(cid)}"></script>')


def ad_slot(name: str) -> str:
    cid = os.environ.get('ADSENSE_CLIENT_ID')
    if not cid:
        return f'<div class="ad-slot" data-slot="{_esc(name)}"></div>'
    return (f'<div class="ad-slot" data-slot="{_esc(name)}">'
            f'<ins class="adsbygoogle" style="display:block" data-ad-client="{_esc(cid)}" '
            f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script></div>')


def related_roles_html(slugs) -> str:
    if not slugs:
        return ''
    links = ''.join(
        f'<a href="{WEB_URL}/r/{_esc(s)}">See live demand for {_esc(s.replace("-", " ").title())} →</a>'
        for s in slugs
    )
    return f'<div class="related"><strong>Related roles</strong>{links}</div>'


def post_list_html(posts) -> str:
    items = ''.join(
        f'<li><h2><a href="{WEB_URL}/blog/{_esc(p.slug)}">{_esc(p.title)}</a></h2>'
        f'<p class="meta">{p.date.strftime("%B %-d, %Y")} · {p.read_minutes} min read</p>'
        f'<p>{_esc(p.description)}</p></li>'
        for p in posts
    )
    return f'<ul class="postlist">{items}</ul>'


def render_page(*, title, description, canonical, body_html, noindex=False) -> str:
    robots = '<meta name="robots" content="noindex">' if noindex else ''
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="{_esc(description)}">
<link rel="canonical" href="{_esc(canonical)}">
{robots}
<meta property="og:title" content="{_esc(title)}">
<meta property="og:description" content="{_esc(description)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{_esc(canonical)}">
<meta name="twitter:card" content="summary">
{adsense_head()}
<style>{BLOG_CSS}</style>
</head>
<body>
<p class="nav"><a href="{WEB_URL}">WhatsInDemand</a> / <a href="{WEB_URL}/blog">Blog</a></p>
<main>{body_html}</main>
</body></html>"""
