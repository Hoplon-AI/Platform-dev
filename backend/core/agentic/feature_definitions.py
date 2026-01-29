"""
Load and validate agentic feature definitions from schemas/agentic-feature-definitions.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


_SCHEMA_FILENAME = "agentic-feature-definitions.json"


def _find_schema_path() -> str:
    """Resolve path to agentic-feature-definitions.json."""
    # From backend/core/agentic/feature_definitions.py -> project_root/schemas
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "schemas" / _SCHEMA_FILENAME,
        Path(os.getcwd()) / "schemas" / _SCHEMA_FILENAME,
    ]
    env_path = os.environ.get("SCHEMAS_PATH")
    if env_path:
        candidates.append(Path(env_path) / _SCHEMA_FILENAME)
    for p in candidates:
        if p and getattr(p, "is_file", lambda: False)():
            return str(p)
    return ""


def get_feature_definitions() -> Dict[str, Any]:
    """
    Load and validate agentic feature definitions.

    Returns:
        Full JSON from agentic-feature-definitions.json.

    Raises:
        FileNotFoundError: If schema file cannot be found.
        ValueError: If schema is invalid (missing required keys).
    """
    path = _find_schema_path()
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(
            f"Schema not found: {_SCHEMA_FILENAME}. "
            "Set SCHEMAS_PATH or run from project root."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Schema root must be a JSON object")
    if "feature_groups" not in data:
        raise ValueError("Schema must contain 'feature_groups'")
    if "extraction_guidance" not in data:
        raise ValueError("Schema must contain 'extraction_guidance'")
    return data


def get_features_for_document_type(document_type: str) -> Dict[str, Any]:
    """
    Get feature definitions relevant for a document type.

    Currently returns the full feature_groups for all PDF types; the schema
    does not define type-specific subsets. Can be extended when the schema
    adds document_type filters.

    Args:
        document_type: e.g. 'fra_document', 'fraew_document', 'scr_document'

    Returns:
        Subset or full feature_groups dict for use in prompts.
    """
    data = get_feature_definitions()
    return data.get("feature_groups", data)
