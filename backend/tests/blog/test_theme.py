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
