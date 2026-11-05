"""Configuration management for TSTA."""

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TSTAConfig:
    storage_type: Literal["json", "sqlite"] = "json"
    storage_path: str = "./data/trees"
    host: str = "127.0.0.1"
    port: int = 8000


def get_config() -> TSTAConfig:
    return TSTAConfig(
        storage_type=os.getenv("TSTA_STORAGE_TYPE", "json"),
        storage_path=os.getenv("TSTA_STORAGE_PATH", "./data/trees"),
        host=os.getenv("TSTA_HOST", "127.0.0.1"),
        port=int(os.getenv("TSTA_PORT", "8000")),
    )
