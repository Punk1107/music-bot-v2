# -*- coding: utf-8 -*-
"""
core/nlu.py — AI-powered Natural Language Understanding pipeline (P4-1).

Converts free-text user messages into structured bot actions using an LLM.
Supports OpenAI and Anthropic as providers.

Configuration (in .env):
  NLU_ENABLED=false              # Set to "true" to activate
  NLU_PROVIDER=openai            # "openai" or "anthropic"
  OPENAI_API_KEY=sk-...          # Required if NLU_PROVIDER=openai
  ANTHROPIC_API_KEY=sk-ant-...   # Required if NLU_PROVIDER=anthropic
  NLU_MODEL=gpt-4o-mini          # Optional: override default model
  NLU_MAX_TOKENS=256             # Optional: cap response tokens

Usage:
    from core.nlu import NLUPipeline, NLUResult
    pipeline = NLUPipeline()

    result: NLUResult | None = await pipeline.parse("play something relaxing")
    if result:
        if result.action == "play":
            await bot.play_query(result.params["query"])

NLUResult actions:
  play          — params: {"query": str}
  skip          — params: {}
  stop          — params: {}
  pause         — params: {}
  resume        — params: {}
  volume_set    — params: {"level": int}   (0–200)
  loop          — params: {"mode": str}    ("off" | "track" | "queue")
  queue_show    — params: {}
  unknown       — params: {"raw": str}     (unrecognised intent)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a Discord music bot command interpreter. Parse the user's message and
return a single JSON object matching this schema exactly — no prose, no markdown:

{
  "action": "<one of: play|skip|stop|pause|resume|volume_set|loop|queue_show|unknown>",
  "params": { <action-specific parameters, empty {} if none> }
}

Action → params mapping:
  play       → {"query": "<search terms or URL>"}
  skip       → {}
  stop       → {}
  pause      → {}
  resume     → {}
  volume_set → {"level": <integer 0-200>}
  loop       → {"mode": "<off|track|queue>"}
  queue_show → {}
  unknown    → {"raw": "<original user message>"}

Rules:
- If the user wants to play music, extract their search intent as the query.
- If the intent is ambiguous, return action="unknown".
- Always return valid JSON. Never include comments or extra keys.
"""

_DEFAULT_MODELS = {
    "openai":    "gpt-4o-mini",
    "anthropic": "claude-haiku-20240307",
}


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class NLUResult:
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0   # Reserved for future scoring

    def __bool__(self) -> bool:
        return self.action != "unknown"


# ── Pipeline ──────────────────────────────────────────────────────────────────

class NLUPipeline:
    """
    Routes free-text to the configured LLM and returns a structured NLUResult.

    All calls are fully async and non-blocking. Requires the shared
    aiohttp.ClientSession from the bot (pass as session= parameter to parse()).
    """

    def __init__(self) -> None:
        self.enabled    = os.getenv("NLU_ENABLED", "false").lower() == "true"
        self.provider   = os.getenv("NLU_PROVIDER", "openai").lower()
        self.model      = os.getenv("NLU_MODEL", _DEFAULT_MODELS.get(self.provider, "gpt-4o-mini"))
        self.max_tokens = int(os.getenv("NLU_MAX_TOKENS", "256"))
        self._api_key   = self._load_api_key()

        if self.enabled and not self._api_key:
            logger.warning(
                "NLU_ENABLED=true but no API key found for provider '%s'. "
                "NLU will be disabled.", self.provider
            )
            self.enabled = False

        if self.enabled:
            logger.info(
                "NLU pipeline enabled: provider=%s model=%s",
                self.provider, self.model,
            )

    def _load_api_key(self) -> Optional[str]:
        if self.provider == "openai":
            return os.getenv("OPENAI_API_KEY") or None
        elif self.provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY") or None
        return None

    async def parse(
        self,
        user_message: str,
        *,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> Optional[NLUResult]:
        """
        Parse *user_message* and return an NLUResult, or None if NLU is
        disabled / an error occurs.

        Args:
            user_message: Raw user text (e.g. "play something relaxing")
            session:      Shared aiohttp session; a temporary one is created if None.
        """
        if not self.enabled:
            return None
        if not user_message or not user_message.strip():
            return None

        try:
            if self.provider == "openai":
                raw = await self._call_openai(user_message, session=session)
            elif self.provider == "anthropic":
                raw = await self._call_anthropic(user_message, session=session)
            else:
                logger.error("Unknown NLU provider: %s", self.provider)
                return None

            return self._parse_response(raw)

        except Exception as exc:
            logger.warning("NLU parse failed for message %r: %s", user_message[:50], exc)
            return None

    # ── Provider calls ────────────────────────────────────────────────────────

    async def _call_openai(
        self,
        message: str,
        *,
        session: Optional[aiohttp.ClientSession],
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system",  "content": _SYSTEM_PROMPT},
                {"role": "user",    "content": message},
            ],
            "max_tokens":  self.max_tokens,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }
        async with self._get_session(session) as sess:
            async with sess.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload, headers=headers,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    async def _call_anthropic(
        self,
        message: str,
        *,
        session: Optional[aiohttp.ClientSession],
    ) -> str:
        payload = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "system":     _SYSTEM_PROMPT,
            "messages":   [{"role": "user", "content": message}],
        }
        headers = {
            "x-api-key":         self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        }
        async with self._get_session(session) as sess:
            async with sess.post(
                "https://api.anthropic.com/v1/messages",
                json=payload, headers=headers,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["content"][0]["text"]

    # ── Response parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> NLUResult:
        try:
            data   = json.loads(raw)
            action = data.get("action", "unknown").lower()
            params = data.get("params", {})
            if not isinstance(params, dict):
                params = {}
            return NLUResult(action=action, params=params)
        except (json.JSONDecodeError, AttributeError) as exc:
            logger.debug("NLU response parse error: %s — raw: %r", exc, raw[:200])
            return NLUResult(action="unknown", params={"raw": raw})

    # ── Session helper ────────────────────────────────────────────────────────

    class _get_session:
        """Context manager: reuse existing session or create a temporary one."""
        def __init__(self, session: Optional[aiohttp.ClientSession]) -> None:
            self._provided = session
            self._owned: Optional[aiohttp.ClientSession] = None

        async def __aenter__(self) -> aiohttp.ClientSession:
            if self._provided and not self._provided.closed:
                return self._provided
            self._owned = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15.0)
            )
            return self._owned

        async def __aexit__(self, *_) -> None:
            if self._owned and not self._owned.closed:
                await self._owned.close()
