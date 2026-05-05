"""Asks Claude for big-name companies we don't yet track and returns a
candidate list ready for the probe step. Probe + insert is handled by the
caller (reusing helpers from scripts/expand_coverage.py)."""

import json
import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a sourcing assistant for a job-market analytics product called WhatsInDemand. Your job is to suggest companies we should add to our scraper.

The scraper supports four ATS providers, in this priority order:
1. greenhouse (host: boards-api.greenhouse.io)
2. lever (host: api.lever.co)
3. ashby (host: api.ashbyhq.com)
4. workable (host: apply.workable.com)

For each company, provide your best guess of:
- name: official company name
- slug: the slug used in their ATS URL (e.g. "stripe" for boards.greenhouse.io/stripe). Lowercase, no spaces.
- ats: one of greenhouse / lever / ashby / workable
- industry: short label (e.g. "Fintech", "AI/ML", "Healthcare", "Consumer", "Enterprise SaaS")
- reason: one sentence on why this company matters

Hard rules:
- Do NOT suggest companies in the existing list provided.
- Prefer LARGE, well-known companies users will search for first (FAANG, top public tech, top private startups, top consulting/finance/retail). Only after big names are clearly covered should you fall back to filling industry gaps.
- If unsure of a slug, give your best guess — the caller will probe it.
- Return strict JSON only. No prose, no markdown fences."""


USER_PROMPT_TEMPLATE = """Suggest {n} new companies to add to our tracker.

Companies we already track (do not repeat):
{existing}

Industries we currently cover (with company counts, for context):
{industry_counts}

Return JSON of the form:
{{"candidates": [
  {{"name": "Stripe", "slug": "stripe", "ats": "greenhouse", "industry": "Fintech", "reason": "Top private fintech, large eng org, posts consistently."}},
  ...
]}}"""


def propose_candidates(
    existing_names: List[str],
    industry_counts: Dict[str, int],
    n: int = 20,
    model: str = "claude-haiku-4-5-20251001",
) -> List[Dict]:
    """Ask Claude for `n` candidate companies. Returns a list of dicts
    with keys: name, slug, ats, industry, reason. Empty list on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set; skipping candidate generation")
        return []

    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed")
        return []

    existing_list = "\n".join(f"- {name}" for name in sorted(existing_names))
    industry_list = "\n".join(
        f"- {ind}: {cnt}" for ind, cnt in sorted(industry_counts.items(), key=lambda kv: -kv[1])
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        n=n,
        existing=existing_list or "(none)",
        industry_counts=industry_list or "(none)",
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as e:
        logger.exception("Claude API call failed: %s", e)
        return []

    text = "".join(block.text for block in resp.content if block.type == "text").strip()

    # Strip accidental markdown fences if Claude added them.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude JSON: %s\nRaw: %s", e, text[:500])
        return []

    candidates = parsed.get("candidates", [])
    return _validate_candidates(candidates, existing_names)


def _validate_candidates(raw: List[Dict], existing_names: List[str]) -> List[Dict]:
    """Drop malformed entries and ones that match an existing name (case-insensitive)."""
    valid_atses = {"greenhouse", "lever", "ashby", "workable"}
    existing_lower = {n.lower() for n in existing_names}
    out = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = (c.get("name") or "").strip()
        slug = (c.get("slug") or "").strip().lower()
        ats = (c.get("ats") or "").strip().lower()
        if not name or not slug or ats not in valid_atses:
            continue
        if name.lower() in existing_lower:
            continue
        out.append({
            "name": name,
            "slug": slug,
            "ats": ats,
            "industry": (c.get("industry") or "Other").strip(),
            "reason": (c.get("reason") or "").strip(),
        })
    return out
