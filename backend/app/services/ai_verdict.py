"""Pure decision logic for the 'Will AI replace [role]?' pages.

No Flask, no DB — given a role's numbers, return an honest, plain-language
verdict. Unit-tested in tests/ai_outlook/test_verdict.py.
"""
import json
import os

LENS_PHRASE = "the roughly 3,300 fast-growing companies we track"

_BLS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bls_projections.json")
_BLS_TABLE = None


def _load_bls_table():
    global _BLS_TABLE
    if _BLS_TABLE is None:
        with open(_BLS_PATH, encoding="utf-8") as f:
            _BLS_TABLE = json.load(f)
    return _BLS_TABLE


def bls_for(soc_code, table=None):
    """Look up a BLS projection record by occupation code. Returns
    {'pct', 'period', 'employment_base'} or None."""
    if not soc_code:
        return None
    if table is None:
        table = _load_bls_table()
    return table.get(soc_code)

GROW_FLOOR = 5.0   # BLS 10-yr % change at/above this => job is growing
FLAT_FLOOR = -2.0  # between FLAT_FLOOR and GROW_FLOOR => roughly steady


def _ai_clause(role_plural: str, ai_pct: int) -> str:
    """One plain sentence about how many current openings ask for AI skills."""
    if ai_pct <= 0:
        return (f"Across {LENS_PHRASE}, almost no current {role_plural} openings "
                f"ask for AI skills yet.")
    return (f"Across {LENS_PHRASE}, {ai_pct}% of current {role_plural} openings "
            f"now ask for AI skills.")


def _period_tail(bls_period):
    """Turn '2024 to 2034' into '2034'; fall back to a plain phrase."""
    if not bls_period:
        return "the next ten years"
    return bls_period.split()[-1]


def decide_verdict(*, role_plural, ai_pct, total, bls_pct, bls_period=None):
    role_plural = role_plural.strip()

    if bls_pct is None:
        return {
            "stance": "adoption_only",
            "diverges": False,
            "headline": (f"Not yet — employers aren't cutting {role_plural}. "
                         f"They're asking them to use AI."),
            "detail": (f"There are {total:,} live {role_plural} openings right now. "
                       + _ai_clause(role_plural, ai_pct)
                       + " The work is changing, not going away."),
        }

    if bls_pct >= GROW_FLOOR:
        return {
            "stance": "no",
            "diverges": False,
            "headline": (f"No — {role_plural} aren't being replaced. The government "
                         f"expects this job to grow, and companies are still hiring."),
            "detail": (f"Official projections put {role_plural} employment up "
                       f"{bls_pct:.0f}% by {_period_tail(bls_period)}. "
                       + _ai_clause(role_plural, ai_pct)
                       + " The work is changing, not disappearing."),
        }

    if bls_pct >= FLAT_FLOOR:
        return {
            "stance": "unlikely",
            "diverges": False,
            "headline": (f"Probably not soon. The number of {role_plural} looks "
                         f"steady, but AI is taking over some of the day-to-day tasks."),
            "detail": (f"Official projections expect {role_plural} employment to stay "
                       f"about the same through {_period_tail(bls_period)}. "
                       + _ai_clause(role_plural, ai_pct)),
        }

    # bls_pct < FLAT_FLOOR: official decline, but the role is still being hired now.
    return {
        "stance": "contested",
        "diverges": True,
        "headline": (f"It's mixed. Official forecasts point down, but right now "
                     f"companies are still hiring {role_plural}."),
        "detail": (f"The government projects {role_plural} employment to fall "
                   f"{abs(bls_pct):.0f}% by {_period_tail(bls_period)}. Yet there are "
                   f"{total:,} live {role_plural} openings across {LENS_PHRASE}. "
                   + _ai_clause(role_plural, ai_pct)
                   + " Strong demand today and a long-term squeeze can both be true."),
    }
