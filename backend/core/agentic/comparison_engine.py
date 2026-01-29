"""
Compare regex and agentic extractions and merge into a single features payload.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


# Fields we can compare between regex and agentic (path in features or agentic)
_COMPARABLE = [
    ("evacuation_strategy", "features.fra_specific.evacuation_strategy", "agentic_features.evacuation_strategy.evacuation_strategy_type"),
    ("building_height_category", None, "agentic_features.high_rise_indicators.building_height_category"),
    ("number_of_storeys", None, "agentic_features.high_rise_indicators.number_of_storeys"),
]


def _get_at_path(obj: Dict[str, Any], path: str) -> Any:
    """Get value at dotted path; path like 'a.b.c'."""
    if not path:
        return None
    cur = obj
    for k in path.split("."):
        cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            break
    return cur


def _norm_val(v: Any) -> str:
    """Normalise for comparison."""
    if v is None:
        return ""
    s = str(v).strip().upper()
    # Common aliases
    if s in ("STAY PUT", "STAY_PUT", "STAY-PUT"):
        return "STAY_PUT"
    if s in ("STAY SAFE", "STAY_SAFE"):
        return "STAY_SAFE"
    return s


def calculate_agreement_score(field: str, regex_val: Any, agentic_val: Any) -> float:
    """
    Score agreement between regex and agentic for one field.
    1.0 = both missing or equal; 0.0 = conflicting.
    """
    r = _norm_val(regex_val)
    a = _norm_val(agentic_val)
    if not r and not a:
        return 1.0
    if r == a:
        return 1.0
    if not r or not a:
        return 0.5  # one has value, other doesn't
    # Partial: e.g. one says "STAY_PUT" the other "Stay Put" – already normed
    if r in a or a in r:
        return 0.9
    return 0.0


def identify_discrepancies(
    regex: Dict[str, Any],
    agentic: Dict[str, Any],
    threshold: float = 0.9,
) -> List[Dict[str, Any]]:
    """List fields where agreement is below threshold."""
    out: List[Dict[str, Any]] = []
    for name, rpath, apath in _COMPARABLE:
        rv = _get_at_path(regex, rpath) if rpath else None
        av = _get_at_path(agentic, apath) if apath else None
        score = calculate_agreement_score(name, rv, av)
        if score < threshold:
            out.append({
                "field": name,
                "regex_value": rv,
                "agentic_value": av,
                "score": round(score, 2),
            })
    return out


def compare_extractions(regex: Dict[str, Any], agentic: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare regex and agentic feature dicts.

    Returns:
        {
            "agreement_score": float in [0,1],
            "discrepancies": [ {"field", "regex_value", "agentic_value", "score"} ],
        }
    """
    discrepancies = identify_discrepancies(regex, agentic)
    scores: List[float] = []
    for name, rpath, apath in _COMPARABLE:
        rv = _get_at_path(regex, rpath) if rpath else None
        av = _get_at_path(agentic, apath) if apath else None
        scores.append(calculate_agreement_score(name, rv, av))
    agreement = sum(scores) / len(scores) if scores else 1.0
    return {
        "agreement_score": round(agreement, 2),
        "discrepancies": discrepancies,
    }


def merge_extractions(
    regex: Dict[str, Any],
    agentic: Dict[str, Any],
    comparison: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge regex and agentic into one features dict.

    - Preserves schema_version, extracted_at, document, scanned, features from regex.
    - Overlays agentic_features and docb_features from agentic.
    - Sets extraction_method="merged" and extraction_comparison_metadata=comparison.
    - If agentic is empty, returns regex unchanged with extraction_method="regex".
    """
    has_agentic = (
        bool(agentic.get("agentic_features"))
        or bool(agentic.get("docb_features"))
    )
    if not has_agentic:
        return regex

    merged = dict(regex)
    if agentic.get("agentic_features"):
        merged["agentic_features"] = agentic["agentic_features"]
    if agentic.get("docb_features"):
        merged["docb_features"] = agentic["docb_features"]
    merged["extraction_method"] = "merged"
    merged["extraction_comparison_metadata"] = comparison
    return merged
