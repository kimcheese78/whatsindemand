"""Server-rendered 'Will AI replace [role]?' pages. Thin composer over
pure logic in app/services/ai_verdict.py and app/services/ai_render.py.
Served via Vercel rewrite at /ai/*."""
from datetime import datetime

from flask import Blueprint, Response

from app.models import Role
from app.routes._web import WEB_URL, CACHE_HEADER, _slugify
from app.routes.public import (
    _find_role_by_slug, _role_page_data, _related_roles, MIN_JOBS_FOR_PAGE,
)
from app.services.ai_verdict import decide_verdict, bls_for, plural
from app.services.ai_render import render_role_outlook_page, render_outlook_index
from app.services.ai_flagship import flagship_html_for

ai_outlook_bp = Blueprint("ai_outlook", __name__)


@ai_outlook_bp.route("/ai/will-ai-replace-<role_slug>", methods=["GET"])
def ai_role_page(role_slug):
    role = _find_role_by_slug(role_slug)
    if not role:
        return Response("<h1>Role not found</h1>", mimetype="text/html", status=404)

    canonical_slug = _slugify(role.normalized_title)
    if role_slug != canonical_slug:
        return Response(status=301,
                        headers={"Location": f"/ai/will-ai-replace-{canonical_slug}"})

    data = _role_page_data(role)
    if not data:
        return Response("<h1>No active postings for this role</h1>",
                        mimetype="text/html", status=404)

    role_plural = plural(role.normalized_title)
    bls_rec = bls_for(role.bls_soc_code)
    verdict = decide_verdict(
        role_plural=role_plural, ai_pct=data["ai_pct"], total=data["total"],
        bls_pct=(bls_rec or {}).get("pct"),
        bls_period=(bls_rec or {}).get("period"),
    )
    related = [(r.normalized_title, _slugify(r.normalized_title))
               for r in _related_roles(role)]

    html = render_role_outlook_page(
        role_singular=role.normalized_title, role_plural=role_plural,
        slug=canonical_slug, month=datetime.utcnow().strftime("%B %Y"),
        data=data, verdict=verdict, bls=bls_rec, related=related,
        min_jobs=MIN_JOBS_FOR_PAGE, flagship_html=flagship_html_for(canonical_slug),
    )
    return Response(html, mimetype="text/html", headers={"Cache-Control": CACHE_HEADER})


@ai_outlook_bp.route("/ai/", methods=["GET"])
def ai_index():
    roles = Role.query.filter(
        Role.total_active_jobs >= MIN_JOBS_FOR_PAGE
    ).order_by(Role.total_active_jobs.desc()).all()
    items = [(plural(r.normalized_title), _slugify(r.normalized_title),
              r.total_active_jobs) for r in roles]
    return Response(render_outlook_index(items=items), mimetype="text/html",
                    headers={"Cache-Control": CACHE_HEADER})


def ai_sitemap_rows():
    """(slug, lastmod) for every indexable role — consumed by public.sitemap."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    roles = Role.query.filter(Role.total_active_jobs >= MIN_JOBS_FOR_PAGE).all()
    return [(_slugify(r.normalized_title), today) for r in roles]
