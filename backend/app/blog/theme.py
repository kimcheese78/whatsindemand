# backend/app/blog/theme.py
"""Dark reading theme (matches the app: IBM Plex, zinc-900), page shell, and config-gated AdSense."""

import os

from app.routes._web import WEB_URL, _esc

BLOG_CSS = """
:root{
--bg:#18181b;--ink:rgba(255,255,255,.92);--strong:rgba(255,255,255,.96);
--muted:rgba(255,255,255,.55);--faint:rgba(255,255,255,.38);
--line:rgba(255,255,255,.10);--line-strong:rgba(255,255,255,.20);
--surface:rgba(255,255,255,.05);--surface-raised:rgba(255,255,255,.08)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.75;font-size:19px;
font-family:'IBM Plex Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.nav{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);
max-width:720px;margin:0 auto;padding:26px 24px 0}
.nav a{color:var(--muted);text-decoration:none}
.nav a:hover{color:var(--strong)}
main{max-width:680px;margin:0 auto;padding:20px 24px 0}
h1{font-size:2.4rem;line-height:1.12;letter-spacing:-.02em;font-weight:600;color:var(--strong);
margin:.5em 0 .15em;text-wrap:balance}
h2{font-size:1.5rem;line-height:1.25;letter-spacing:-.01em;font-weight:600;color:var(--strong);margin:1.7em 0 .4em}
h3{font-size:1.2rem;font-weight:600;color:var(--strong);margin:1.5em 0 .3em}
p{margin:1.1em 0}
strong{color:var(--strong)}
a{color:#fff;text-decoration:underline;text-underline-offset:2px;text-decoration-color:rgba(255,255,255,.35)}
a:hover{text-decoration-color:#fff}
img{max-width:100%;height:auto;border-radius:10px}
.meta{color:var(--muted);font-size:.92rem;margin:0 0 1.6em}
pre{background:var(--surface);border:1px solid var(--line);color:#e7e9ee;padding:16px 18px;
border-radius:10px;overflow-x:auto;font-size:.82rem;
font-family:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace}
code{font-family:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85em}
p code,li code{background:var(--surface);border:1px solid var(--line);border-radius:5px;padding:1px 5px}
pre code{background:none;border:0;padding:0}
blockquote{margin:1.5em 0;padding:2px 0 2px 20px;border-left:3px solid var(--line-strong);color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.95rem;margin:1.2em 0}
td,th{border-bottom:1px solid var(--line);padding:10px 8px;text-align:left}
th{color:var(--muted);font-weight:600}
hr{border:0;border-top:1px solid var(--line);margin:2em 0}
.ad-slot{margin:36px 0;min-height:90px;display:flex;align-items:center;justify-content:center;
border:1px dashed var(--line);border-radius:10px}
.related{margin:44px 0}
.related strong{display:block;font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);margin-bottom:10px}
.related a{display:block;border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:8px 0;
text-decoration:none;color:var(--strong);background:var(--surface);transition:background .15s,border-color .15s}
.related a:hover{background:var(--surface-raised);border-color:var(--line-strong)}
.postlist{list-style:none;padding:0;margin:8px 0 0}
.postlist li{border-bottom:1px solid var(--line);padding:26px 0}
.postlist h2{font-size:1.4rem;margin:0 0 .25em}
.postlist h2 a{color:var(--strong);text-decoration:none}
.postlist h2 a:hover{text-decoration:underline}
.postlist .meta{margin:0 0 .5em}
.postlist p{color:var(--muted);margin:0}
.chips{margin:18px 0 8px}
.chips a{display:inline-block;font-size:12px;letter-spacing:.04em;color:var(--muted);
border:1px solid var(--line);border-radius:999px;padding:4px 12px;margin:3px 6px 3px 0;
text-decoration:none;background:var(--surface)}
.chips a:hover{color:var(--strong);border-color:var(--line-strong)}
footer{color:var(--faint);font-size:.85rem;border-top:1px solid var(--line);margin-top:60px;padding:22px 0 64px}
footer a{color:var(--muted)}
.subscribe{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px;margin:44px 0}
.subscribe strong{display:block;color:var(--strong);font-size:1.05rem;margin-bottom:12px}
.subscribe input{font:inherit;padding:11px 13px;border:1px solid var(--line-strong);border-radius:9px;
background:rgba(0,0,0,.25);color:#fff;width:60%;min-width:220px}
.subscribe input::placeholder{color:var(--faint)}
.subscribe button{font:inherit;font-weight:600;padding:11px 18px;border:0;border-radius:9px;
background:#fff;color:#000;cursor:pointer;margin-left:8px}
.subscribe button:hover{background:#e5e5e5}
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
<meta name="theme-color" content="#18181b">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
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
