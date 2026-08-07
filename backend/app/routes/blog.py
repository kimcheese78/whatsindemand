# backend/app/routes/blog.py
"""Server-rendered blog at /blog (markdown files → HTML), edge-cached."""

import re
import secrets
from datetime import datetime

from flask import Blueprint, Response, request

from app.routes._web import WEB_URL, _esc
from app.blog import loader, theme, feed
from app.models import db, NewsletterSubscriber
from app.services.email import send_email

blog_bp = Blueprint('blog', __name__)

# Blog HTML changes on redeploy and on new/edited posts, so browsers must
# revalidate (max-age=0) rather than hold a day-old copy; the CDN edge caches
# briefly (s-maxage) and serves stale while it revalidates in the background.
BLOG_CACHE = 'public, max-age=0, s-maxage=300, stale-while-revalidate=604800'


def _html(body: str) -> Response:
    return Response(body, mimetype='text/html', headers={'Cache-Control': BLOG_CACHE})


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
                    headers={'Cache-Control': BLOG_CACHE})


def _subscribe_form() -> str:
    return ('<div class="subscribe"><strong>Get the weekly hiring-trends digest</strong>'
            '<form method="post" action="/blog/subscribe">'
            '<p><input type="email" name="email" placeholder="you@email.com" required> '
            '<button type="submit">Subscribe</button></p></div>')


def _footer() -> str:
    return (f'<footer>© WhatsInDemand · <a href="{WEB_URL}">Dashboard</a> · '
            f'<a href="{WEB_URL}/blog/rss.xml">RSS</a></footer>')


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
