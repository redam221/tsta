"""Settings persistence for the TSTA desktop app.

Stores user-configured LLM credentials (the "purchased API") in a local
JSON file under the user home directory, so it survives across runs and
is never hard-coded.
"""

from __future__ import annotations

import json
from pathlib import Path

# Data root: ~/.tsta/  (keeps credentials + trees out of the repo)
DATA_DIR = Path.home() / ".tsta"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = DATA_DIR / "settings.json"
TREES_DIR = DATA_DIR / "trees"
TREES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SETTINGS: dict = {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 2048,
}

# Preset providers — pick one and the base_url / default model fill in.
PROVIDERS: dict = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "doubao": {
        "label": "豆包 (火山方舟)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-1-6-250615",
    },
    "siliconflow": {
        "label": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "custom": {
        "label": "自定义 (OpenAI 兼容)",
        "base_url": "",
        "model": "",
    },
}


def load_settings() -> dict:
    """Load settings, merging over defaults for any missing keys."""
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(data: dict) -> dict:
    """Persist settings. Only known keys are written; credentials are stored
    as-is (this is the user's own local file)."""
    settings = load_settings()
    for key in ("provider", "base_url", "api_key", "model",
                "temperature", "max_tokens"):
        if key in data:
            settings[key] = data[key]
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return settings
