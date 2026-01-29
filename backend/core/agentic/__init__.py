"""
Agentic feature extraction using AWS Bedrock and Claude.

Provides:
- feature_definitions: load/validate schemas, get features per document type
- bedrock_client: invoke Claude on Bedrock
- extraction_agent: extract A/B/C features from PDF text
- comparison_engine: compare regex vs agentic, merge with attribution
"""

from backend.core.agentic.feature_definitions import (
    get_feature_definitions,
    get_features_for_document_type,
)
from backend.core.agentic.bedrock_client import invoke_claude, BedrockAgenticError
from backend.core.agentic.extraction_agent import extract_features_agentic
from backend.core.agentic.comparison_engine import (
    compare_extractions,
    merge_extractions,
)

__all__ = [
    "get_feature_definitions",
    "get_features_for_document_type",
    "invoke_claude",
    "BedrockAgenticError",
    "extract_features_agentic",
    "compare_extractions",
    "merge_extractions",
]
