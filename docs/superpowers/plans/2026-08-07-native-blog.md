# Native Blog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native, server-rendered markdown blog at `whatsindemand.com/blog` that reuses the existing `public.py` SEO-page pattern, with tags, RSS, reserved AdSense slots, a Resend-backed newsletter, and sitemap integration.

**Architecture:** A new Flask blueprint (`app/routes/blog.py`) serves edge-cached HTML built from markdown files in `app/blog/posts/`. Post parsing/rendering lives in a DB-free `app/blog/` package (loader, theme, feed) so most logic is unit-testable without a database. Vercel rewrites proxy `/blog/*` to the Railway backend, exactly like `/r/*` today.

**Tech Stack:** Flask 3.0, SQLAlchemy 2.0 / Flask-Migrate (Alembic), `mistune` (markdown), `python-frontmatter` (front-matter), Resend (`app.services.email.send_email`), React SPA on Vercel.

## Global Constraints

- **DB is prod-only.** There is no local/test database. DB-touching code is verified by running Flask locally against the prod `DATABASE_URL` (per CLAUDE.md's DSN gotcha) and cleaning up test rows — never assume a local Postgres. Pure (DB-free) logic is unit-tested with pytest.
- **Server-rendered, no client JS for content.** Blog pages are HTML + inline `<style>` only. The only JS is the config-gated AdSense snippet.
- **Canonical host is `https://www.whatsindemand.com`** — reuse `WEB_URL`; do not hardcode a different host.
- **Edge cache header** for all blog GET pages: `public, max-age=86400, stale-while-revalidate=604800` — reuse `CACHE_HEADER`.
- **Never commit secrets.** No DSNs/keys in tracked files (recent incident — see `docs/superpowers/specs/`).
- **Blueprints register with NO url_prefix** for public pages (routes carry the full `/blog...` path), matching `public_bp`.
- **AdSense is config-gated** by env var `ADSENSE_CLIENT_ID`; nothing loads when it is unset.
- Frequent commits: one per task minimum.

---

## File Structure

**Create:**
- `backend/app/routes/_web.py` — shared web helpers (`_esc`, `_slugify`, `WEB_URL`, `CACHE_HEADER`) extracted from `public.py`.
- `backend/app/blog/__init__.py` — empty package marker.
- `backend/app/blog/loader.py` — `Post` dataclass, front-matter parsing/validation, markdown render, read-time, mtime cache, `load_posts()` / `get_post()`.
- `backend/app/blog/theme.py` — light reading-theme CSS, `render_page(...)` HTML shell, meta tags, `adsense_head()` / `ad_slot()`, list/related-roles fragments.
- `backend/app/blog/feed.py` — pure RSS builder and blog sitemap-URL builder.
- `backend/app/blog/posts/2026-08-07-welcome-to-the-whatsindemand-blog.md` — first real post.
- `backend/app/blog/drafts/.gitkeep` — reserve the drafts folder.
- `backend/tests/__init__.py`, `backend/tests/blog/__init__.py` — test packages.
- `backend/tests/blog/test_loader.py`, `test_theme.py`, `test_feed.py`, `test_routes.py` — pure/test-client tests.
- `backend/tests/blog/fixtures/` — sample `.md` files for loader tests.
- `frontend/public/ads.txt` — AdSense authorized-sellers file (placeholder until publisher ID known).

**Modify:**
- `backend/app/routes/public.py` — import helpers from `_web`; extend `sitemap()` with blog URLs.
- `backend/app/routes/blog.py` — new blueprint (created in Task 5).
- `backend/app/__init__.py` — register `blog_bp`.
- `backend/app/models.py` — add `NewsletterSubscriber`.
- `backend/requirements.txt` — add `mistune`, `python-frontmatter`, `pytest`.
- `frontend/vercel.json` — add `/blog` rewrites, fix stale `/Articles` redirect, extend CSP for AdSense.
- `frontend/src/App.js` — add a "Blog" nav link.

---

## Task 1: Dependencies + shared web helpers

Extract the small helper set from `public.py` so the blog reuses it instead of duplicating, and add the new libraries.

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/routes/_web.py`
- Modify: `backend/app/routes/public.py` (imports)
- Create: `backend/tests/__init__.py`, `backend/tests/blog/__init__.py`, `backend/tests/blog/test_web.py`

**Interfaces:**
- Produces: `_web.WEB_URL: str`, `_web.CACHE_HEADER: str`, `_web._esc(s) -> str`, `_web._slugify(title: str) -> str`.

- [ ] **Step 1: Add dependencies**

In `backend/requirements.txt` add these lines (anywhere; keep alphabetical-ish):

```
mistune==3.0.2
python-frontmatter==1.1.0
pytest==8.3.3
```

Install:

```bash
cd backend && source venv/bin/activate && pip install -r requirements.txt
```

Expected: `Successfully installed mistune-3.0.2 python-frontmatter-1.1.0 pytest-8.3.3` (or "already satisfied").

- [ ] **Step 2: Write the failing test**

Create `backend/tests/__init__.py` (empty), `backend/tests/blog/__init__.py` (empty), and `backend/tests/blog/test_web.py`:

```python
from app.routes._web import _esc, _slugify, WEB_URL, CACHE_HEADER


def test_esc_escapes_html():
    assert _esc('<b>a & "b"</b>') == '&lt;b&gt;a &amp; &quot;b&quot;&lt;/b&gt;'


def test_slugify_lowercases_and_hyphenates():
    assert _slugify('Data Engineer') == 'data-engineer'
    assert _slugify('R&D / Ops') == 'r-d-ops'


def test_constants():
    assert WEB_URL == 'https://www.whatsindemand.com'
    assert 'max-age=86400' in CACHE_HEADER
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_web.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.routes._web'`.

- [ ] **Step 4: Create `_web.py`**

Create `backend/app/routes/_web.py`:

```python
# backend/app/routes/_web.py
"""Shared helpers for server-rendered public pages (/r, /blog, sitemap)."""

WEB_URL = 'https://www.whatsindemand.com'
CACHE_HEADER = 'public, max-age=86400, stale-while-revalidate=604800'


def _esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def _slugify(title: str) -> str:
    return (title.lower().replace('/', ' ').replace('&', ' ')
            .replace('  ', ' ').strip().replace(' ', '-'))
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_web.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Point `public.py` at the shared helpers**

In `backend/app/routes/public.py`, replace the local `WEB_URL`/`CACHE_HEADER` constants and the `_slugify`/`_esc` function definitions with an import. At the top of the file (after the existing imports) add:

```python
from app.routes._web import WEB_URL, CACHE_HEADER, _esc, _slugify
```

Then delete the now-duplicate definitions in `public.py`: the `WEB_URL =` and `CACHE_HEADER =` lines, and the `def _slugify(...)` and `def _esc(...)` blocks. Leave `MIN_JOBS_FOR_PAGE`, `_PAGE_CSS`, and everything else untouched.

- [ ] **Step 7: Verify `/r/` pages still import and render**

```bash
cd backend && venv/bin/python -c "from app import create_app; print('ok import')"
```

Expected: `ok import` with no traceback (confirms `public.py` still resolves its names).

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/app/routes/_web.py backend/app/routes/public.py backend/tests/
git commit -m "refactor: extract shared web helpers into _web.py; add blog deps"
```

---

## Task 2: Post loader

Parse markdown posts with front-matter into `Post` objects, with validation, read-time, draft/future exclusion, and an mtime cache.

**Files:**
- Create: `backend/app/blog/__init__.py` (empty)
- Create: `backend/app/blog/loader.py`
- Create: `backend/tests/blog/fixtures/2026-08-07-sample.md`, `.../draft.md`, `.../2099-01-01-future.md`
- Create: `backend/tests/blog/test_loader.py`

**Interfaces:**
- Produces:
  - `Post` dataclass with fields: `slug:str, title:str, description:str, date:datetime.date, tags:list[str], related_roles:list[str], source:str, body_html:str, read_minutes:int`.
  - `load_posts(posts_dir: Path | None = None) -> list[Post]` — published posts, newest first.
  - `get_post(slug: str, posts_dir=None) -> Post | None`.
  - `posts_by_tag(tag: str, posts_dir=None) -> list[Post]`.

- [ ] **Step 1: Create fixtures**

Create `backend/tests/blog/fixtures/2026-08-07-sample.md`:

```markdown
---
title: Sample Post
description: A sample description.
date: 2026-08-07
tags: [salaries, data]
related_roles: [data-engineer]
---
# Hello

Some **body** text with enough words to read.
```

Create `backend/tests/blog/fixtures/draft.md`:

```markdown
---
title: A Draft
description: Not published.
date: 2026-08-01
draft: true
---
Body.
```

Create `backend/tests/blog/fixtures/2099-01-01-future.md`:

```markdown
---
title: Future Post
description: Scheduled.
date: 2099-01-01
---
Body.
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/blog/test_loader.py`:

```python
from pathlib import Path
import datetime
from app.blog.loader import load_posts, get_post, posts_by_tag

FIX = Path(__file__).parent / 'fixtures'


def test_loads_only_published_posts():
    posts = load_posts(FIX)
    slugs = [p.slug for p in posts]
    assert 'sample' in slugs
    assert 'draft' not in slugs          # draft: true excluded
    assert 'future' not in slugs         # future-dated excluded


def test_post_fields_parsed():
    p = get_post('sample', FIX)
    assert p.title == 'Sample Post'
    assert p.date == datetime.date(2026, 8, 7)
    assert p.tags == ['salaries', 'data']
    assert p.related_roles == ['data-engineer']
    assert '<strong>body</strong>' in p.body_html
    assert p.read_minutes >= 1
    assert p.source == 'human'


def test_slug_defaults_to_filename_without_date():
    assert get_post('sample', FIX).slug == 'sample'


def test_posts_by_tag_filters():
    assert [p.slug for p in posts_by_tag('salaries', FIX)] == ['sample']
    assert posts_by_tag('nonexistent', FIX) == []


def test_missing_slug_returns_none():
    assert get_post('nope', FIX) is None
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.blog.loader'`.

- [ ] **Step 4: Implement the loader**

Create `backend/app/blog/__init__.py` (empty). Create `backend/app/blog/loader.py`:

```python
# backend/app/blog/loader.py
"""Load markdown blog posts (front-matter + body) into Post objects."""

import datetime
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter
import mistune

logger = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / 'posts'
REQUIRED = ('title', 'description', 'date')
_DATE_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}-')

_render_md = mistune.create_markdown(plugins=['strikethrough', 'table', 'url'])

# path -> (mtime, Post|None)
_cache: dict[Path, tuple[float, "Post | None"]] = {}


@dataclass
class Post:
    slug: str
    title: str
    description: str
    date: datetime.date
    tags: list
    related_roles: list
    source: str
    body_html: str
    read_minutes: int


def _read_minutes(text: str) -> int:
    words = len(re.findall(r'\w+', text))
    return max(1, round(words / 200))


def _coerce_date(value) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def _parse(path: Path) -> "Post | None":
    fm = frontmatter.load(str(path))
    meta = fm.metadata
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        logger.warning('blog: %s missing required front-matter %s — skipped', path.name, missing)
        return None
    if meta.get('draft'):
        return None
    date = _coerce_date(meta['date'])
    if date > datetime.date.today():
        return None
    slug = meta.get('slug') or _DATE_PREFIX.sub('', path.stem)
    return Post(
        slug=slug,
        title=str(meta['title']),
        description=str(meta['description']),
        date=date,
        tags=list(meta.get('tags') or []),
        related_roles=list(meta.get('related_roles') or []),
        source=str(meta.get('source', 'human')),
        body_html=_render_md(fm.content),
        read_minutes=_read_minutes(fm.content),
    )


def _load_cached(path: Path) -> "Post | None":
    mtime = path.stat().st_mtime
    cached = _cache.get(path)
    if cached is None or cached[0] != mtime:
        _cache[path] = (mtime, _parse(path))
    return _cache[path][1]


def load_posts(posts_dir: Path | None = None) -> list[Post]:
    d = Path(posts_dir) if posts_dir else POSTS_DIR
    if not d.exists():
        return []
    posts = [p for p in (_load_cached(f) for f in d.glob('*.md')) if p is not None]
    posts.sort(key=lambda p: p.date, reverse=True)
    return posts


def get_post(slug: str, posts_dir: Path | None = None) -> "Post | None":
    for p in load_posts(posts_dir):
        if p.slug == slug:
            return p
    return None


def posts_by_tag(tag: str, posts_dir: Path | None = None) -> list[Post]:
    return [p for p in load_posts(posts_dir) if tag in p.tags]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_loader.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/blog/__init__.py backend/app/blog/loader.py backend/tests/blog/
git commit -m "feat: blog post loader (front-matter, markdown, draft/future filtering)"
```

---

## Task 3: Reading theme + page shell + AdSense slots

Produce the full HTML document (meta tags, light theme CSS, config-gated AdSense) and small presentational fragments.

**Files:**
- Create: `backend/app/blog/theme.py`
- Create: `backend/tests/blog/test_theme.py`

**Interfaces:**
- Consumes: `Post` from `loader`, `_web._esc`, `_web.WEB_URL`.
- Produces:
  - `render_page(*, title, description, canonical, body_html, noindex=False) -> str`
  - `ad_slot(name: str) -> str` — reserved container; injects the AdSense `<ins>` only when `ADSENSE_CLIENT_ID` is set.
  - `adsense_head() -> str` — the Auto Ads `<script>` when configured, else `''`.
  - `related_roles_html(slugs: list[str]) -> str`
  - `post_list_html(posts: list) -> str`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/blog/test_theme.py`:

```python
import os
from app.blog import theme


def test_render_page_has_meta_and_canonical():
    html = theme.render_page(
        title='T', description='D',
        canonical='https://www.whatsindemand.com/blog/x',
        body_html='<p>hi</p>',
    )
    assert '<title>T' in html
    assert '<meta name="description" content="D">' in html
    assert '<link rel="canonical" href="https://www.whatsindemand.com/blog/x">' in html
    assert '<p>hi</p>' in html
    assert 'noindex' not in html


def test_render_page_noindex():
    html = theme.render_page(title='T', description='D', canonical='c',
                             body_html='', noindex=True)
    assert 'name="robots" content="noindex"' in html


def test_ad_slot_empty_without_env(monkeypatch):
    monkeypatch.delenv('ADSENSE_CLIENT_ID', raising=False)
    assert theme.ad_slot('top').strip().startswith('<div')
    assert 'adsbygoogle' not in theme.ad_slot('top')
    assert theme.adsense_head() == ''


def test_ad_slot_active_with_env(monkeypatch):
    monkeypatch.setenv('ADSENSE_CLIENT_ID', 'ca-pub-123')
    assert 'adsbygoogle' in theme.ad_slot('top')
    assert 'ca-pub-123' in theme.adsense_head()


def test_related_roles_links():
    html = theme.related_roles_html(['data-engineer', 'ml-engineer'])
    assert '/r/data-engineer' in html
    assert '/r/ml-engineer' in html
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_theme.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.blog.theme'`.

- [ ] **Step 3: Implement the theme**

Create `backend/app/blog/theme.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_theme.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/blog/theme.py backend/tests/blog/test_theme.py
git commit -m "feat: blog reading theme, page shell, config-gated AdSense slots"
```

---

## Task 4: RSS feed + blog sitemap URLs

Pure builders for the RSS 2.0 feed and the list of blog URLs the sitemap needs.

**Files:**
- Create: `backend/app/blog/feed.py`
- Create: `backend/tests/blog/test_feed.py`

**Interfaces:**
- Consumes: `Post` list, `_web.WEB_URL`.
- Produces:
  - `render_rss(posts: list) -> str` — valid RSS 2.0 XML.
  - `blog_sitemap_urls(posts: list) -> list[str]` — `<url>...</url>` strings for `/blog`, each post, and each tag.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/blog/test_feed.py`:

```python
import datetime
from xml.dom import minidom
from app.blog.loader import Post
from app.blog.feed import render_rss, blog_sitemap_urls


def _post(slug='p', tags=None):
    return Post(slug=slug, title='T & U', description='D', date=datetime.date(2026, 8, 7),
                tags=tags or [], related_roles=[], source='human',
                body_html='<p>b</p>', read_minutes=1)


def test_rss_is_wellformed_xml():
    xml = render_rss([_post()])
    minidom.parseString(xml)  # raises if malformed
    assert '<rss version="2.0"' in xml
    assert 'https://www.whatsindemand.com/blog/p' in xml
    assert 'T &amp; U' in xml            # escaped title


def test_sitemap_urls_include_index_posts_tags():
    urls = blog_sitemap_urls([_post(slug='p', tags=['salaries'])])
    joined = ''.join(urls)
    assert 'https://www.whatsindemand.com/blog</loc>' in joined
    assert 'https://www.whatsindemand.com/blog/p</loc>' in joined
    assert 'https://www.whatsindemand.com/blog/tag/salaries</loc>' in joined
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_feed.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.blog.feed'`.

- [ ] **Step 3: Implement the feed builders**

Create `backend/app/blog/feed.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_feed.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/blog/feed.py backend/tests/blog/test_feed.py
git commit -m "feat: blog RSS feed and sitemap URL builders"
```

---

## Task 5: Blog routes + blueprint registration

Wire the loader/theme/feed into a Flask blueprint and register it. Content routes touch no DB, so they are testable with Flask's test client.

**Files:**
- Create: `backend/app/routes/blog.py`
- Modify: `backend/app/__init__.py`
- Create: `backend/tests/blog/test_routes.py`

**Interfaces:**
- Consumes: `loader.load_posts/get_post/posts_by_tag`, `theme.*`, `feed.render_rss`.
- Produces: `blog_bp` (Flask Blueprint) with routes `/blog`, `/blog/<slug>`, `/blog/tag/<tag>`, `/blog/rss.xml`. (Newsletter routes are added in Task 7.)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/blog/test_routes.py`:

```python
import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app('testing')
    app.config['TESTING'] = True
    return app.test_client()


def test_index_lists_posts(client):
    r = client.get('/blog')
    assert r.status_code == 200
    assert b'WhatsInDemand Blog' in r.data or b'Blog' in r.data


def test_missing_post_404(client):
    assert client.get('/blog/does-not-exist').status_code == 404


def test_rss_content_type(client):
    r = client.get('/blog/rss.xml')
    assert r.status_code == 200
    assert 'xml' in r.content_type
```

> Note: these routes never query the database, so no DB connection is needed even though `create_app` initializes SQLAlchemy.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_routes.py -v
```

Expected: FAIL — 404s for `/blog` (blueprint not registered yet).

- [ ] **Step 3: Implement the blueprint**

Create `backend/app/routes/blog.py`:

```python
# backend/app/routes/blog.py
"""Server-rendered blog at /blog (markdown files → HTML), edge-cached."""

from flask import Blueprint, Response

from app.routes._web import WEB_URL, CACHE_HEADER, _esc
from app.blog import loader, theme, feed

blog_bp = Blueprint('blog', __name__)


def _html(body: str) -> Response:
    return Response(body, mimetype='text/html', headers={'Cache-Control': CACHE_HEADER})


@blog_bp.route('/blog', methods=['GET'])
def index():
    posts = loader.load_posts()
    tags = sorted({t for p in posts for t in p.tags})
    chips = ''.join(f'<a href="{WEB_URL}/blog/tag/{_esc(t)}">{_esc(t)}</a>' for t in tags)
    body = (f'<h1>The WhatsInDemand Blog</h1>'
            f'<p class="meta">Hiring trends, skills, and career data from 3,300+ companies.</p>'
            f'<div class="chips">{chips}</div>'
            f'{theme.post_list_html(posts)}'
            f'{_subscribe_form()}'
            f'{_footer()}')
    return _html(theme.render_page(
        title='The WhatsInDemand Blog',
        description='Hiring trends, in-demand skills, and career data from 3,300+ companies.',
        canonical=f'{WEB_URL}/blog', body_html=body))


@blog_bp.route('/blog/<slug>', methods=['GET'])
def post(slug):
    p = loader.get_post(slug)
    if not p:
        return Response('<h1>Post not found</h1>', mimetype='text/html', status=404)
    body = (f'<h1>{_esc(p.title)}</h1>'
            f'<p class="meta">{p.date.strftime("%B %-d, %Y")} · {p.read_minutes} min read</p>'
            f'{theme.ad_slot("top")}'
            f'{p.body_html}'
            f'{theme.ad_slot("in-article")}'
            f'{theme.related_roles_html(p.related_roles)}'
            f'{_subscribe_form()}'
            f'{theme.ad_slot("footer")}'
            f'{_footer()}')
    return _html(theme.render_page(
        title=f'{p.title} — WhatsInDemand',
        description=p.description,
        canonical=f'{WEB_URL}/blog/{p.slug}', body_html=body))


@blog_bp.route('/blog/tag/<tag>', methods=['GET'])
def tag(tag):
    posts = loader.posts_by_tag(tag)
    body = (f'<h1>Posts tagged “{_esc(tag)}”</h1>'
            f'{theme.post_list_html(posts)}{_footer()}')
    return _html(theme.render_page(
        title=f'{tag} — WhatsInDemand Blog',
        description=f'Blog posts about {tag}.',
        canonical=f'{WEB_URL}/blog/tag/{tag}', body_html=body,
        noindex=not posts))


@blog_bp.route('/blog/rss.xml', methods=['GET'])
def rss():
    return Response(feed.render_rss(loader.load_posts()),
                    mimetype='application/rss+xml',
                    headers={'Cache-Control': CACHE_HEADER})


def _subscribe_form() -> str:
    return ('<div class="subscribe"><strong>Get the weekly hiring-trends digest</strong>'
            '<form method="post" action="/blog/subscribe">'
            '<p><input type="email" name="email" placeholder="you@email.com" required> '
            '<button type="submit">Subscribe</button></p></div>')


def _footer() -> str:
    return (f'<footer>© WhatsInDemand · <a href="{WEB_URL}">Dashboard</a> · '
            f'<a href="{WEB_URL}/blog/rss.xml">RSS</a></footer>')
```

- [ ] **Step 4: Register the blueprint**

In `backend/app/__init__.py`, directly below the `public_bp` registration (the block ending at line ~105), add:

```python
    # Server-rendered blog (/blog, /blog/<slug>, /blog/tag/<tag>, /blog/rss.xml)
    from app.routes.blog import blog_bp
    app.register_blueprint(blog_bp)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_routes.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Manual smoke test**

```bash
cd backend && FLASK_CONFIG=development venv/bin/python -c "
from app import create_app
c = create_app().test_client()
print('index', c.get('/blog').status_code)
print('rss', c.get('/blog/rss.xml').status_code)
"
```

Expected: `index 200` / `rss 200`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/blog.py backend/app/__init__.py backend/tests/blog/test_routes.py
git commit -m "feat: blog blueprint (index, post, tag, rss) + registration"
```

---

## Task 6: Sitemap integration

Add blog URLs to the existing `/sitemap.xml` so there is one sitemap.

**Files:**
- Modify: `backend/app/routes/public.py` (`sitemap()`)

**Interfaces:**
- Consumes: `feed.blog_sitemap_urls`, `loader.load_posts`.

- [ ] **Step 1: Extend `sitemap()`**

In `backend/app/routes/public.py`, add near the top imports:

```python
from app.blog import loader as blog_loader
from app.blog.feed import blog_sitemap_urls
```

Then in the `sitemap()` function, after the existing `urls += [...]` role block and before the `xml = (...)` line, insert:

```python
    urls += blog_sitemap_urls(blog_loader.load_posts())
```

- [ ] **Step 2: Verify the blog-URL portion (pure)**

The URL builder is already covered by `tests/blog/test_feed.py::test_sitemap_urls_include_index_posts_tags`. Re-run to confirm nothing regressed:

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_feed.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Verify import wiring**

```bash
cd backend && venv/bin/python -c "from app.routes import public; print('sitemap import ok')"
```

Expected: `sitemap import ok`.

> Full `/sitemap.xml` output also queries `Role` (needs the prod DB) and is verified end-to-end in Task 10 against prod.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/public.py
git commit -m "feat: include blog URLs in sitemap.xml"
```

---

## Task 7: Newsletter (model + migration + subscribe/unsubscribe)

Add the subscriber table and the two DB-backed routes. Pure helpers are unit-tested; the DB flow is verified against prod (no local DB exists).

**Files:**
- Modify: `backend/app/models.py`
- Create: migration in `backend/migrations/versions/` (autogenerated)
- Modify: `backend/app/routes/blog.py`
- Create: `backend/tests/blog/test_newsletter.py`

**Interfaces:**
- Consumes: `app.services.email.send_email(to, subject, html, text) -> bool`, `models.db`, `models.NewsletterSubscriber`.
- Produces: `NewsletterSubscriber` model; routes `POST /blog/subscribe`, `GET /blog/unsubscribe/<token>`; helper `_valid_email(s) -> bool`; `_welcome_email(sub) -> tuple[str, str]` (html, text).

- [ ] **Step 1: Add the model**

In `backend/app/models.py`, append:

```python
class NewsletterSubscriber(db.Model):
    """Blog newsletter subscribers (single opt-in, token-based unsubscribe)."""
    __tablename__ = 'newsletter_subscribers'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    unsubscribed_at = db.Column(db.DateTime)
```

- [ ] **Step 2: Write the failing test (pure helpers)**

Create `backend/tests/blog/test_newsletter.py`:

```python
from app.routes.blog import _valid_email


def test_valid_email():
    assert _valid_email('a@b.com')
    assert not _valid_email('nope')
    assert not _valid_email('')
    assert not _valid_email('a@b')
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_newsletter.py -v
```

Expected: FAIL — `ImportError: cannot import name '_valid_email'`.

- [ ] **Step 4: Implement routes + helpers**

In `backend/app/routes/blog.py`, add imports at the top:

```python
import re
import secrets
from datetime import datetime
from flask import request
from app.models import db, NewsletterSubscriber
from app.services.email import send_email
```

Add near the other helpers:

```python
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _valid_email(s: str) -> bool:
    return bool(_EMAIL_RE.match((s or '').strip()))


def _welcome_email(sub) -> tuple:
    url = f'{WEB_URL}/blog/unsubscribe/{sub.token}'
    html = (f'<p>You are subscribed to the WhatsInDemand hiring-trends digest.</p>'
            f'<p><a href="{url}">Unsubscribe</a></p>')
    text = f'You are subscribed to the WhatsInDemand digest.\nUnsubscribe: {url}'
    return html, text


def _notice(msg: str, status: int = 200) -> Response:
    body = f'<h1>{_esc(msg)}</h1><p class="meta"><a href="{WEB_URL}/blog">← Back to the blog</a></p>'
    return Response(theme.render_page(title=msg, description=msg,
                    canonical=f'{WEB_URL}/blog', body_html=body, noindex=True),
                    mimetype='text/html', status=status)
```

Add the two routes:

```python
@blog_bp.route('/blog/subscribe', methods=['POST'])
def subscribe():
    email = (request.form.get('email') or '').strip().lower()
    if not _valid_email(email):
        return _notice('Please enter a valid email address.', 400)
    sub = NewsletterSubscriber.query.filter_by(email=email).first()
    if sub is None:
        sub = NewsletterSubscriber(email=email, token=secrets.token_urlsafe(32))
        db.session.add(sub)
        db.session.commit()
        html, text = _welcome_email(sub)
        send_email(email, 'Welcome to the WhatsInDemand digest', html, text)
    elif sub.unsubscribed_at is not None:
        sub.unsubscribed_at = None
        db.session.commit()
    return _notice('You are subscribed. Check your inbox.')


@blog_bp.route('/blog/unsubscribe/<token>', methods=['GET'])
def unsubscribe(token):
    sub = NewsletterSubscriber.query.filter_by(token=token).first()
    if sub and sub.unsubscribed_at is None:
        sub.unsubscribed_at = datetime.utcnow()
        db.session.commit()
    return _notice('You have been unsubscribed.')
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && venv/bin/python -m pytest tests/blog/test_newsletter.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Generate and apply the migration (against prod DB)**

Per CLAUDE.md's DSN gotcha, provide the prod `DATABASE_URL` inline (get it from Railway → Variables; do NOT paste it into any tracked file):

```bash
cd backend
DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/flask db migrate -m "add newsletter_subscribers"
```

Open the new file in `backend/migrations/versions/` and confirm `upgrade()` contains `op.create_table('newsletter_subscribers', ...)` with `email`, `token`, `created_at`, `unsubscribed_at` and unique constraints on `email` and `token`. Then apply:

```bash
DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/flask db upgrade
```

Expected: `Running upgrade ... add newsletter_subscribers`.

- [ ] **Step 7: Manually verify the subscribe/unsubscribe flow (prod DB, clean up after)**

```bash
cd backend
DATABASE_URL='<prod-dsn>' PYTHONPATH=. venv/bin/python -c "
from app import create_app
c = create_app().test_client()
print('subscribe', c.post('/blog/subscribe', data={'email':'test+blog@whatsindemand.com'}).status_code)
from app.models import db, NewsletterSubscriber
app = create_app()
with app.app_context():
    s = NewsletterSubscriber.query.filter_by(email='test+blog@whatsindemand.com').first()
    print('row created, token len', len(s.token))
    print('unsub', c.get('/blog/unsubscribe/'+s.token).status_code)
    db.session.delete(NewsletterSubscriber.query.filter_by(email='test+blog@whatsindemand.com').first())
    db.session.commit()
    print('cleaned up')
"
```

Expected: `subscribe 200`, `row created...`, `unsub 200`, `cleaned up`. (No real email is sent unless `RESEND_API_KEY` is set locally.)

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/app/routes/blog.py backend/migrations/versions/ backend/tests/blog/test_newsletter.py
git commit -m "feat: blog newsletter signup + unsubscribe (Resend, single opt-in)"
```

---

## Task 8: Vercel rewrites, ads.txt, and CSP

Route `/blog/*` to the backend, remove the soon-dead `/Articles` redirect, pre-authorize AdSense in the CSP, and add `ads.txt`.

**Files:**
- Modify: `frontend/vercel.json`
- Create: `frontend/public/ads.txt`

- [ ] **Step 1: Add blog rewrites and fix the stale redirect**

In `frontend/vercel.json`:

Replace the `redirects` block (which currently points `/Articles/*` at the soon-deleted `blog.whatsindemand.com`) with:

```json
  "redirects": [
    { "source": "/Articles/:slug*", "destination": "/blog", "permanent": true }
  ],
```

In `rewrites`, add these two entries **before** the existing `/r/` and catch-all entries (order matters — the catch-all `/(.*)` must stay last):

```json
    { "source": "/blog", "destination": "https://whatsindemand-production.up.railway.app/blog" },
    { "source": "/blog/:path*", "destination": "https://whatsindemand-production.up.railway.app/blog/:path*" },
```

- [ ] **Step 2: Pre-authorize AdSense in the CSP**

In `frontend/vercel.json`, in the `Content-Security-Policy` header value, extend these directives (append the domains; keep existing entries):

- `script-src` … add `https://pagead2.googlesyndication.com https://googleads.g.doubleclick.net`
- `img-src` … add `https://pagead2.googlesyndication.com` (it already allows `https:` so this is optional but explicit)
- add a new directive `frame-src` value already exists (`https://accounts.google.com`) → append `https://googleads.g.doubleclick.net https://tpc.googlesyndication.com`
- `connect-src` … add `https://pagead2.googlesyndication.com`

> These only *permit* AdSense; nothing loads until `ADSENSE_CLIENT_ID` is set on the backend. Doing it now means activation is just: set the env var + fill `ads.txt`.

- [ ] **Step 3: Add ads.txt placeholder**

Create `frontend/public/ads.txt`:

```
# Fill in after AdSense approval, then redeploy:
# google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
```

- [ ] **Step 4: Validate JSON**

```bash
cd frontend && node -e "JSON.parse(require('fs').readFileSync('vercel.json','utf8')); console.log('vercel.json valid')"
```

Expected: `vercel.json valid`.

- [ ] **Step 5: Commit**

```bash
git add frontend/vercel.json frontend/public/ads.txt
git commit -m "feat: proxy /blog to backend, fix stale Articles redirect, pre-authorize AdSense CSP + ads.txt"
```

---

## Task 9: Blog nav link in the app

Add a "Blog" link so users can reach `/blog` from the SPA. Because `/blog` is served by the backend (via rewrite), use a plain anchor, **not** a react-router `<Link>`.

**Files:**
- Modify: `frontend/src/App.js`

- [ ] **Step 1: Locate the primary nav**

```bash
cd frontend && grep -n "About\|Contact\|footer\|<nav\|header" src/App.js | head -20
```

Use the results to find the header/footer nav where links like "About"/"Contact" render.

- [ ] **Step 2: Add the link**

Next to the existing nav links (matching their JSX/styling), add:

```jsx
<a href="/blog">Blog</a>
```

Use a plain `<a href="/blog">` (full-page navigation to the server-rendered blog), styled to match the sibling links. Add it in both the header and footer if both exist.

- [ ] **Step 3: Verify the build compiles**

```bash
cd frontend && npm run build
```

Expected: `Compiled successfully` (warnings are fine).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.js
git commit -m "feat: add Blog link to app nav"
```

---

## Task 10: Seed post + end-to-end verification

Ship one real post and verify the whole thing against prod.

**Files:**
- Create: `backend/app/blog/posts/2026-08-07-welcome-to-the-whatsindemand-blog.md`
- Create: `backend/app/blog/drafts/.gitkeep`

- [ ] **Step 1: Write the first post**

Create `backend/app/blog/posts/2026-08-07-welcome-to-the-whatsindemand-blog.md`:

```markdown
---
title: What 3,300 Companies Are Actually Hiring For
description: We track live job postings at 3,300+ fast-growing companies. Here is what the hiring data says about the skills that matter right now.
date: 2026-08-07
tags: [hiring-trends, skills]
related_roles: [data-engineer, software-engineer, product-manager]
source: human
---
WhatsInDemand reads live job postings from 3,300+ fast-growing companies and
turns them into demand signals: which skills show up most, which roles are
growing, and what employers actually ask for.

## Why postings beat opinion

Surveys tell you what people *say* matters. Postings tell you what companies are
*paying* for this week. That is the data behind every page here.

## Start with your target role

Pick a role and see its live skill demand, top employers, and remote share on
its role page — for example [Data Engineer](https://www.whatsindemand.com/r/data-engineer)
or [Product Manager](https://www.whatsindemand.com/r/product-manager).

More posts soon — subscribe below to get the weekly digest.
```

- [ ] **Step 2: Reserve the drafts folder**

```bash
mkdir -p backend/app/blog/drafts && touch backend/app/blog/drafts/.gitkeep
```

- [ ] **Step 3: Render the post locally**

```bash
cd backend && venv/bin/python -c "
from app import create_app
c = create_app().test_client()
r = c.get('/blog/welcome-to-the-whatsindemand-blog')
print('status', r.status_code)
assert r.status_code == 200
assert b'canonical' in r.data and b'data-engineer' in r.data
print('post renders with canonical + related role link')
print('index has post:', b'3,300' in c.get('/blog').data)
"
```

Expected: `status 200`, the two assertions pass, `index has post: True`.

- [ ] **Step 4: Run the full blog test suite**

```bash
cd backend && venv/bin/python -m pytest tests/blog/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit and push the branch**

```bash
git add backend/app/blog/posts/ backend/app/blog/drafts/.gitkeep
git commit -m "content: first blog post + reserve drafts folder"
git push -u origin feat/native-blog
```

- [ ] **Step 6: Post-deploy verification (after merge to main → Railway + Vercel deploy)**

Once `feat/native-blog` is merged to `main` and both services deploy:

```bash
curl -sI https://www.whatsindemand.com/blog | head -5
curl -s https://www.whatsindemand.com/blog/welcome-to-the-whatsindemand-blog | grep -o '<title>[^<]*' | head -1
curl -s https://www.whatsindemand.com/sitemap.xml | grep -c '/blog'
curl -sI https://www.whatsindemand.com/ads.txt | head -1
```

Expected: `/blog` returns `200`; the post title prints; sitemap contains `/blog` URLs (count ≥ 2); `ads.txt` returns `200`.

- [ ] **Step 7: Deprecate the old subdomain (manual, outside the repo)**

Delete `blog.whatsindemand.com` on Hostinger and its DNS record. The `/Articles/*` redirect now points at `/blog`, so no dead links remain on the main domain.

---

## Post-plan open items (not blocking the build)

- **AdSense activation:** after publishing 3–5 posts and getting approved, set `ADSENSE_CLIENT_ID` on the Railway backend service and fill `frontend/public/ads.txt` with your `pub-…` line, then redeploy.
- **Nav placement:** confirm final position of the Blog link (header vs footer vs both).
