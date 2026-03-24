"""
Settings API — LLM provider configuration
Allows the frontend to read and update the active LLM provider at runtime.
"""

import os
from flask import request, jsonify

from . import settings_bp
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.settings')


@settings_bp.route('/llm', methods=['GET'])
def get_llm_settings():
    """Return the current LLM provider configuration (keys are masked)."""
    openai_key = Config.LLM_API_KEY or ''
    claude_key = Config.CLAUDE_API_KEY or ''

    return jsonify({
        "success": True,
        "data": {
            "provider": Config.LLM_PROVIDER,
            "openai": {
                "api_key_set": bool(openai_key),
                "api_key_preview": _mask(openai_key),
                "base_url": Config.LLM_BASE_URL,
                "model": Config.LLM_MODEL_NAME,
            },
            "claude": {
                "api_key_set": bool(claude_key),
                "api_key_preview": _mask(claude_key),
                "model": Config.CLAUDE_MODEL_NAME,
                "console_url": Config.ANTHROPIC_CONSOLE_URL,
            },
        }
    })


@settings_bp.route('/llm', methods=['POST'])
def update_llm_settings():
    """
    Update the active LLM provider at runtime.

    Accepted JSON body:
        {
            "provider": "openai" | "claude",
            "openai_api_key": "sk-...",          // optional
            "openai_base_url": "https://...",    // optional
            "openai_model": "gpt-4o-mini",       // optional
            "claude_api_key": "sk-ant-...",      // optional
            "claude_model": "claude-opus-4-5",   // optional
        }
    """
    body = request.get_json(silent=True) or {}

    provider = body.get('provider', Config.LLM_PROVIDER).lower()
    if provider not in ('openai', 'claude'):
        return jsonify({"success": False, "error": "provider must be 'openai' or 'claude'"}), 400

    # Apply changes to the Config class (in-process, not persisted to .env)
    Config.LLM_PROVIDER = provider

    if 'openai_api_key' in body and body['openai_api_key']:
        Config.LLM_API_KEY = body['openai_api_key']
        os.environ['LLM_API_KEY'] = body['openai_api_key']
    if 'openai_base_url' in body and body['openai_base_url']:
        Config.LLM_BASE_URL = body['openai_base_url']
        os.environ['LLM_BASE_URL'] = body['openai_base_url']
    if 'openai_model' in body and body['openai_model']:
        Config.LLM_MODEL_NAME = body['openai_model']
        os.environ['LLM_MODEL_NAME'] = body['openai_model']
    if 'claude_api_key' in body and body['claude_api_key']:
        Config.CLAUDE_API_KEY = body['claude_api_key']
        os.environ['CLAUDE_API_KEY'] = body['claude_api_key']
    if 'claude_model' in body and body['claude_model']:
        Config.CLAUDE_MODEL_NAME = body['claude_model']
        os.environ['CLAUDE_MODEL_NAME'] = body['claude_model']

    os.environ['LLM_PROVIDER'] = provider
    logger.info(f"LLM provider switched to '{provider}'")

    return jsonify({
        "success": True,
        "message": f"LLM provider set to '{provider}'",
        "data": {"provider": provider}
    })


@settings_bp.route('/claude-console-url', methods=['GET'])
def claude_console_url():
    """Return the Anthropic Console URL so the frontend can link users there."""
    return jsonify({
        "success": True,
        "data": {
            "url": Config.ANTHROPIC_CONSOLE_URL,
            "description": (
                "Open the Anthropic Console to create or copy your Claude API key, "
                "then paste it into the API key field."
            )
        }
    })


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _mask(key: str) -> str:
    """Return a partially masked version of an API key (safe to show in UI)."""
    if not key:
        return ''
    if len(key) <= 8:
        return '*' * len(key)
    return key[:4] + '****' + key[-4:]
