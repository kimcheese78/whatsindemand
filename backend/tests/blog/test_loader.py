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
    # 'scalar-tags' fixture also carries the 'salaries' tag (bare scalar) —
    # see test_scalar_tags_not_shredded. Compare as a set: order isn't the
    # point here, membership is.
    assert {p.slug for p in posts_by_tag('salaries', FIX)} == {'sample', 'scalar-tags'}
    assert posts_by_tag('nonexistent', FIX) == []


def test_missing_slug_returns_none():
    assert get_post('nope', FIX) is None


def test_bad_date_excluded():
    # date: 2026-13-45 is malformed; the post must be skipped, not crash
    # the whole listing.
    slugs = [p.slug for p in load_posts(FIX)]
    assert 'bad-date' not in slugs


def test_missing_title_excluded():
    # front-matter has description + date but no title — required-field
    # skip path.
    slugs = [p.slug for p in load_posts(FIX)]
    assert 'missing-title' not in slugs


def test_scalar_tags_not_shredded():
    p = get_post('scalar-tags', FIX)
    assert p is not None
    assert p.tags == ['salaries']
