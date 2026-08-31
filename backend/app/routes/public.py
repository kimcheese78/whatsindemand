# backend/app/routes/public.py
"""
Public, server-rendered role pages for search engines and link sharing.

The React app is client-rendered and therefore nearly invisible to crawlers;
these pages are the indexable face of the dataset. Served through Vercel
rewrites at whatsindemand.com/r/<slug>, /r/, and /sitemap.xml.

Design constraints:
- Fast queries only (counts + group-bys on active jobs). The dashboard's
  cohort-locked trend math is deliberately NOT computed here.
- No JS, inline CSS only, one canonical URL per role.
- Cache-Control: public — Vercel's edge caches these for a day.
"""
import json
from datetime import datetime

from flask import Blueprint, Response, request
from sqlalchemy import func

from app.models import db, Job, JobSkill, Skill, Role, Company
from app.routes._web import WEB_URL, CACHE_HEADER, _esc, _slugify
from app.blog import loader as blog_loader
from app.blog.feed import blog_sitemap_urls

public_bp = Blueprint('public', __name__)

MIN_JOBS_FOR_PAGE = 30          # below this the page is thin content — noindex


def _find_role_by_slug(slug: str):
    name = slug.replace('-', ' ')
    return Role.query.filter(
        func.lower(Role.normalized_title) == func.lower(name)
    ).first()


_PAGE_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
background:#0a0a0a;color:#f0f0f0;margin:0;padding:0;line-height:1.6}
main{max-width:720px;margin:0 auto;padding:48px 24px}
a{color:#7dd3fc;text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:2.2rem;margin:0 0 4px;letter-spacing:-0.02em}
h2{font-size:1.05rem;margin:36px 0 12px;color:#aaa;text-transform:uppercase;letter-spacing:0.08em}
.sub{color:#888;margin:0 0 24px}
.stat-row{display:flex;gap:32px;flex-wrap:wrap;margin:24px 0;padding:20px;background:#141414;border:1px solid #2a2a2a}
.stat b{display:block;font-size:1.6rem}
.stat span{font-size:0.8rem;color:#888}
table{width:100%;border-collapse:collapse}
td,th{padding:8px 4px;border-bottom:1px solid #222;text-align:left;font-size:0.95rem}
th{color:#888;font-weight:500;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em}
.bar{height:6px;background:#2a2a2a;min-width:120px}
.bar i{display:block;height:6px;background:#f0f0f0}
.cta{display:inline-block;margin:32px 0;padding:14px 24px;background:#fff;color:#000;font-weight:600}
.cta:hover{text-decoration:none;opacity:.9}
footer{color:#666;font-size:0.8rem;margin-top:48px;border-top:1px solid #222;padding-top:16px}
.num{font-variant-numeric:tabular-nums}
"""


def _role_page_data(role):
    """The handful of fast aggregates a public page needs."""
    base = db.session.query(Job.id).filter(Job.role_id == role.id, Job.is_active == True)
    job_ids = [j for (j,) in base.all()]
    total = len(job_ids)
    if total == 0:
        return None

    company_count = db.session.query(
        func.count(func.distinct(Job.company_id))
    ).filter(Job.id.in_(job_ids)).scalar() or 0

    skill_rows = db.session.query(
        Skill.name, Skill.subcategory, func.count(JobSkill.id)
    ).join(JobSkill, Skill.id == JobSkill.skill_id).filter(
        JobSkill.job_id.in_(job_ids), Skill.is_verified == True
    ).group_by(Skill.id).order_by(func.count(JobSkill.id).desc()).limit(12).all()

    company_rows = db.session.query(
        Company.name, func.count(Job.id)
    ).join(Job, Job.company_id == Company.id).filter(
        Job.id.in_(job_ids)
    ).group_by(Company.id).order_by(func.count(Job.id).desc()).limit(6).all()

    ai_count = db.session.query(
        func.count(func.distinct(JobSkill.job_id))
    ).join(Skill, JobSkill.skill_id == Skill.id).filter(
        JobSkill.job_id.in_(job_ids),
        Skill.subcategory == 'AI & Machine Learning',
        Skill.is_verified == True,
    ).scalar() or 0

    remote_count = db.session.query(func.count(Job.id)).filter(
        Job.id.in_(job_ids), Job.location_is_remote == True
    ).scalar() or 0

    return {
        'total': total,
        'company_count': company_count,
        'skills': [
            {'name': n, 'subcategory': sub, 'pct': round(c / total * 100)}
            for n, sub, c in skill_rows
        ],
        'companies': [{'name': n, 'count': c} for n, c in company_rows],
        'ai_pct': round(ai_count / total * 100),
        'remote_pct': round(remote_count / total * 100),
    }


@public_bp.route('/r/<role_slug>', methods=['GET'])
def public_role_page(role_slug):
    role = _find_role_by_slug(role_slug)
    if not role:
        return Response('<h1>Role not found</h1>', mimetype='text/html', status=404)

    canonical_slug = _slugify(role.normalized_title)
    if role_slug != canonical_slug:
        return Response(status=301, headers={'Location': f'/r/{canonical_slug}'})

    d = _role_page_data(role)
    if not d:
        return Response('<h1>No active postings for this role</h1>',
                        mimetype='text/html', status=404)

    title = role.normalized_title
    month = datetime.utcnow().strftime('%B %Y')
    page_title = f"{title}: skills in demand, {month} — WhatsInDemand"
    description = (
        f"{d['ai_pct']}% of {title} postings now ask for AI skills. "
        f"Live demand data from {d['total']:,} active postings at "
        f"{d['company_count']:,} fast-growing companies: top skills, top employers, remote share."
    )
    canonical = f"{WEB_URL}/r/{canonical_slug}"
    noindex = d['total'] < MIN_JOBS_FOR_PAGE

    breadcrumb_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "WhatsInDemand",
             "item": f"{WEB_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Roles",
             "item": f"{WEB_URL}/r/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": canonical},
        ],
    })

    skills_rows_html = ''.join(
        f"<tr><td>{_esc(s['name'])}</td>"
        f"<td class='num'>{s['pct']}%</td>"
        f"<td><div class='bar'><i style='width:{min(s['pct'], 100)}%'></i></div></td></tr>"
        for s in d['skills']
    )
    companies_html = ''.join(
        f"<tr><td>{_esc(c['name'])}</td><td class='num'>{c['count']}</td></tr>"
        for c in d['companies']
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(page_title)}</title>
<meta name="description" content="{_esc(description)}">
<link rel="canonical" href="{canonical}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:title" content="{_esc(page_title)}">
<meta property="og:description" content="{_esc(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{breadcrumb_ld}</script>
<style>{_PAGE_CSS}</style>
</head>
<body>
<main>
  <p class="sub"><a href="{WEB_URL}">WhatsInDemand</a> / roles</p>
  <h1>{_esc(title)}</h1>
  <p class="sub">What {d['company_count']:,} fast-growing companies ask for — updated {month}</p>

  <div class="stat-row">
    <div class="stat"><b class="num">{d['total']:,}</b><span>active postings</span></div>
    <div class="stat"><b class="num">{d['ai_pct']}%</b><span>ask for AI skills</span></div>
    <div class="stat"><b class="num">{d['remote_pct']}%</b><span>remote</span></div>
    <div class="stat"><b class="num">{d['company_count']:,}</b><span>companies hiring</span></div>
  </div>

  <h2>Most-demanded skills</h2>
  <table>
    <tr><th>Skill</th><th>% of postings</th><th></th></tr>
    {skills_rows_html}
  </table>

  <h2>Top employers hiring now</h2>
  <table>
    <tr><th>Company</th><th>Open roles</th></tr>
    {companies_html}
  </table>

  <a class="cta" href="{WEB_URL}">See the live dashboard — free →</a>

  <footer>
    Data from live job postings at 3,300+ companies, refreshed weekly.
    Skill tags come from a curated taxonomy of 5,700+ verified skills.
    <br>© WhatsInDemand
  </footer>
</main>
</body></html>"""

    return Response(html, mimetype='text/html',
                    headers={'Cache-Control': CACHE_HEADER})


@public_bp.route('/r/', methods=['GET'])
def public_role_index():
    roles = Role.query.filter(
        Role.total_active_jobs >= MIN_JOBS_FOR_PAGE
    ).order_by(Role.total_active_jobs.desc()).all()

    items = ''.join(
        f"<li><a href='/r/{_slugify(r.normalized_title)}'>{_esc(r.normalized_title)}</a> "
        f"<span class='num' style='color:#888'>({r.total_active_jobs:,} postings)</span></li>"
        for r in roles
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Roles tracked — WhatsInDemand</title>
<meta name="description" content="Live skill-demand pages for {len(roles)} roles, from job postings at 3,300+ fast-growing companies.">
<link rel="canonical" href="{WEB_URL}/r/">
<style>{_PAGE_CSS}li{{margin:6px 0}}</style></head>
<body><main>
<p class="sub"><a href="{WEB_URL}">WhatsInDemand</a></p>
<h1>Roles we track</h1>
<p class="sub">Live demand pages, refreshed weekly</p>
<ul>{items}</ul>
</main></body></html>"""
    return Response(html, mimetype='text/html',
                    headers={'Cache-Control': CACHE_HEADER})


@public_bp.route('/sitemap.xml', methods=['GET'])
def sitemap():
    roles = Role.query.filter(Role.total_active_jobs >= MIN_JOBS_FOR_PAGE).all()
    today = datetime.utcnow().strftime('%Y-%m-%d')
    urls = [f"<url><loc>{WEB_URL}/r/</loc><lastmod>{today}</lastmod></url>"]
    urls += [
        f"<url><loc>{WEB_URL}/r/{_slugify(r.normalized_title)}</loc>"
        f"<lastmod>{today}</lastmod><changefreq>weekly</changefreq></url>"
        for r in roles
    ]
    urls += blog_sitemap_urls(blog_loader.load_posts())
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + ''.join(urls) + '</urlset>')
    return Response(xml, mimetype='application/xml',
                    headers={'Cache-Control': CACHE_HEADER})
