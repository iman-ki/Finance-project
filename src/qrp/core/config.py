"""Configuration loading. Experiments change YAML, not code."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"
ENV_FILE = PROJECT_ROOT / ".env"

# Used to annualize per-period numbers (e.g. volatility * sqrt(periods)).
PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env(path: Path | str = ENV_FILE) -> None:
    """Read KEY=VALUE lines from .env into os.environ. Variables already set win."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def resolve_path(path: Path | str) -> Path:
    """Config paths are relative to the project root, not the current directory."""
    path = Path(path)
    return path if path.is_absolute() else PROJECT_ROOT / path
