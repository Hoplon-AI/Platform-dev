"""
backend/workers/extraction_common.py

Shared utilities for LLM document extraction (FRA + FRAEW processors):

  - Type-coercion helpers (_to_str, _to_bool, _to_float, _to_date) used by
    Pydantic field validators in both processors.
  - Validation-warning harvesting: validators record every repair/null/skip
    event into a warnings list passed via Pydantic's validation context, so
    data-quality problems feed the confidence score instead of vanishing
    into debug logs.
  - Composite confidence: extraction_confidence is computed in Python as
    min(LLM self-report, critical-field coverage, 1 - repair penalty).
    The LLM self-report alone is poorly calibrated; the composite is
    bounded by verifiable signals.

Warning dict shape (stored as JSONB in silver.fra_features /
silver.fraew_features .validation_warnings):

  {"field": str, "raw": str|None, "reason": str, "weight": float}

weight is the confidence penalty for that warning (default 0.05;
dropped list items use 0.10 — losing an action item is worse than
nulling one scalar).
"""

import logging
import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Penalty weights
WARN_WEIGHT_DEFAULT = 0.05   # one scalar field repaired/nulled
WARN_WEIGHT_DROPPED = 0.10   # a list item (action, finding, wall type) discarded
MAX_REPAIR_PENALTY  = 0.5    # penalty cap — warnings alone never floor confidence below 0.5


# ──────────────────────────────────────────────────────────────────────
# Type coercion helpers
# ──────────────────────────────────────────────────────────────────────

_NULL_WORDS = frozenset({
    "null", "none", "n/a", "unknown", "tbc", "tbd",
    "not stated", "not applicable", "not available",
    "not provided", "not assessed", "",
})


def _to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in _NULL_WORDS:
        return None
    return s


def _to_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1", "present", "installed", "provided", "fitted"):
            return True
        if v in ("false", "no", "0", "not present", "not installed", "none", "n/a"):
            return False
    return None


def _to_float(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in ("null", "n/a", "unknown", "tbc", "tbd", "none"):
            return None
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
        s_stripped = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
        for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y",
                    "%Y/%m/%d", "%Y.%m.%d", "%d.%m.%Y",
                    "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
            try:
                return datetime.strptime(s_stripped if s_stripped != s else s, fmt).date()
            except ValueError:
                continue
        logger.warning("Could not parse date: %r", value)
    return None


def _date_to_str(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


# ──────────────────────────────────────────────────────────────────────
# Validation-warning harvesting
# ──────────────────────────────────────────────────────────────────────

def make_warning(
    field: str,
    raw: Any,
    reason: str,
    weight: float = WARN_WEIGHT_DEFAULT,
) -> dict:
    """Build one JSON-safe warning entry. Raw value truncated to 120 chars."""
    raw_str = None
    if raw is not None:
        raw_str = str(raw)
        if len(raw_str) > 120:
            raw_str = raw_str[:117] + "..."
    return {"field": field, "raw": raw_str, "reason": reason, "weight": weight}


def ctx_warn(
    context: Optional[dict],
    field: str,
    raw: Any,
    reason: str,
    weight: float = WARN_WEIGHT_DEFAULT,
) -> None:
    """
    Append a warning to the list in a Pydantic validation context.
    No-op when the model is validated without a context (e.g. constructed
    directly in tests or fallback paths) — validation still succeeds.
    """
    if context is None:
        return
    warnings = context.get("warnings")
    if warnings is None:
        return
    warnings.append(make_warning(field, raw, reason, weight))


# ──────────────────────────────────────────────────────────────────────
# Composite confidence
# ──────────────────────────────────────────────────────────────────────

def coverage_score(critical_values: list) -> float:
    """
    Fraction of critical fields that came back populated.
    False is a real answer (system explicitly absent) and counts as present;
    None, empty string and empty list count as missing.
    """
    if not critical_values:
        return 1.0
    present = sum(
        1 for v in critical_values
        if v is not None and v != "" and v != []
    )
    return present / len(critical_values)


def composite_confidence(
    llm_self_report: float,
    coverage: float,
    warnings: list[dict],
) -> float:
    """
    min(LLM self-report, critical-field coverage) - repair penalty,
    clamped to [0, 1]. Self-report and coverage are ceilings; the penalty
    is subtracted so every warning ALWAYS lowers the score — a hallucinated
    citation must reduce confidence even when the self-report is modest.
    """
    penalty = min(
        MAX_REPAIR_PENALTY,
        sum(w.get("weight", WARN_WEIGHT_DEFAULT) for w in warnings),
    )
    score = min(llm_self_report, coverage) - penalty
    return round(max(0.0, min(1.0, score)), 3)


# ──────────────────────────────────────────────────────────────────────
# Citations — grounding each extracted value in the source document
# ──────────────────────────────────────────────────────────────────────
#
# The LLM returns, per critical field, a pointer to its evidence:
#   {"pg": <[Page N] number>, "q": "<first 6-8 words of source sentence>", "c": "H|M|L"}
# Python then verifies the quote actually appears on that page (exact match
# after whitespace normalisation, fuzzy >= 0.85 fallback, neighbour pages
# for off-by-one page refs) and expands it to the full source sentence.
# An unverifiable quote is a hallucination signal: it becomes a validation
# warning and a confidence penalty. The quote is deliberately short — a
# pointer, not a transcript — to keep output-token cost near zero.

_PAGE_MARKER_RE = re.compile(r"\[Page (\d+)\]")
FUZZY_MATCH_THRESHOLD = 0.85
SNIPPET_MAX_CHARS = 320


class Citation(BaseModel):
    """One field citation from the LLM, enriched by verify_citations()."""
    pg: Optional[int] = None      # page number the LLM cited
    q:  Optional[str] = None      # first words of the source sentence, verbatim
    c:  Optional[str] = None      # per-field confidence: H | M | L
    # enrichment (set by verify_citations, never trusted from the LLM)
    verified:   Optional[bool] = None
    found_page: Optional[int] = None
    snippet:    Optional[str] = None
    score:      Optional[float] = None       # numeric per-field confidence, computed
    reasons:    list[str] = Field(default_factory=list)  # why the score is what it is

    @field_validator("pg", mode="before")
    @classmethod
    def _to_int(cls, v: Any) -> Optional[int]:
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @field_validator("q", mode="before")
    @classmethod
    def _clean_q(cls, v: Any) -> Optional[str]:
        return _to_str(v)

    @field_validator("c", mode="before")
    @classmethod
    def _norm_c(cls, v: Any) -> Optional[str]:
        s = _to_str(v)
        if s is None:
            return None
        s = s.upper()[:1]
        return s if s in ("H", "M", "L") else None


def parse_citations(raw: Any, context: Optional[dict]) -> dict[str, Citation]:
    """Validate the LLM's citations block. Invalid entries are skipped silently
    (a bad citation must never sink the extraction itself)."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Citation] = {}
    for field_name, entry in list(raw.items())[:40]:
        if not isinstance(entry, dict) or not isinstance(field_name, str):
            continue
        cite = Citation.model_validate(entry)
        # never trust enrichment fields from the LLM
        cite.verified = None
        cite.found_page = None
        cite.snippet = None
        cite.score = None
        cite.reasons = []
        if cite.q or cite.c:
            out[field_name] = cite
    return out


def split_pages(text: str) -> dict[int, str]:
    """Split [Page N]-marked document text into {page_number: page_text}."""
    if not text:
        return {}
    parts = _PAGE_MARKER_RE.split(text)
    pages: dict[int, str] = {}
    # parts = [preamble, "1", text1, "2", text2, ...]
    for i in range(1, len(parts) - 1, 2):
        try:
            n = int(parts[i])
        except ValueError:
            continue
        # same page number can appear twice if a doc embeds the marker string
        pages[n] = pages.get(n, "") + parts[i + 1]
    return pages


def _normalise_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _find_quote_span(norm_quote: str, norm_page: str, fuzzy: bool) -> Optional[tuple[int, int]]:
    """Locate a normalised quote in normalised page text.
    Exact substring first; sliding-window SequenceMatcher fallback."""
    idx = norm_page.find(norm_quote)
    if idx >= 0:
        return (idx, idx + len(norm_quote))
    if not fuzzy or len(norm_quote) < 12:
        return None
    L = len(norm_quote)
    step = max(1, L // 4)
    best_ratio, best_span = 0.0, None
    matcher = SequenceMatcher(autojunk=False)
    matcher.set_seq2(norm_quote)
    for start in range(0, max(1, len(norm_page) - L + 1), step):
        window = norm_page[start:start + L]
        matcher.set_seq1(window)
        if matcher.real_quick_ratio() < FUZZY_MATCH_THRESHOLD:
            continue
        ratio = matcher.ratio()
        if ratio > best_ratio:
            best_ratio, best_span = ratio, (start, start + L)
    return best_span if best_ratio >= FUZZY_MATCH_THRESHOLD else None


def _expand_sentence(norm_page: str, span: tuple[int, int]) -> str:
    """Expand a matched quote span to its containing sentence (bounded)."""
    start, end = span
    left = max(norm_page.rfind(". ", 0, start), norm_page.rfind("• ", 0, start),
               norm_page.rfind("| ", 0, start))
    left = left + 2 if left >= 0 else max(0, start - 120)
    right_candidates = [p for p in (norm_page.find(". ", end), norm_page.find(" |", end))
                        if p >= 0]
    right = (min(right_candidates) + 1) if right_candidates else min(len(norm_page), end + 200)
    snippet = norm_page[left:right].strip()
    if len(snippet) > SNIPPET_MAX_CHARS:
        snippet = snippet[:SNIPPET_MAX_CHARS - 3] + "..."
    return snippet


def verify_citations(
    citations: dict[str, Citation],
    source_text: Optional[str],
    warnings: list[dict],
) -> None:
    """
    Verify each citation quote against the [Page N]-marked source text,
    enriching Citation objects in place (verified / found_page / snippet).

    - exact or fuzzy match on the cited page, then neighbour pages (±1) —
      LLM page refs are often off by one — then exact-only over all pages
    - unverifiable quote  → warning (possible hallucination)
    - c == "L"            → warning (model self-reports low confidence)
    - no source_text      → verification skipped, verified stays None
    - each citation gets a numeric per-field score (see _field_score)
    """
    if not citations:
        return
    pages = split_pages(source_text) if source_text else {}
    norm_pages = {n: _normalise_ws(t).lower() for n, t in pages.items()}
    # snapshot: scoring subtracts only for validator/consistency warnings,
    # not the ones this function itself appends (those are already reflected
    # in the verified flag / H-M-L base)
    pre_existing_warnings = list(warnings)

    for field_name, cite in citations.items():
        if cite.c == "L":
            warnings.append(make_warning(
                field_name, cite.q, "model self-reports LOW confidence for this field"))

        if not cite.q:
            continue
        if not norm_pages:
            continue  # no page-marked source available — cannot verify

        norm_quote = _normalise_ws(cite.q).lower()
        candidate_pages = []
        if cite.pg in norm_pages:
            candidate_pages = [cite.pg, cite.pg - 1, cite.pg + 1]
        candidate_pages = [p for p in candidate_pages if p in norm_pages]

        found = False
        for p in candidate_pages:
            span = _find_quote_span(norm_quote, norm_pages[p], fuzzy=True)
            if span:
                cite.verified = True
                cite.found_page = p
                cite.snippet = _expand_sentence(norm_pages[p], span)
                found = True
                break
        if not found:
            # last resort: exact-only scan of every page
            for p, norm_page in norm_pages.items():
                idx = norm_page.find(norm_quote)
                if idx >= 0:
                    cite.verified = True
                    cite.found_page = p
                    cite.snippet = _expand_sentence(norm_page, (idx, idx + len(norm_quote)))
                    found = True
                    break
        if not found:
            cite.verified = False
            warnings.append(make_warning(
                f"{field_name}.citation", cite.q,
                "cited quote not found in document — possible hallucination"))

    # score every citation once verification is settled
    for field_name, cite in citations.items():
        cite.score, cite.reasons = _field_score(cite, field_name, pre_existing_warnings)


# Base per-field score from the model's own H/M/L self-report
_C_BASE = {"H": 0.95, "M": 0.7, "L": 0.4}


def _field_score(cite: Citation, field_name: str, warnings: list[dict]) -> tuple[float, list[str]]:
    """
    Numeric per-field confidence plus plain-English reasons:
      base from H/M/L self-report (0.6 when the model gave none)
      verified verbatim in the document  → +0.05 (capped at 1.0)
      citation NOT found (hallucination) → capped at 0.3
      any validation warning on this field → -0.2 (floored at 0.05)
    """
    reasons: list[str] = []
    score = _C_BASE.get(cite.c or "", 0.6)
    if cite.c == "L":
        reasons.append("the model itself flagged this field as uncertain")
    elif cite.c == "M":
        reasons.append("the value was inferred from context rather than stated explicitly")
    elif cite.c is None:
        reasons.append("the model gave no confidence rating for this field")
    if cite.verified is True:
        score = min(1.0, score + 0.05)
    elif cite.verified is False:
        score = min(score, 0.3)
        reasons.append("the cited text could not be found in the document")
    base_field = field_name.split(".")[0]
    matched = [w for w in warnings if w.get("field", "").split(".")[0] == base_field]
    if matched:
        score = max(0.05, score - 0.2)
        reasons.extend(w.get("reason", "") for w in matched[:3])
    return round(score, 2), reasons


def verify_item_sources(
    items: list,
    source_text: Optional[str],
    warnings: list[dict],
    label: str,
    text_attr: str = "description",
) -> None:
    """
    Verify list items (action items / remedial actions) against the source.

    Each item carries a `pg` the LLM cited and verbatim text in `text_attr`;
    the opening words of that text are matched against the cited page
    (± neighbours), falling back to an exact full-document scan. Sets
    item.source_verified / item.source_page in place. An unverifiable item
    is a hallucination signal → warning.
    """
    if not items or not source_text:
        return
    pages = split_pages(source_text)
    if not pages:
        return
    norm_pages = {n: _normalise_ws(t).lower() for n, t in pages.items()}

    for i, item in enumerate(items):
        text = getattr(item, text_attr, None)
        if not text:
            continue
        words = _normalise_ws(text).split(" ")
        norm_quote = " ".join(words[:8]).lower()
        if len(norm_quote) < 12:
            continue  # too short to match meaningfully

        pg = getattr(item, "pg", None)
        candidate_pages = [p for p in (pg, (pg - 1) if pg else None, (pg + 1) if pg else None)
                           if p in norm_pages]
        found_page = None
        for p in candidate_pages:
            if _find_quote_span(norm_quote, norm_pages[p], fuzzy=True):
                found_page = p
                break
        if found_page is None:
            for p, norm_page in norm_pages.items():
                if norm_quote in norm_page:
                    found_page = p
                    break
        item.source_verified = found_page is not None
        item.source_page = found_page
        if found_page is None:
            warnings.append(make_warning(
                f"{label}[{i}]", norm_quote,
                "item text not found in document — possible hallucination"))


def citations_to_json(citations: dict[str, Citation]) -> dict:
    """JSON-safe dict for DB persistence / API responses."""
    return {
        f: {
            "pg": c.pg, "q": c.q, "c": c.c,
            "verified": c.verified, "found_page": c.found_page, "snippet": c.snippet,
            "score": c.score, "reasons": c.reasons,
        }
        for f, c in citations.items()
    }
