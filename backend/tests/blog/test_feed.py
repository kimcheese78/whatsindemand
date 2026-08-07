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
