"""
Thin wrapper to invoke Claude on AWS Bedrock.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


class BedrockAgenticError(Exception):
    """Raised when Bedrock invoke or response handling fails."""
    pass


def invoke_claude(
    prompt: str,
    *,
    system: str | None = None,
    model_id: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """
    Invoke LLM on Bedrock and return the assistant text.

    Supports multiple model providers:
    - Anthropic (Claude): anthropic.claude-*
    - Mistral: mistral.*
    - Amazon (Nova): amazon.nova-*

    Args:
        prompt: User message (e.g. extraction instruction + document text).
        system: Optional system prompt.
        model_id: Bedrock model ID (default from BEDROCK_MODEL_ID).
        max_tokens: Max tokens to generate.
        temperature: Sampling temperature.

    Returns:
        Assistant reply as string.

    Raises:
        BedrockAgenticError: On invoke or parse errors.
    """
    model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
    try:
        client = _get_bedrock_runtime()
    except Exception as e:
        raise BedrockAgenticError(f"Failed to create Bedrock client: {e}") from e

    # Build request body based on model provider
    body = _build_request_body(model_id, prompt, system, max_tokens, temperature)

    try:
        print(f"[BEDROCK] Sending request to model {model_id}, body size: {len(json.dumps(body))} bytes")
        resp = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body).encode("utf-8"),
        )
    except Exception as e:
        err = str(e).lower()
        print(f"[BEDROCK] Error: {e}")
        if "accessdeniedException" in str(e) or "access denied" in err:
            raise BedrockAgenticError(f"Bedrock access denied for model {model_id}: {e}") from e
        if "resourcenotfound" in err or "no such" in err:
            raise BedrockAgenticError(f"Bedrock model not found: {model_id}") from e
        if "throttl" in err or "rate" in err:
            raise BedrockAgenticError("Bedrock rate limited") from e
        if "validation" in err or "invalid" in err:
            raise BedrockAgenticError(f"Bedrock validation error: {e}") from e
        raise BedrockAgenticError(f"Bedrock invoke failed: {e}") from e

    try:
        out = json.loads(resp["body"].read().decode("utf-8"))
    except Exception as e:
        raise BedrockAgenticError(f"Failed to decode Bedrock response: {e}") from e

    # Parse response based on model provider
    return _parse_response(model_id, out)


def _build_request_body(
    model_id: str,
    prompt: str,
    system: str | None,
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    """Build provider-specific request body."""

    if model_id.startswith("anthropic."):
        # Anthropic Claude - Messages API
        messages: List[Dict[str, Any]] = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        body: Dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            body["system"] = [{"type": "text", "text": system}]
        return body

    elif model_id.startswith("mistral."):
        # Mistral - Chat completion format
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        return {
            "prompt": f"<s>[INST] {full_prompt} [/INST]",
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    elif model_id.startswith("amazon.nova"):
        # Amazon Nova - Messages API (similar to Anthropic)
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        body = {
            "messages": messages,
            "inferenceConfig": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            body["system"] = [{"text": system}]
        return body

    else:
        # Default to Anthropic format
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            body["system"] = [{"type": "text", "text": system}]
        return body


def _parse_response(model_id: str, response: Dict[str, Any]) -> str:
    """Parse provider-specific response."""

    if model_id.startswith("anthropic."):
        # Anthropic Claude response
        content = response.get("content") or []
        texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(texts) if texts else ""

    elif model_id.startswith("mistral."):
        # Mistral response
        outputs = response.get("outputs") or []
        if outputs and isinstance(outputs, list):
            return outputs[0].get("text", "")
        return ""

    elif model_id.startswith("amazon.nova"):
        # Amazon Nova response
        output = response.get("output") or {}
        message = output.get("message") or {}
        content = message.get("content") or []
        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
        return "\n".join(texts) if texts else ""

    else:
        # Default to Anthropic format
        content = response.get("content") or []
        texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(texts) if texts else ""


def _get_bedrock_runtime():
    import boto3
    return boto3.client("bedrock-runtime", region_name=os.getenv("AWS_DEFAULT_REGION", "eu-west-1"))
