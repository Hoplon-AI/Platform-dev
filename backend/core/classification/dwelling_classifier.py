"""
Deterministic dwelling classification for mixed portfolios.

Normalises free-text SoV property types (and EPC built_form as a NULL-only
fallback) into a fixed dwelling_form vocabulary, and derives whether a fire
risk assessment is required for a given asset.

Deliberately NOT LLM-driven — same principle as _normalise_rag_status() in the
FRA/FRAEW processors: classification that feeds underwriter-facing logic must
be reproducible. Keep the keyword table in sync with the backfill CASE in
database/migrations/030_dwelling_form_standalone.sql.
"""

from __future__ import annotations

# Fixed vocabulary for silver.properties.dwelling_form
DWELLING_FORMS = frozenset([
    "house", "bungalow", "flat", "maisonette", "sheltered",
    "commercial", "mixed_use", "garage", "infrastructure", "other",
])

# Ordered keyword table — first match wins, so more specific forms come first
# (bungalow before house, maisonette/tenement before flat).
_KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("bungalow",       ("bungalow",)),
    ("maisonette",     ("maisonette",)),
    ("house",          ("shared house", "house", "detached", "terrace", "semi")),
    ("sheltered",      ("sheltered",)),
    ("garage",         ("garage",)),
    ("mixed_use",      ("mixed",)),
    ("commercial",     ("retail", "shop", "office", "commercial", "industrial",
                        "community")),
    ("infrastructure", ("drainage", "services", "organisation")),
    ("flat",           ("flat", "apartment", "studio", "tenement", "deck access",
                        "main door", "multiple residential", "bedsit")),
]

# Forms that are single-household dwellings when standalone — no common parts,
# so the Fire Safety Order 2005 / Fire (Scotland) Act FRA duty does not apply.
# Sheltered housing and anything with shared internal areas always requires one.
_NO_FRA_WHEN_STANDALONE = frozenset(["house", "bungalow"])

# Forms that are not dwellings at all (never counted as insurable units in
# dwelling analytics, never FRA-rated as residential).
NON_DWELLING_FORMS = frozenset(["garage", "infrastructure", "commercial"])


def classify_dwelling_form(property_type: str | None,
                           built_form: str | None = None) -> str | None:
    """Map free-text property_type to the fixed dwelling_form vocabulary.

    built_form (EPC) is only consulted when property_type yields nothing —
    SoV-priority rule.  Returns None when there is no signal at all.
    """
    for source in (property_type, built_form):
        if not source or not str(source).strip():
            continue
        text = str(source).strip().lower()
        for form, keywords in _KEYWORD_RULES:
            if any(kw in text for kw in keywords):
                return form
        return "other"  # had text, matched nothing — classified, not unknown
    return None


def derive_is_standalone(dwelling_form: str | None,
                         block_reference: str | None) -> bool | None:
    """Provisional standalone flag at SoV ingest time.

    Block detection (enrichment_worker) finalises this later; here we only
    claim what the SoV itself supports:
      - any block_reference        → in a block (False)
      - house/bungalow, no block   → standalone (True)
      - anything else              → unknown (None) until block detection runs
    """
    if block_reference and str(block_reference).strip():
        return False
    if dwelling_form in _NO_FRA_WHEN_STANDALONE:
        return True
    return None


def derive_fra_requirement(dwelling_form: str | None,
                           is_standalone: bool | None) -> str:
    """'required' | 'not_required' | 'unknown' for a single asset.

    Only a standalone single-household house/bungalow is exempt: FRAs apply to
    the common parts of multi-occupied buildings, which those don't have.
    "not_required" is a compliant state, not missing data.
    """
    if dwelling_form in NON_DWELLING_FORMS:
        return "not_required"
    if dwelling_form in _NO_FRA_WHEN_STANDALONE and is_standalone:
        return "not_required"
    if dwelling_form is None or is_standalone is None:
        return "unknown"
    return "required"
