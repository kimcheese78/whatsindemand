"""Loads hand-written flagship essays injected into /ai/ pages.

Flagship roles get an extra editorial block on top of the data. The essays
live as HTML partials in app/content/ai_flagships/<slug>.html and must pass
the plain-language voice gate (see the spec). Reviewed by a human before ship.
"""
import os

_DIR = os.path.join(os.path.dirname(__file__), "..", "content", "ai_flagships")
_FLAGSHIPS = {"software-engineer", "data-scientist", "accountant"}


def flagship_html_for(slug):
    if slug not in _FLAGSHIPS:
        return None
    path = os.path.join(_DIR, f"{slug}.html")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()
