from app.routes._web import _esc, _slugify, WEB_URL, CACHE_HEADER


def test_esc_escapes_html():
    assert _esc('<b>a & "b"</b>') == '&lt;b&gt;a &amp; &quot;b&quot;&lt;/b&gt;'


def test_slugify_lowercases_and_hyphenates():
    assert _slugify('Data Engineer') == 'data-engineer'
    assert _slugify('R&D / Ops') == 'r-d-ops'


def test_constants():
    assert WEB_URL == 'https://www.whatsindemand.com'
    assert 'max-age=86400' in CACHE_HEADER
