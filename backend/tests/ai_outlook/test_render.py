from app.services.ai_verdict import decide_verdict, LENS_PHRASE
from app.services.ai_render import (
    render_role_outlook_page, render_outlook_index, ai_sitemap_urls,
)

DATA = {
    "total": 17151, "company_count": 1200, "ai_pct": 34, "remote_pct": 28,
    "skills": [
        {"name": "Python", "subcategory": "Programming Languages", "pct": 61},
        {"name": "LLMs", "subcategory": "AI & Machine Learning", "pct": 22},
    ],
    "companies": [{"name": "Stripe", "count": 40}, {"name": "Datadog", "count": 33}],
}


def _page(total=17151, bls=None, flagship=None):
    data = dict(DATA, total=total)
    verdict = decide_verdict(role_plural="software engineers", ai_pct=data["ai_pct"],
                             total=total, bls_pct=(bls or {}).get("pct"),
                             bls_period=(bls or {}).get("period"))
    return render_role_outlook_page(
        role_singular="Software Engineer", role_plural="software engineers",
        slug="software-engineer", month="September 2026", data=data,
        verdict=verdict, bls=bls, related=[("Data Scientist", "data-scientist")],
        min_jobs=30, flagship_html=flagship,
    )


def test_page_has_h1_and_canonical():
    html = _page()
    assert "<h1>Will AI replace software engineers?</h1>" in html
    assert '<link rel="canonical" href="https://www.whatsindemand.com/ai/will-ai-replace-software-engineer">' in html


def test_page_shows_verdict_and_lens():
    html = _page()
    assert "aren't cutting" in html.lower() or "not yet" in html.lower()
    assert LENS_PHRASE in html


def test_page_noindex_below_threshold():
    assert '<meta name="robots" content="noindex">' in _page(total=12)
    assert '<meta name="robots" content="noindex">' not in _page(total=200)


def test_page_has_breadcrumb_and_article_schema_no_faq():
    html = _page()
    assert '"@type": "BreadcrumbList"' in html
    assert '"@type": "Article"' in html
    assert "FAQPage" not in html


def test_page_renders_bls_section_only_when_present():
    assert "government" not in _page(bls=None).lower()
    withbls = _page(bls={"pct": 15.0, "period": "2024 to 2034"})
    assert "15%" in withbls


def test_flagship_html_injected_when_given():
    html = _page(flagship="<p id='flag'>hand written</p>")
    assert "<p id='flag'>hand written</p>" in html


def test_index_lists_items_and_links():
    html = render_outlook_index(items=[("software engineers", "software-engineer", 17151)])
    assert "/ai/will-ai-replace-software-engineer" in html
    assert "17,151" in html


def test_sitemap_urls_shape():
    urls = ai_sitemap_urls([("software-engineer", "2026-09-17")], today="2026-09-17")
    assert urls[0].startswith("<url><loc>https://www.whatsindemand.com/ai/</loc>")
    assert any("/ai/will-ai-replace-software-engineer</loc>" in u for u in urls)
