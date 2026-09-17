"""Pure HTML builders for the 'Will AI replace [role]?' pages.

No Flask, no DB. Takes plain dicts, returns strings. The route layer
(app/routes/ai_outlook.py) fetches data and calls these. Unit-tested in
tests/ai_outlook/test_render.py.
"""
import json

from app.routes._web import WEB_URL, _esc, _slugify  # pure helpers, safe to import
from app.services.ai_verdict import LENS_PHRASE, plural

_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
background:#0a0a0a;color:#f0f0f0;margin:0;padding:0;line-height:1.6}
main{max-width:720px;margin:0 auto;padding:48px 24px}
a{color:#7dd3fc;text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:2.1rem;margin:0 0 8px;letter-spacing:-0.02em}
h2{font-size:1.05rem;margin:36px 0 12px;color:#aaa;text-transform:uppercase;letter-spacing:0.08em}
.sub{color:#888;margin:0 0 24px}
.verdict{font-size:1.25rem;color:#fff;background:#141414;border:1px solid #2a2a2a;
padding:20px 22px;margin:24px 0;border-left:3px solid #7dd3fc}
.verdict p{margin:10px 0 0;font-size:1rem;color:#ccc}
.stat-row{display:flex;gap:32px;flex-wrap:wrap;margin:24px 0;padding:20px;background:#141414;border:1px solid #2a2a2a}
.stat b{display:block;font-size:1.6rem}.stat span{font-size:0.8rem;color:#888}
table{width:100%;border-collapse:collapse}
td,th{padding:8px 4px;border-bottom:1px solid #222;text-align:left;font-size:0.95rem}
th{color:#888;font-weight:500;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em}
.cta{display:inline-block;margin:32px 0;padding:14px 24px;background:#fff;color:#000;font-weight:600}
.cta:hover{text-decoration:none;opacity:.9}
footer{color:#666;font-size:0.8rem;margin-top:48px;border-top:1px solid #222;padding-top:16px}
.num{font-variant-numeric:tabular-nums}
.related{list-style:none;padding:0;margin:12px 0 0}.related li{margin:5px 0}
"""


def _canonical(slug):
    return f"{WEB_URL}/ai/will-ai-replace-{slug}"


def render_role_outlook_page(*, role_singular, role_plural, slug, month, data,
                             verdict, bls, related, min_jobs, flagship_html=None):
    canonical = _canonical(slug)
    noindex = data["total"] < min_jobs
    title = (f"Will AI replace {role_plural}? What the hiring data says, "
             f"{month} — WhatsInDemand")
    # Single-escaped in the template below; keep the raw text plain here.
    description = f"{verdict['headline']} {verdict['detail']}"[:200]

    breadcrumb_ld = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "WhatsInDemand", "item": f"{WEB_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Will AI replace…", "item": f"{WEB_URL}/ai/"},
            {"@type": "ListItem", "position": 3, "name": f"Will AI replace {role_plural}?", "item": canonical},
        ],
    })
    article_ld = json.dumps({
        "@context": "https://schema.org", "@type": "Article",
        "headline": f"Will AI replace {role_plural}?",
        "about": role_singular, "url": canonical,
        "author": {"@type": "Organization", "name": "WhatsInDemand", "url": f"{WEB_URL}/"},
        "publisher": {"@type": "Organization", "name": "WhatsInDemand", "url": f"{WEB_URL}/"},
        "isAccessibleForFree": True,
    })

    # BLS section (only when present)
    bls_html = ""
    if bls:
        bls_html = (
            f"<h2>The official outlook</h2>"
            f"<p>The U.S. Bureau of Labor Statistics expects {_esc(role_plural)} employment "
            f"to change {bls['pct']:+.0f}% over {_esc(bls['period'])}. "
            f"<a href='https://www.bls.gov/emp/' rel='nofollow'>Source: BLS Employment Projections</a>.</p>"
        )

    # Skills split: AI/ML tasks vs the rest
    ai_skills = [s for s in data["skills"] if s["subcategory"] == "AI & Machine Learning"]
    other_skills = [s for s in data["skills"] if s["subcategory"] != "AI & Machine Learning"][:6]
    changing = ""
    if ai_skills:
        names = ", ".join(_esc(s["name"]) for s in ai_skills[:4])
        changing = (f"<p>AI shows up directly in these openings: {names}. "
                    f"That is the part of the job changing fastest.</p>")
    still_human = ""
    if other_skills:
        names = ", ".join(_esc(s["name"]) for s in other_skills)
        still_human = (f"<p>Employers still ask most for: {names} — "
                       f"the parts of the work people are hired to own.</p>")

    companies_html = "".join(
        f"<tr><td>{_esc(c['name'])}</td><td class='num'>{c['count']}</td></tr>"
        for c in data["companies"]
    )
    related_html = "".join(
        f"<li><a href='/ai/will-ai-replace-{_slugify(name)}'>Will AI replace {_esc(plural(name))}?</a></li>"
        for name, _ in related
    )

    flagship_block = flagship_html or ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="{_esc(description)}">
<link rel="canonical" href="{canonical}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:title" content="{_esc('Will AI replace ' + role_plural + '?')}">
<meta property="og:description" content="{_esc(verdict['headline'])}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{WEB_URL}/og-image.png?v=3">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{breadcrumb_ld}</script>
<script type="application/ld+json">{article_ld}</script>
<style>{_CSS}</style>
</head>
<body>
<main>
  <p class="sub"><a href="{WEB_URL}">WhatsInDemand</a> / <a href="{WEB_URL}/ai/">will AI replace…</a></p>
  <h1>Will AI replace {_esc(role_plural)}?</h1>
  <p class="sub">Based on live job postings — updated {month}</p>

  <div class="verdict">{_esc(verdict['headline'])}
    <p>{_esc(verdict['detail'])}</p>
  </div>

  <div class="stat-row">
    <div class="stat"><b class="num">{data['total']:,}</b><span>live openings</span></div>
    <div class="stat"><b class="num">{data['ai_pct']}%</b><span>ask for AI skills</span></div>
    <div class="stat"><b class="num">{data['remote_pct']}%</b><span>remote</span></div>
    <div class="stat"><b class="num">{data['company_count']:,}</b><span>companies hiring</span></div>
  </div>

  {bls_html}

  <h2>What AI is actually changing</h2>
  {changing}
  {still_human}

  {flagship_block}

  <h2>Who's hiring right now</h2>
  <table><tr><th>Company</th><th>Open roles</th></tr>{companies_html}</table>

  <p style="margin-top:28px"><a href="{WEB_URL}/r/{slug}">See the full {_esc(role_singular)} data page →</a></p>

  <h2>Related</h2>
  <ul class="related">{related_html}</ul>

  <a class="cta" href="{WEB_URL}">See the live dashboard — free →</a>

  <footer>
    Numbers come from live job postings at {LENS_PHRASE}, refreshed weekly.
    Official projections are from the U.S. Bureau of Labor Statistics.
    <br>© WhatsInDemand
  </footer>
</main>
</body></html>"""


def render_outlook_index(*, items):
    lis = "".join(
        f"<li><a href='/ai/will-ai-replace-{slug}'>Will AI replace {_esc(role_plural)}?</a> "
        f"<span class='num' style='color:#888'>({total:,} openings)</span></li>"
        for role_plural, slug, total in items
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Will AI replace your job? — WhatsInDemand</title>
<meta name="description" content="Honest, data-backed answers to 'Will AI replace [job]?' for {len(items)} roles, from live job postings.">
<link rel="canonical" href="{WEB_URL}/ai/">
<style>{_CSS}li{{margin:6px 0}}</style></head>
<body><main>
<p class="sub"><a href="{WEB_URL}">WhatsInDemand</a></p>
<h1>Will AI replace your job?</h1>
<p class="sub">Straight answers from live hiring data — updated weekly</p>
<ul>{lis}</ul>
</main></body></html>"""


def ai_sitemap_urls(rows, today):
    """rows: list of (slug, lastmod). Returns list of <url> strings incl. the hub."""
    out = [f"<url><loc>{WEB_URL}/ai/</loc><lastmod>{today}</lastmod></url>"]
    out += [
        f"<url><loc>{WEB_URL}/ai/will-ai-replace-{slug}</loc>"
        f"<lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq></url>"
        for slug, lastmod in rows
    ]
    return out
