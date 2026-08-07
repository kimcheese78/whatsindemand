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
