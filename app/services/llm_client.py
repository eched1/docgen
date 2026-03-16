"""
LLM client — supports OpenAI and Anthropic for documentation generation.
Uses OPENAI_API_KEY or ANTHROPIC_API_KEY from environment.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client for doc generation."""

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if self.openai_key:
            self.provider = "openai"
            self.model = os.getenv("LLM_MODEL", "gpt-4o")
            self.base_url = "https://api.openai.com/v1"
        elif self.anthropic_key:
            self.provider = "anthropic"
            self.model = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
            self.base_url = "https://api.anthropic.com/v1"
        else:
            self.provider = "none"
            self.model = "none"
            logger.warning("No LLM API key found — set OPENAI_API_KEY or ANTHROPIC_API_KEY")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> tuple[str, dict]:
        """Generate text from LLM. Returns (content, usage_dict)."""
        if self.provider == "none":
            return self._fallback_generate(user_prompt), {"provider": "fallback", "tokens": 0}

        async with httpx.AsyncClient(timeout=120.0) as client:
            if self.provider == "openai":
                return await self._openai_generate(client, system_prompt, user_prompt, max_tokens, temperature)
            else:
                return await self._anthropic_generate(client, system_prompt, user_prompt, max_tokens, temperature)

    async def _openai_generate(
        self, client: httpx.AsyncClient, system: str, user: str, max_tokens: int, temp: float
    ) -> tuple[str, dict]:
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": temp,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = {
            "provider": "openai",
            "model": self.model,
            "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
            "total_tokens": data.get("usage", {}).get("total_tokens", 0),
        }
        return content, usage

    async def _anthropic_generate(
        self, client: httpx.AsyncClient, system: str, user: str, max_tokens: int, temp: float
    ) -> tuple[str, dict]:
        resp = await client.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "max_tokens": max_tokens,
                "temperature": temp,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["content"][0]["text"]
        usage = {
            "provider": "anthropic",
            "model": self.model,
            "input_tokens": data.get("usage", {}).get("input_tokens", 0),
            "output_tokens": data.get("usage", {}).get("output_tokens", 0),
            "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
        }
        return content, usage

    def _fallback_generate(self, user_prompt: str) -> str:
        """Generate basic docs without LLM — template-based fallback."""
        return (
            "# Infrastructure Documentation\n\n"
            "> Generated without AI — set OPENAI_API_KEY or ANTHROPIC_API_KEY for full generation.\n\n"
            "## Raw Config Summary\n\n"
            f"```\n{user_prompt[:3000]}\n```\n"
        )


# Singleton
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
