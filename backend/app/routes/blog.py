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
