"""
MQE I/O Utilities — JSON + CSV saving/loading + shared formatting.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("mqe.io")


def save_json(path: Path, obj: dict[str, Any]) -> None:
    """Save dict to JSON file. Creates parent dirs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON file to dict. Raises on missing/invalid files."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def try_load_json(path: Path) -> Optional[dict[str, Any]]:
    """Load JSON file, return None on failure."""
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError, FileNotFoundError):
        return None


def save_trades_csv(path: Path, trades: list[dict[str, Any]]) -> None:
    """Save trades list to CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not trades:
        path.touch()
        return
    fieldnames = list(trades[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trades)


def fmt(value: Any, decimals: int = 2) -> str:
    """Format a numeric value safely."""
    if isinstance(value, int):
        return str(value)
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)
