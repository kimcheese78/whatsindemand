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
    tags: list[str]
    related_roles: list[str]
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


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _parse(path: Path) -> "Post | None":
    try:
        fm = frontmatter.load(str(path))
    except ValueError as e:
        # A malformed date literal (e.g. `2026-13-45`) is rejected by
        # PyYAML's own timestamp construction at parse time, before we ever
        # see `meta['date']` — catch it here too, not just in _coerce_date.
        logger.warning('blog: %s has invalid front-matter — skipped (%s)', path.name, e)
        return None
    meta = fm.metadata
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        logger.warning('blog: %s missing required front-matter %s — skipped', path.name, missing)
        return None
    if meta.get('draft'):
        return None
    try:
        date = _coerce_date(meta['date'])
    except (ValueError, TypeError) as e:
        logger.warning('blog: %s has invalid date %r — skipped (%s)', path.name, meta.get('date'), e)
        return None
    if date > datetime.date.today():
        return None
    slug = meta.get('slug') or _DATE_PREFIX.sub('', path.stem)
    return Post(
        slug=slug,
        title=str(meta['title']),
        description=str(meta['description']),
        date=date,
        tags=_as_list(meta.get('tags')),
        related_roles=_as_list(meta.get('related_roles')),
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
