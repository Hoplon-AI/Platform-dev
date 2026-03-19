"""Address cross-validation for the UPRN pipeline.

Compares an original input address against the address returned by a
downstream API (e.g. EPC) to catch UPRN mismatches, stale records, or
unit-level errors within the same building.

Uses two scoring methods and takes the higher:
  - Sequence similarity (difflib.SequenceMatcher) — good for minor formatting diffs
  - Token overlap — good for reordered or partially missing address components

Confidence thresholds:
  >= 0.8  HIGH    — addresses match, safe to proceed
  >= 0.5  MEDIUM  — likely the same address, missing detail (e.g. no postcode)
  <  0.5  LOW     — probable mismatch, UPRN may be wrong

No external dependencies (stdlib only).
"""

import re
from difflib import SequenceMatcher


def _normalize(address: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = address.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _token_overlap(a_tokens: set, b_tokens: set) -> float:
    """Fraction of tokens shared between both addresses."""
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = a_tokens & b_tokens
    return len(intersection) / max(len(a_tokens), len(b_tokens))


def compare_addresses(original: str, returned: str) -> dict:
    """Compare two addresses and return a confidence score.

    Intended for cross-validating addresses across different data sources
    in the pipeline (e.g. OS Places address vs EPC address for the same UPRN).

    Both addresses are normalized (lowercased, punctuation stripped) before
    comparison. The higher of sequence similarity and token overlap is used,
    so reordered or abbreviated addresses still score well.

    Args:
        original: The address from the initial data source (e.g. OS Places).
        returned: The address from the downstream API (e.g. EPC).

    Returns:
        dict with keys:
            - score (float): 0.0 to 1.0, higher is better
            - confidence (str): HIGH (>= 0.8) / MEDIUM (>= 0.5) / LOW (< 0.5)
            - original (str): The original address passed in
            - returned (str): The returned address passed in
    """
    norm_orig = _normalize(original)
    norm_ret = _normalize(returned)

    seq_score = SequenceMatcher(None, norm_orig, norm_ret).ratio()
    token_score = _token_overlap(set(norm_orig.split()), set(norm_ret.split()))

    score = round(max(seq_score, token_score), 3)

    if score >= 0.8:
        confidence = "HIGH"
    elif score >= 0.5:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "score": score,
        "confidence": confidence,
        "original": original,
        "returned": returned,
    }


if __name__ == "__main__":
    tests = [
        ("Flat 17, Brooklands Court, Brooklands Avenue, Cambridge, CB2 8BP",
         "Flat 17, Brooklands Court, Brooklands Avenue"),
        ("30 Sycamore Drive, Carterton, OX18 3AT",
         "30, Sycamore Drive, Carterton"),
        ("10 Downing Street, London",
         "Flat 5, Tower Block, Manchester"),
        ("171 Merrow Street, London, SE17 2NY",
         "171, MERROW STREET, LONDON, SE17 2NY"),
    ]

    for orig, ret in tests:
        result = compare_addresses(orig, ret)
        print(f"Score: {result['score']}  Confidence: {result['confidence']}")
        print(f"  Original: {result['original']}")
        print(f"  Returned: {result['returned']}")
        print()
