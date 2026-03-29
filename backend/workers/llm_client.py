# """
# backend/workers/llm_client.py

# Provider-agnostic LLM client.

# Local development:  uses Groq API (FREE — no credit card needed)
#                     or Anthropic API (paid — $5 credits)
# Production (AWS):   uses AWS Bedrock (IAM role, no API key needed)

# Configuration (environment variables):
#     LLM_PROVIDER=groq        → uses GROQ_API_KEY       (free, recommended for local dev)
#     LLM_PROVIDER=anthropic   → uses ANTHROPIC_API_KEY  (paid)
#     LLM_PROVIDER=bedrock     → uses AWS IAM role       (production)

# Usage:
#     from backend.workers.llm_client import LLMClient

#     client = LLMClient.from_env()
#     response_text = await client.extract(prompt)

# Getting a free Groq key:
#     1. Go to https://console.groq.com
#     2. Sign up with Google (one click, no credit card)
#     3. API Keys → Create API Key
#     4. Set GROQ_API_KEY=gsk_xxxx in your .env
# """

# import asyncio
# import logging
# import os

# logger = logging.getLogger(__name__)


# # ------------------------------------------------------------------
# # Model IDs
# # ------------------------------------------------------------------

# # Groq — free tier, fast, excellent at JSON extraction
# GROQ_MODEL = "llama-3.3-70b-versatile"

# # Direct Anthropic API (paid)
# ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# # AWS Bedrock — IAM role grants access in production
# BEDROCK_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"


# # ------------------------------------------------------------------
# # LLMClient
# # ------------------------------------------------------------------

# class LLMClient:
#     """
#     Async wrapper around Groq, Anthropic, or AWS Bedrock.
#     All three share the same interface: await client.extract(prompt)
#     """

#     def __init__(self, provider: str, groq_client=None, anthropic_client=None, bedrock_client=None):
#         self._provider  = provider
#         self._groq      = groq_client
#         self._anthropic = anthropic_client
#         self._bedrock   = bedrock_client

#     # ------------------------------------------------------------------
#     # Factory
#     # ------------------------------------------------------------------

#     @classmethod
#     def from_env(cls) -> "LLMClient":
#         """
#         Create LLMClient from LLM_PROVIDER env var.

#         LLM_PROVIDER=groq      (default — free, no credit card)
#         LLM_PROVIDER=anthropic (paid Anthropic credits)
#         LLM_PROVIDER=bedrock   (AWS production, IAM role)
#         """
#         provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()

#         if provider == "groq":
#             return cls._create_groq_client()
#         elif provider == "anthropic":
#             return cls._create_anthropic_client()
#         elif provider == "bedrock":
#             return cls._create_bedrock_client()
#         else:
#             raise ValueError(
#                 f"Unknown LLM_PROVIDER='{provider}'. "
#                 f"Set LLM_PROVIDER=groq, anthropic, or bedrock"
#             )

#     @classmethod
#     def _create_groq_client(cls) -> "LLMClient":
#         try:
#             from groq import AsyncGroq
#         except ImportError:
#             raise ImportError(
#                 "groq package not installed. Run: pip install groq\n"
#                 "Get a free API key (no credit card) at https://console.groq.com"
#             )

#         api_key = os.getenv("GROQ_API_KEY")
#         if not api_key:
#             raise EnvironmentError(
#                 "GROQ_API_KEY not set.\n"
#                 "1. Go to https://console.groq.com\n"
#                 "2. Sign up with Google (free, no credit card)\n"
#                 "3. API Keys → Create API Key\n"
#                 "4. Add GROQ_API_KEY=gsk_xxxx to your .env"
#             )

#         client = AsyncGroq(api_key=api_key)
#         logger.info("LLMClient: using Groq API (model=%s)", GROQ_MODEL)
#         return cls(provider="groq", groq_client=client)

#     @classmethod
#     def _create_anthropic_client(cls) -> "LLMClient":
#         try:
#             import anthropic
#         except ImportError:
#             raise ImportError(
#                 "anthropic package not installed. Run: pip install anthropic"
#             )

#         api_key = os.getenv("ANTHROPIC_API_KEY")
#         if not api_key:
#             raise EnvironmentError(
#                 "ANTHROPIC_API_KEY not set. Get a key at https://console.anthropic.com"
#             )

#         client = anthropic.AsyncAnthropic(api_key=api_key)
#         logger.info("LLMClient: using Anthropic API (model=%s)", ANTHROPIC_MODEL)
#         return cls(provider="anthropic", anthropic_client=client)

#     @classmethod
#     def _create_bedrock_client(cls) -> "LLMClient":
#         try:
#             import boto3
#         except ImportError:
#             raise ImportError(
#                 "boto3 package not installed. Run: pip install boto3"
#             )

#         region = os.getenv("AWS_REGION", "eu-west-1")
#         client = boto3.client("bedrock-runtime", region_name=region)
#         logger.info("LLMClient: using AWS Bedrock (model=%s region=%s)",
#                     BEDROCK_MODEL_ID, region)
#         return cls(provider="bedrock", bedrock_client=client)

#     # ------------------------------------------------------------------
#     # Main interface
#     # ------------------------------------------------------------------

#     async def extract(self, prompt: str, max_tokens: int = 4096) -> str:
#         """
#         Send prompt to LLM, return raw response text (should be JSON).
#         """
#         if self._provider == "groq":
#             return await self._call_groq(prompt, max_tokens)
#         elif self._provider == "anthropic":
#             return await self._call_anthropic(prompt, max_tokens)
#         elif self._provider == "bedrock":
#             return await self._call_bedrock(prompt, max_tokens)
#         else:
#             raise RuntimeError(f"Unknown provider: {self._provider}")

#     # ------------------------------------------------------------------
#     # Groq (free)
#     # ------------------------------------------------------------------

#     async def _call_groq(self, prompt: str, max_tokens: int) -> str:
#         """Call Groq API. Fully async."""
#         completion = await self._groq.chat.completions.create(
#             model       = GROQ_MODEL,
#             max_tokens  = max_tokens,
#             messages    = [{"role": "user", "content": prompt}],
#             temperature = 0.1,  # Low temp for consistent JSON output
#         )
#         return completion.choices[0].message.content

#     # ------------------------------------------------------------------
#     # Anthropic (paid)
#     # ------------------------------------------------------------------

#     async def _call_anthropic(self, prompt: str, max_tokens: int) -> str:
#         """Call Anthropic API directly. Fully async."""
#         message = await self._anthropic.messages.create(
#             model      = ANTHROPIC_MODEL,
#             max_tokens = max_tokens,
#             messages   = [{"role": "user", "content": prompt}],
#         )
#         return message.content[0].text

#     # ------------------------------------------------------------------
#     # AWS Bedrock (production)
#     # ------------------------------------------------------------------

#     async def _call_bedrock(self, prompt: str, max_tokens: int) -> str:
#         """
#         Call AWS Bedrock. boto3 is synchronous so we run it in an
#         executor to avoid blocking the FastAPI event loop.
#         """
#         import json as _json

#         body = _json.dumps({
#             "anthropic_version": "bedrock-2023-05-31",
#             "max_tokens": max_tokens,
#             "messages": [{"role": "user", "content": prompt}],
#         })

#         loop = asyncio.get_event_loop()

#         def _invoke():
#             response = self._bedrock.invoke_model(
#                 modelId     = BEDROCK_MODEL_ID,
#                 body        = body,
#                 contentType = "application/json",
#                 accept      = "application/json",
#             )
#             return _json.loads(response["body"].read())

#         result = await loop.run_in_executor(None, _invoke)
#         return result["content"][0]["text"]


"""
backend/workers/llm_client.py

Provider-agnostic LLM client.

Local development:  uses Groq API (FREE — no credit card needed)
Production (AWS):   uses AWS Bedrock (IAM role, no API key needed)

Groq free tier limits by model:
  llama-3.1-8b-instant    →  30,000 TPM  / 500,000 TPD  ← USE THIS for dev
  llama-3.3-70b-versatile →   6,000 TPM  / 100,000 TPD  ← hits limit fast

Configuration:
  LLM_PROVIDER=groq       → uses GROQ_API_KEY
  LLM_PROVIDER=anthropic  → uses ANTHROPIC_API_KEY
  LLM_PROVIDER=bedrock    → uses AWS IAM role (production)
  GROQ_MODEL=<model>      → override model (optional)
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

# ── Groq model selection ──────────────────────────────────────────────
#
# llama-3.1-8b-instant   → 500K tokens/day FREE  ← DEFAULT for local dev
# llama-3.3-70b-versatile→ 100K tokens/day FREE  ← burns out fast
#
# Override with: GROQ_MODEL=llama-3.3-70b-versatile in .env (if you need better quality)
#
GROQ_MODEL_DEFAULT = "llama-3.1-8b-instant"
GROQ_MODEL         = os.getenv("GROQ_MODEL", GROQ_MODEL_DEFAULT)

# Anthropic direct API
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# AWS Bedrock
BEDROCK_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

# Google Gemini
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")


class LLMClient:
    """
    Async wrapper around Groq, Anthropic, AWS Bedrock, or Google Gemini.
    All four share the same interface: await client.extract(prompt)

    LLM_PROVIDER=groq     → GROQ_API_KEY        (free tier, local dev)
    LLM_PROVIDER=anthropic → ANTHROPIC_API_KEY   (paid)
    LLM_PROVIDER=bedrock  → AWS IAM role         (production)
    LLM_PROVIDER=gemini   → GEMINI_API_KEY       (Google AI Studio)
    """

    def __init__(self, provider, groq_client=None, anthropic_client=None,
                 bedrock_client=None, gemini_client=None):
        self._provider  = provider
        self._groq      = groq_client
        self._anthropic = anthropic_client
        self._bedrock   = bedrock_client
        self._gemini    = gemini_client

    @classmethod
    def from_env(cls) -> "LLMClient":
        provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
        if provider == "groq":
            return cls._create_groq_client()
        elif provider == "anthropic":
            return cls._create_anthropic_client()
        elif provider == "bedrock":
            return cls._create_bedrock_client()
        elif provider == "gemini":
            return cls._create_gemini_client()
        else:
            raise ValueError(f"Unknown LLM_PROVIDER='{provider}'. Use: groq, anthropic, bedrock, or gemini")

    @classmethod
    def _create_groq_client(cls) -> "LLMClient":
        try:
            from groq import AsyncGroq
        except ImportError:
            raise ImportError("pip install groq")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set.\n"
                "1. Go to https://console.groq.com\n"
                "2. Sign up with Google (free, no credit card)\n"
                "3. API Keys → Create API Key\n"
                "4. Add GROQ_API_KEY=gsk_xxxx to your .env"
            )
        client = AsyncGroq(api_key=api_key)
        logger.info("LLMClient: Groq model=%s (500K tokens/day free)", GROQ_MODEL)
        return cls(provider="groq", groq_client=client)

    @classmethod
    def _create_anthropic_client(cls) -> "LLMClient":
        try:
            import anthropic
        except ImportError:
            raise ImportError("pip install anthropic")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set.")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        logger.info("LLMClient: Anthropic model=%s", ANTHROPIC_MODEL)
        return cls(provider="anthropic", anthropic_client=client)

    @classmethod
    def _create_bedrock_client(cls) -> "LLMClient":
        try:
            import boto3
        except ImportError:
            raise ImportError("pip install boto3")
        region = os.getenv("AWS_REGION", "eu-west-1")
        client = boto3.client("bedrock-runtime", region_name=region)
        logger.info("LLMClient: Bedrock model=%s region=%s", BEDROCK_MODEL_ID, region)
        return cls(provider="bedrock", bedrock_client=client)

    @classmethod
    def _create_gemini_client(cls) -> "LLMClient":
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai package not installed. Run: pip install google-genai"
            )
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY not set.\n"
                "1. Go to https://aistudio.google.com\n"
                "2. Click 'Get API Key' → Create API key\n"
                "3. Set GEMINI_API_KEY=AIzaSy... in your environment"
            )
        client = genai.Client(api_key=api_key)
        logger.info("LLMClient: Gemini model=%s", GEMINI_MODEL)
        return cls(provider="gemini", gemini_client=client)

    @property
    def supports_large_context(self) -> bool:
        """
        True for providers that handle full documents in one pass.
        Gemini: 1M token context. Bedrock/Anthropic: 200K token context.
        Groq free tier: 6K TPM hard limit — must use two-pass chunking.
        """
        return self._provider in ("gemini", "bedrock", "anthropic")

    async def extract(self, prompt: str, max_tokens: int = 4096) -> str:
        if self._provider == "groq":
            return await self._call_groq(prompt, max_tokens)
        elif self._provider == "anthropic":
            return await self._call_anthropic(prompt, max_tokens)
        elif self._provider == "bedrock":
            return await self._call_bedrock(prompt, max_tokens)
        elif self._provider == "gemini":
            return await self._call_gemini(prompt, max_tokens)
        else:
            raise RuntimeError(f"Unknown provider: {self._provider}")

    async def _call_groq(self, prompt: str, max_tokens: int) -> str:
        completion = await self._groq.chat.completions.create(
            model       = GROQ_MODEL,
            max_tokens  = max_tokens,
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.1,
        )
        return completion.choices[0].message.content

    async def _call_anthropic(self, prompt: str, max_tokens: int) -> str:
        message = await self._anthropic.messages.create(
            model      = ANTHROPIC_MODEL,
            max_tokens = max_tokens,
            messages   = [{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    async def _call_bedrock(self, prompt: str, max_tokens: int) -> str:
        import json as _json
        body = _json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        })
        loop = asyncio.get_event_loop()
        def _invoke():
            response = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID, body=body,
                contentType="application/json", accept="application/json",
            )
            return _json.loads(response["body"].read())
        result = await loop.run_in_executor(None, _invoke)
        return result["content"][0]["text"]

    async def _call_gemini(self, prompt: str, max_tokens: int) -> str:
        # google-genai SDK is synchronous — run in executor to avoid blocking FastAPI
        # Gemini 2.5 Flash has thinking mode ON by default — thinking tokens eat into
        # the output budget and truncate JSON responses. Disable thinking for extraction.
        loop = asyncio.get_event_loop()
        def _invoke():
            from google.genai import types
            response = self._gemini.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=16384,
                    temperature=0.1,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return response.text
        return await loop.run_in_executor(None, _invoke)