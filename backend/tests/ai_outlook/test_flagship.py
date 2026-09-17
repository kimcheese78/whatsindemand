from app.services.ai_flagship import flagship_html_for


def test_returns_none_for_non_flagship():
    assert flagship_html_for("operations-manager") is None


def test_returns_html_for_flagship():
    html = flagship_html_for("software-engineer")
    assert html is not None
    assert "<" in html  # some markup
