"""Title -> seniority_level inference.

Single source of truth used by all ATS parsers and the backfill script.
Rules are checked top to bottom; first match wins.

Labels:
    intern, entry, junior, associate, mid, senior, lead,
    staff, senior-staff, principal, director, distinguished

Notable conventions:
    - "Level II" / "Engineer 2" -> mid  (not entry)
    - Director / VP / Chief / Head of -> director  (not principal)
    - Principal / Distinguished / Fellow / Founding -> principal (IC)
    - Bare "Associate" -> associate  (not entry)
    - "Senior Associate" -> senior  (senior check runs first)
"""
import re
from typing import Optional

# Ordered (regex, label). First match wins.
_RULES = [
    # Intern first — short and unambiguous
    (r'\b(intern|internship|co[- ]?op)\b', 'intern'),

    # Executive / senior leadership (put before principal because titles like
    # "VP of Principal Engineering" would otherwise be misclassified).
    (r'\b(director|vp|svp|evp|chief|c[tfmoprs]o|ciso|head of|founding)\b', 'director'),

    # IC top tier
    (r'\bdistinguished\b', 'distinguished'),
    (r'\b(principal|fellow)\b', 'principal'),

    # Staff family
    (r'\b(senior|sr\.?)\s+staff\b', 'senior-staff'),
    (r'\bstaff\b', 'staff'),

    # Senior (also Level III / "Engineer 3")
    (r'\b(senior|sr\.?)\b', 'senior'),
    (r'\biii\b', 'senior'),
    (r'\blevel\s*3\b', 'senior'),
    (r'\bengineer\s*3\b', 'senior'),

    # Lead (team/tech/engineering lead or bare "Lead")
    (r'\blead\b', 'lead'),

    # Mid (Level II / "Engineer 2")
    (r'\bii\b', 'mid'),
    (r'\blevel\s*2\b', 'mid'),
    (r'\bengineer\s*2\b', 'mid'),
    (r'\bmid[- ]?level\b', 'mid'),

    # Entry-level signals
    (r'\b(entry[- ]level|new\s*grad|early\s*career|apprentice|graduate)\b', 'entry'),
    (r'\bengineer\s*(i|1)\b', 'entry'),
    (r'\blevel\s*(i|1)\b', 'entry'),

    # Junior
    (r'\b(junior|jr\.?)\b', 'junior'),

    # Associate (bare, since Senior/Sr. already caught above)
    (r'\bassociate\b', 'associate'),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), label) for pat, label in _RULES]


def infer_seniority(title: Optional[str]) -> str:
    """Return a seniority label for a job title. Defaults to 'mid'."""
    if not title:
        return 'mid'
    t = title.lower()
    for pattern, label in _COMPILED:
        if pattern.search(t):
            return label
    return 'mid'
