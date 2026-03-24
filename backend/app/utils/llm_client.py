"""
LLM client wrapper
Supports OpenAI and Anthropic Claude providers.
"""

import json
import re
from typing import Optional, Dict, Any, List

from ..config import Config


class LLMClient:
    """LLM client — supports 'openai' and 'claude' providers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ):
        self.provider = (provider or Config.LLM_PROVIDER or 'openai').lower()

        if self.provider == 'claude':
            self._init_claude(api_key, model)
        else:
            self._init_openai(api_key, base_url, model)

    # ------------------------------------------------------------------ #
    #  Initialisation helpers                                              #
    # ------------------------------------------------------------------ #

    def _init_openai(self, api_key, base_url, model):
        from openai import OpenAI
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _init_claude(self, api_key, model):
        import anthropic
        self.api_key = api_key or Config.CLAUDE_API_KEY
        self.model = model or Config.CLAUDE_MODEL_NAME
        if not self.api_key:
            raise ValueError(
                "CLAUDE_API_KEY is not configured. "
                "Get your key at https://console.anthropic.com/settings/keys"
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    # ------------------------------------------------------------------ #
    #  Internal: provider-specific send                                   #
    # ------------------------------------------------------------------ #

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict]
    ) -> str:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format
        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        # Remove <think> blocks emitted by some reasoning models
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    def _chat_claude(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False
    ) -> str:
        # Anthropic separates the system prompt from human/assistant turns
        system_parts: List[str] = []
        filtered: List[Dict[str, str]] = []
        for msg in messages:
            if msg['role'] == 'system':
                system_parts.append(msg['content'])
            else:
                filtered.append(msg)

        if json_mode:
            system_parts.append(
                "You must respond with valid JSON only — no extra text, "
                "no markdown fences, no explanation."
            )

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": filtered,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send a chat request and return the model's text response.

        Args:
            messages: List of role/content dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: OpenAI-style response format hint (ignored for Claude)

        Returns:
            Model response text
        """
        if self.provider == 'claude':
            return self._chat_claude(messages, temperature, max_tokens)
        return self._chat_openai(messages, temperature, max_tokens, response_format)

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send a chat request and return a parsed JSON object.

        Args:
            messages: List of role/content dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON object
        """
        if self.provider == 'claude':
            raw = self._chat_claude(messages, temperature, max_tokens, json_mode=True)
        else:
            raw = self._chat_openai(
                messages, temperature, max_tokens,
                response_format={"type": "json_object"}
            )

        # Strip markdown code fences that some models include
        cleaned = raw.strip()
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError(f"LLM returned invalid JSON: {cleaned}")

