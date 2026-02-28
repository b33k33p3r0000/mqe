"""
MQE I/O Utilities — JSON + CSV saving/loading.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def save_json(path: Path, obj: Dict[str, Any]) -> None:
    """Save dict to JSON file. Creates parent dirs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file to dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_trades_csv(path: Path, trades: List[Dict[str, Any]]) -> None:
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
