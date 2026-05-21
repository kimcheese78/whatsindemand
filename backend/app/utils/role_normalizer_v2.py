"""Canonical-taxonomy-driven role normalizer.

Replacement for the regex/spaCy-heavy role_normalizer.py.

Pipeline:
  1. Clean + lowercase the raw title.
  2. Strip seniority prefixes (returned separately).
  3. De-level: strip parentheticals, employment-type suffixes, level numerals,
     trailing location/region tails.
  4. Look up the de-leveled form in aliases.yaml -> canonical_id.
  5. Fallback: progressive substring match against alias keys.
  6. If still no match: return ('Unknown', queued for manual review).

Returns the same dict shape as the legacy normalize_title() so callers don't
change.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Optional, Tuple

import yaml

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
CANONICAL_PATH = os.path.normpath(os.path.join(DATA_DIR, "canonical_roles.yaml"))
ALIASES_PATH = os.path.normpath(os.path.join(DATA_DIR, "aliases.yaml"))


@lru_cache(maxsize=1)
def _load_taxonomy() -> Tuple[dict, dict]:
    with open(CANONICAL_PATH) as f:
        canonical = yaml.safe_load(f)
    with open(ALIASES_PATH) as f:
        aliases = yaml.safe_load(f)
    return canonical, aliases


# ---------------------------------------------------------------------------
# Seniority extraction
# ---------------------------------------------------------------------------

_SENIORITY_MAP = [
    (r"\bdistinguished\b", "distinguished"),
    (r"\bprincipal\b", "principal"),
    (r"\bstaff\b", "staff"),
    (r"\bsr\b\.?|\bsenior\b", "senior"),
    (r"\blead\b", "lead"),
    (r"\bjr\b\.?|\bjunior\b", "junior"),
    (r"\bentry[- ]level\b|\bearly[- ]career\b|\bnew grad\b", "entry"),
    (r"\bintern(?:ship)?\b", "intern"),
    (r"\bmid[- ]level\b|\bintermediate\b", "mid"),
]


_LEAD_KEEP_PHRASES = ("tech lead", "team lead", "technical lead", "engineering lead",
                      "product lead", "design lead", "platform lead", "data lead")


def extract_seniority(title: str) -> Tuple[Optional[str], str]:
    """Return (seniority, title_with_seniority_stripped)."""
    s = title.lower()
    found = None
    for pat, level in _SENIORITY_MAP:
        # Don't strip "lead" if it's part of a role-noun phrase like
        # "tech lead, X" — that's the role, not a seniority modifier.
        if level == "lead" and any(p in s for p in _LEAD_KEEP_PHRASES):
            continue
        if re.search(pat, s):
            found = level
            s = re.sub(pat, " ", s)
            break  # most-specific wins, only strip one
    s = re.sub(r"\s+", " ", s).strip(" ,-")
    return found, s


# ---------------------------------------------------------------------------
# De-leveling normalization
# ---------------------------------------------------------------------------

_PAREN_TAIL = re.compile(r"\s*\([^)]*\)\s*$")
_LEVEL_SUFFIXES = re.compile(r"(?:\s+|[-,]\s*)(?:i{1,3}v?|iv|v|[1-5])\s*$", re.I)
_LOCATION_TAIL = re.compile(
    r"[,\-–—|]\s*(?:remote|hybrid|on[- ]?site|us|usa|emea|apac|na|"
    r"latam|europe|americas|global|north america|south america|"
    r"united states|united kingdom|uk|canada|india|australia|"
    r"japan|china|germany|france|spain|italy|brazil|mexico|"
    r"new york|nyc|sf|san francisco|la|los angeles|seattle|austin|boston|"
    r"london|berlin|paris|tokyo|singapore|amsterdam|dublin|toronto|"
    r"100% remote(?:\s*-\s*usa)?|"
    r"[a-z]{2}(?:\s*-\s*[a-z]{2,})?)\s*$",
    re.I,
)
# Strip trailing codenames / project tails after a dash:
# "- Monopoly GO!", "- Stargate", "- Frontier Collective", etc.
# Heuristic: if title still contains a recognizable role noun before the dash,
# everything after the last " - " or " – " or " — " is likely a project tail.
_DASH_TAIL = re.compile(
    r"\s+[-–—]\s+[a-z0-9&'!,\.\s/]+$", re.I
)
_ROLE_NOUNS_FOR_TAIL_STRIP = (
    "manager", "engineer", "analyst", "specialist", "coordinator", "associate",
    "lead", "director", "designer", "scientist", "developer", "architect",
    "consultant", "representative", "administrator", "technician", "supervisor",
    "officer", "head", "advisor", "agent", "writer", "editor", "researcher",
    "marketer", "buyer", "planner", "trainer", "recruiter", "controller",
    "accountant", "auditor", "counsel", "paralegal", "vp", "president",
    "executive", "artist", "producer", "strategist", "owner", "principal",
)
_EMPLOYMENT_PATTERNS = [
    r"\(remote\)", r"\(hybrid\)", r"\(on[- ]site\)", r"\(onsite\)",
    r"\(contract(?:or)?\)", r"\(full[- ]time\)", r"\(part[- ]time\)",
    r"\(work from home\)", r"\(wfh\)", r"\(temporary\)", r"\(temp\)",
    r"\(intern(?:ship)?\)", r"\(casual employee\)", r"\(full[- ]time contractor\)",
    r"\(ai[- ]native\)",
    r"-\s*sign[- ]on bonus available", r"sign[- ]on bonus",
    r"\bper diem\b",
]


def _delevel(title: str) -> str:
    s = title.strip()
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("–", "-").replace("—", "-")
    s = s.lower()
    for _ in range(3):
        new = _PAREN_TAIL.sub("", s).strip()
        if new == s:
            break
        s = new
    for pat in _EMPLOYMENT_PATTERNS:
        s = re.sub(pat, "", s, flags=re.I).strip()
    for _ in range(3):
        new = _LOCATION_TAIL.sub("", s).strip(" ,-")
        if new == s:
            break
        s = new
    s = _LEVEL_SUFFIXES.sub("", s).strip(" ,-")
    # Strip codename/project tail after the last " - " IF a role noun
    # appears before the dash (so "Lead Game Designer - Monopoly GO!"
    # collapses but "Customer Success" alone doesn't).
    for _ in range(3):
        m = _DASH_TAIL.search(s)
        if not m:
            break
        head = s[: m.start()].strip(" ,-")
        head_words = set(head.split())
        if any(noun in head_words for noun in _ROLE_NOUNS_FOR_TAIL_STRIP):
            s = head
        else:
            break
    s = re.sub(r"\s+", " ", s).strip(" ,-")
    return s


# ---------------------------------------------------------------------------
# Skip patterns
# ---------------------------------------------------------------------------

_SKIP_KEYWORDS = [
    # Talent pool / catchall listings
    "talent pool", "talent community", "join our talent", "talent network",
    "candidate pool", "oyster talent",
    # "Don't see a role" variants
    "don't see what you're looking for", "didn't see what you are looking for",
    "don't see your dream job", "don't see a role", "don't see the job",
    "don't see the perfect", "can't find a role",
    # General application variants
    "general application", "general apply", "general interest",
    "general resume submittal", "open application",
    # Engagement / community signups
    "interested in joining", "join our community", "introduce yourself",
    "register your interest", "sign up to our", "university talent network",
    # Program / fellowship catchalls
    "future opportunities", "future openings", "expression of interest",
    "early career program",
]


def _should_skip(title: str) -> bool:
    s = title.lower().replace("’", "'").replace("‘", "'")
    return any(kw in s for kw in _SKIP_KEYWORDS)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


_TITLE_PREFIX_PATTERNS = [
    # Comma-prefixed
    (re.compile(r"^manager,\s+(.+)$"), "{} manager"),
    (re.compile(r"^director,\s+(.+)$"), "{} director"),
    (re.compile(r"^director of\s+(.+)$"), "director of {}"),
    (re.compile(r"^head of\s+(.+)$"), "{} manager"),
    (re.compile(r"^head,\s+(.+)$"), "{} manager"),
    (re.compile(r"^(?:vp|svp|evp|gvp|avp)(?:,| of)?\s+(.+)$"), "{} director"),
    (re.compile(r"^(?:area\s+)?vice president(?:,| of)?\s+(.+)$"), "{} director"),
    (re.compile(r"^chief\s+(.+?)\s+officer$"), "{} director"),
    (re.compile(r"^team lead,?\s+(.+)$"), "{} manager"),
    (re.compile(r"^tech lead,?\s+(.+)$"), "{} engineer"),
    (re.compile(r"^supervisor,?\s+(.+)$"), "{} supervisor"),
    (re.compile(r"^associate,?\s+(.+)$"), "{} associate"),
    (re.compile(r"^specialist,?\s+(.+)$"), "{} specialist"),
    (re.compile(r"^coordinator,?\s+(.+)$"), "{} coordinator"),
    (re.compile(r"^analyst(?: i{1,3})?,?\s+(.+)$"), "{} analyst"),
    (re.compile(r"^engineer,?\s+(.+)$"), "{} engineer"),
    (re.compile(r"^designer,?\s+(.+)$"), "{} designer"),
    # Bare prefix without comma: "Manager X", "Director X"
    (re.compile(r"^manager\s+(.+)$"), "{} manager"),
    (re.compile(r"^director\s+(.+)$"), "{} director"),
    (re.compile(r"^supervisor\s+(.+)$"), "{} supervisor"),
]


def _lookup(deleveled: str) -> Optional[str]:
    """Return canonical_id, or None if no match."""
    _, aliases = _load_taxonomy()
    # 1. exact
    if deleveled in aliases:
        return aliases[deleveled]
    # 2. drop trailing comma-clause and try again ("foo, bar baz" -> "foo")
    if "," in deleveled:
        head = deleveled.split(",", 1)[0].strip()
        if head in aliases:
            return aliases[head]
    # 3. drop trailing dash-clause ("foo - bar" -> "foo")
    if " - " in deleveled:
        head = deleveled.split(" - ", 1)[0].strip()
        if head in aliases:
            return aliases[head]
    # 4. structural rewrites: "Manager, X" -> "X manager", etc.
    rewritten_candidate = None
    for pattern, template in _TITLE_PREFIX_PATTERNS:
        m = pattern.match(deleveled)
        if m:
            rewritten = template.format(m.group(1).strip())
            if rewritten in aliases:
                return aliases[rewritten]
            # Try also stripping comma-clause from rewritten
            if "," in rewritten:
                head = rewritten.split(",", 1)[0].strip()
                if head in aliases:
                    return aliases[head]
            rewritten_candidate = rewritten
            break
    # 5. trailing role-noun match. Try the deleveled form, the step-4
    # rewritten form, and a comma-stripped variant of each (drops trailing
    # team/scope like "Lead Full Stack Developer, Business Applications").
    targets = []
    for t in (deleveled, rewritten_candidate):
        if not t:
            continue
        targets.append(t)
        if "," in t:
            targets.append(t.split(",", 1)[0].strip())
    suffix_nouns = ("manager", "engineer", "analyst", "specialist", "coordinator",
                    "associate", "lead", "director", "designer", "scientist",
                    "developer", "architect", "consultant", "representative",
                    "administrator", "technician", "supervisor", "recruiter",
                    "writer", "editor", "researcher", "marketer", "buyer",
                    "planner", "trainer", "advisor", "agent", "officer")
    for target in targets:
        # exact lookup of comma-stripped form
        if target in aliases:
            return aliases[target]
        for suffix in suffix_nouns:
            if target.endswith(" " + suffix):
                words = target.split()
                for n in range(min(5, len(words)), 1, -1):
                    candidate = " ".join(words[-n:])
                    if candidate in aliases:
                        return aliases[candidate]
    # 6. substring fallback: longest alias key contained in deleveled,
    # ignoring junk (null-valued) aliases. Require multi-char keys to avoid
    # spurious 1-2 letter matches.
    best_key = None
    best_len = 0
    for key, val in aliases.items():
        if not key or val is None or len(key) < 6:
            continue
        if len(key) <= best_len:
            continue
        if key in deleveled:
            best_key = key
            best_len = len(key)
    if best_key is not None:
        return aliases[best_key]

    # 7. last-resort: match by trailing role-noun in deleveled OR rewritten.
    for target in (deleveled, rewritten_candidate):
        if not target:
            continue
        for suffix, default_canonical in _SUFFIX_DEFAULTS:
            if target.endswith(" " + suffix) or target == suffix:
                return default_canonical
    return None


# Last-resort suffix → default canonical_id mapping. Order matters: more
# specific multi-word suffixes first.
_SUFFIX_DEFAULTS = [
    ("software engineer", "software_engineer"),
    ("software developer", "software_engineer"),
    ("data engineer", "data_engineer"),
    ("data scientist", "data_scientist"),
    ("data analyst", "data_analyst"),
    ("ml engineer", "machine_learning_engineer"),
    ("ai engineer", "ai_engineer"),
    ("backend engineer", "backend_engineer"),
    ("frontend engineer", "frontend_engineer"),
    ("fullstack engineer", "fullstack_engineer"),
    ("full stack engineer", "fullstack_engineer"),
    ("mobile engineer", "mobile_engineer"),
    ("android engineer", "mobile_engineer"),
    ("ios engineer", "mobile_engineer"),
    ("firmware engineer", "mobile_engineer"),
    ("devops engineer", "devops_engineer"),
    ("security engineer", "security_engineer"),
    ("platform engineer", "platform_engineer"),
    ("infrastructure engineer", "infrastructure_engineer"),
    ("network engineer", "network_engineer"),
    ("systems engineer", "systems_engineer"),
    ("solutions engineer", "solutions_engineer"),
    ("solutions architect", "solutions_architect"),
    ("test engineer", "test_engineer"),
    ("qa engineer", "qa_engineer"),
    ("research engineer", "research_engineer"),
    ("research scientist", "research_scientist"),
    ("hardware engineer", "electrical_engineer"),
    ("mechanical engineer", "mechanical_engineer"),
    ("electrical engineer", "electrical_engineer"),
    ("manufacturing engineer", "manufacturing_engineer"),
    ("product engineer", "software_engineer"),
    ("product designer", "product_designer"),
    ("ux designer", "ux_designer"),
    ("ux researcher", "ux_researcher"),
    ("brand designer", "brand_designer"),
    ("graphic designer", "graphic_designer"),
    ("content designer", "content_designer"),
    ("game designer", "product_designer"),
    ("product manager", "product_manager"),
    ("program manager", "program_manager"),
    ("project manager", "project_manager"),
    ("engineering manager", "engineering_manager"),
    ("marketing manager", "marketing_manager"),
    ("sales manager", "sales_manager"),
    ("operations manager", "operations_manager"),
    ("finance manager", "finance_manager"),
    ("accounting manager", "accounting_manager"),
    ("payroll manager", "payroll_manager"),
    ("tax manager", "tax_manager"),
    ("contract manager", "contracts_manager"),
    ("contracts manager", "contracts_manager"),
    ("partner manager", "partner_manager"),
    ("account manager", "account_manager"),
    ("account executive", "account_executive"),
    ("customer success manager", "customer_success_manager"),
    ("technical writer", "technical_writer"),
    ("data analyst", "data_analyst"),
    ("financial analyst", "financial_analyst"),
    ("business analyst", "business_analyst"),
    ("treasury analyst", "treasury_analyst"),
    ("accountant", "accountant"),
    ("bookkeeper", "accountant"),
    ("controller", "controller"),
    ("auditor", "internal_auditor"),
    ("counsel", "legal_counsel"),
    ("paralegal", "paralegal"),
    ("recruiter", "recruiter"),
    ("sourcer", "talent_sourcer"),
    ("physician", "physician"),
    ("nurse practitioner", "nurse_practitioner"),
    ("physician assistant", "physician_assistant"),
    ("medical assistant", "medical_assistant"),
    ("therapist", "mental_health_therapist"),
    # Generic single-word fallbacks last
    ("engineer", "software_engineer"),
    ("developer", "software_engineer"),
    ("designer", "product_designer"),
    ("analyst", "business_analyst"),
    ("scientist", "data_scientist"),
    ("manager", "operations_manager"),
    ("director", "operations_manager"),
    ("specialist", "operations_manager"),
    ("coordinator", "administrative_assistant"),
    ("associate", "operations_manager"),
    ("administrator", "systems_administrator"),
    ("technician", "manufacturing_technician"),
    ("planner", "material_planner"),
    ("trainer", "technical_writer"),
    ("consultant", "solutions_consultant"),
    ("representative", "sales_representative"),
    ("supervisor", "operations_manager"),
    ("architect", "solutions_architect"),
    ("buyer", "senior_buyer"),
    ("lead", "operations_manager"),
    ("head", "operations_manager"),
    ("officer", "operations_manager"),
    ("partner", "partner_manager"),
    ("strategist", "business_analyst"),
    ("advisor", "solutions_consultant"),
    ("agent", "sales_representative"),
    ("clerk", "administrative_assistant"),
    # "assistant" alone is too broad — nursing/dental/vet assistants are healthcare,
    # not admin. Specific forms are handled via aliases.yaml instead.
    # ("assistant", "administrative_assistant"),  # removed: causes false matches
    ("operator", "manufacturing_technician"),
    ("editor", "technical_writer"),
    ("writer", "technical_writer"),
    ("producer", "program_manager"),
]


# ---------------------------------------------------------------------------
# Public API (compatible with legacy normalize_title)
# ---------------------------------------------------------------------------


def normalize_title(raw_title: str) -> dict:
    """Return {normalized_title, category, seniority_level, job_family, canonical_id}."""
    if not raw_title or not raw_title.strip():
        return _unknown(None)

    if _should_skip(raw_title):
        return _unknown(None)

    # First try lookup WITHOUT stripping seniority — handles cases where
    # words like "lead" or "principal" are part of the role name
    # (e.g. "Trade Advisory Lead", "Principal Software Engineer" — the
    # latter still resolves to software_engineer via substring fallback).
    deleveled_full = _delevel(raw_title)
    canonical_id = _lookup(deleveled_full) if deleveled_full else None

    seniority, without_seniority = extract_seniority(raw_title)

    # If no match yet, try after seniority strip
    if canonical_id is None:
        deleveled = _delevel(without_seniority)
        if deleveled:
            canonical_id = _lookup(deleveled)

    if canonical_id is None:
        return {
            "normalized_title": "Unknown",
            "category": "Unmapped",
            "seniority_level": seniority,
            "job_family": "Unmapped",
            "canonical_id": None,
        }

    canonical, _ = _load_taxonomy()
    role = canonical[canonical_id]
    return {
        "normalized_title": role["name"],
        "category": role["category"],
        "seniority_level": seniority,
        "job_family": role["job_family"],
        "canonical_id": canonical_id,
    }


def _unknown(seniority: Optional[str]) -> dict:
    return {
        "normalized_title": "Unknown",
        "category": "Skip",
        "seniority_level": seniority,
        "job_family": "Skip",
        "canonical_id": None,
    }
