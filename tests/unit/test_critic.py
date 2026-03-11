# tests/unit/test_critic.py
"""Tests for agent/critic.py — quick mode deterministic checks."""
import json
import os
import subprocess
import sys
import pytest
from pathlib import Path
from typing import Dict, Any, List

# ── Path setup (will be used when critic.py exists) ──────────────────
# Imports from critic are added in Task 2


# ── Helpers ──────────────────────────────────────────────────────────

TRADE_CSV_HEADER = "symbol,entry_ts,exit_ts,direction,entry_price,exit_price,pnl_usd,reason\n"


def _make_trade_row(
    symbol: str = "BTC/USDT",
    entry_ts: str = "2025-01-15T10:00:00",
    exit_ts: str = "2025-01-15T14:00:00",
    direction: str = "long",
    entry_price: float = 50000.0,
    exit_price: float = 52000.0,
    pnl_usd: float = 2000.0,
    reason: str = "signal",
) -> str:
    return f"{symbol},{entry_ts},{exit_ts},{direction},{entry_price},{exit_price},{pnl_usd},{reason}\n"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _write_csv(path: Path, rows: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TRADE_CSV_HEADER + "".join(rows))


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def clean_run(tmp_path):
    """A healthy run with no issues — all checks should PASS."""
    run_dir = tmp_path / "results" / "20260307_120000"
    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    # pipeline.json
    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "portfolio_equity": 148000.0,
        "total_pnl": 48000.0,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.90, "s1_sharpe": 3.2},
            "ETH/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.8},
            "SOL/USDT": {"degradation_ratio": 0.95, "s1_sharpe": 3.5},
        },
        "per_pair_results": {
            "BTC/USDT": {
                "max_drawdown": 0.08,
                "total_pnl": 16000.0,
                "num_trades": 8,
            },
            "ETH/USDT": {
                "max_drawdown": 0.07,
                "total_pnl": 16000.0,
                "num_trades": 8,
            },
            "SOL/USDT": {
                "max_drawdown": 0.09,
                "total_pnl": 16000.0,
                "num_trades": 8,
            },
        },
    }
    _write_json(eval_dir / "pipeline.json", pipeline)

    # trades.csv — 8 trades per pair spread across 4 quarters
    rows = []
    months = ["01", "04", "07", "10"]
    for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
        for i, month in enumerate(months):
            for j in range(2):
                day = 10 + j
                rows.append(_make_trade_row(
                    symbol=symbol,
                    entry_ts=f"2025-{month}-{day:02d}T10:00:00",
                    exit_ts=f"2025-{month}-{day:02d}T14:00:00",
                    pnl_usd=2000.0,
                    reason="signal",
                ))
    _write_csv(eval_dir / "trades.csv", rows)

    return run_dir


@pytest.fixture
def overfit_run(tmp_path):
    """A run where WF degradation ratio is below 0.33 — strong overfit signal."""
    run_dir = tmp_path / "results" / "20260307_130000"
    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "portfolio_equity": 120000.0,
        "total_pnl": 20000.0,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.20, "s1_sharpe": 4.5},
            "ETH/USDT": {"degradation_ratio": 0.25, "s1_sharpe": 3.8},
        },
        "per_pair_results": {
            "BTC/USDT": {"max_drawdown": 0.06, "total_pnl": 10000.0, "num_trades": 5},
            "ETH/USDT": {"max_drawdown": 0.05, "total_pnl": 10000.0, "num_trades": 5},
        },
    }
    _write_json(eval_dir / "pipeline.json", pipeline)

    rows = [
        _make_trade_row("BTC/USDT", "2025-01-10T10:00:00", "2025-01-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("BTC/USDT", "2025-04-10T10:00:00", "2025-04-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("BTC/USDT", "2025-07-10T10:00:00", "2025-07-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("BTC/USDT", "2025-10-10T10:00:00", "2025-10-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("BTC/USDT", "2025-11-10T10:00:00", "2025-11-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-01-10T10:00:00", "2025-01-10T14:00:00", symbol="ETH/USDT", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-04-10T10:00:00", "2025-04-10T14:00:00", symbol="ETH/USDT", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-07-10T10:00:00", "2025-07-10T14:00:00", symbol="ETH/USDT", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-10-10T10:00:00", "2025-10-10T14:00:00", symbol="ETH/USDT", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-11-10T10:00:00", "2025-11-10T14:00:00", symbol="ETH/USDT", pnl_usd=5000.0),
    ]
    _write_csv(eval_dir / "trades.csv", rows)

    return run_dir


@pytest.fixture
def dd_floor_gaming_run(tmp_path):
    """A run where max_drawdown is suspiciously close to 5% (DD floor gaming)."""
    run_dir = tmp_path / "results" / "20260307_140000"
    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    pipeline = {
        "symbols": ["BTC/USDT"],
        "portfolio_equity": 140000.0,
        "total_pnl": 40000.0,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.88, "s1_sharpe": 3.0},
        },
        "per_pair_results": {
            "BTC/USDT": {
                # Exactly at DD floor (5.00%) — suspicious
                "max_drawdown": 0.0500,
                "total_pnl": 40000.0,
                "num_trades": 10,
            },
        },
    }
    _write_json(eval_dir / "pipeline.json", pipeline)

    rows = [_make_trade_row("BTC/USDT", f"2025-0{(i % 4) + 1}-10T10:00:00",
                            f"2025-0{(i % 4) + 1}-10T14:00:00", pnl_usd=4000.0)
            for i in range(10)]
    _write_csv(eval_dir / "trades.csv", rows)

    return run_dir


@pytest.fixture
def equity_mismatch_run(tmp_path):
    """A run where sum of per-pair PnL doesn't match portfolio total PnL."""
    run_dir = tmp_path / "results" / "20260307_150000"
    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "portfolio_equity": 160000.0,
        # Reported total_pnl = 60000, but per-pair sum = 42000 (mismatch > 5%)
        "total_pnl": 60000.0,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.90, "s1_sharpe": 2.5},
            "ETH/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.3},
        },
        "per_pair_results": {
            "BTC/USDT": {"max_drawdown": 0.07, "total_pnl": 22000.0, "num_trades": 6},
            "ETH/USDT": {"max_drawdown": 0.06, "total_pnl": 20000.0, "num_trades": 6},
        },
    }
    _write_json(eval_dir / "pipeline.json", pipeline)

    rows = [
        _make_trade_row("BTC/USDT", "2025-01-10T10:00:00", "2025-01-10T14:00:00", pnl_usd=22000.0 / 3),
        _make_trade_row("BTC/USDT", "2025-04-10T10:00:00", "2025-04-10T14:00:00", pnl_usd=22000.0 / 3),
        _make_trade_row("BTC/USDT", "2025-07-10T10:00:00", "2025-07-10T14:00:00", pnl_usd=22000.0 / 3),
        _make_trade_row("ETH/USDT", "2025-01-15T10:00:00", "2025-01-15T14:00:00", symbol="ETH/USDT", pnl_usd=20000.0 / 3),
        _make_trade_row("ETH/USDT", "2025-04-15T10:00:00", "2025-04-15T14:00:00", symbol="ETH/USDT", pnl_usd=20000.0 / 3),
        _make_trade_row("ETH/USDT", "2025-07-15T10:00:00", "2025-07-15T14:00:00", symbol="ETH/USDT", pnl_usd=20000.0 / 3),
    ]
    _write_csv(eval_dir / "trades.csv", rows)

    return run_dir


@pytest.fixture
def concentrated_pnl_run(tmp_path):
    """A run where >50% of PnL comes from a single quarter — distribution concern."""
    run_dir = tmp_path / "results" / "20260307_160000"
    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    pipeline = {
        "symbols": ["BTC/USDT"],
        "portfolio_equity": 130000.0,
        "total_pnl": 30000.0,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.8},
        },
        "per_pair_results": {
            "BTC/USDT": {"max_drawdown": 0.08, "total_pnl": 30000.0, "num_trades": 5},
        },
    }
    _write_json(eval_dir / "pipeline.json", pipeline)

    # Q1 gets 80% of PnL — highly concentrated
    rows = [
        _make_trade_row("BTC/USDT", "2025-01-10T10:00:00", "2025-01-10T14:00:00", pnl_usd=12000.0),
        _make_trade_row("BTC/USDT", "2025-01-20T10:00:00", "2025-01-20T14:00:00", pnl_usd=12000.0),
        _make_trade_row("BTC/USDT", "2025-04-10T10:00:00", "2025-04-10T14:00:00", pnl_usd=2000.0),
        _make_trade_row("BTC/USDT", "2025-07-10T10:00:00", "2025-07-10T14:00:00", pnl_usd=2000.0),
        _make_trade_row("BTC/USDT", "2025-10-10T10:00:00", "2025-10-10T14:00:00", pnl_usd=2000.0),
    ]
    _write_csv(eval_dir / "trades.csv", rows)

    return run_dir


@pytest.fixture
def high_hard_stop_run(tmp_path):
    """A run where >30% of exits are hard_stop — excessive losses from forced exits."""
    run_dir = tmp_path / "results" / "20260307_170000"
    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    pipeline = {
        "symbols": ["BTC/USDT"],
        "portfolio_equity": 110000.0,
        "total_pnl": 10000.0,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.80, "s1_sharpe": 2.0},
        },
        "per_pair_results": {
            "BTC/USDT": {"max_drawdown": 0.10, "total_pnl": 10000.0, "num_trades": 10},
        },
    }
    _write_json(eval_dir / "pipeline.json", pipeline)

    # 4 out of 10 trades exit via hard_stop = 40%
    rows = [
        _make_trade_row("BTC/USDT", "2025-01-05T10:00:00", "2025-01-05T14:00:00", pnl_usd=3000.0, reason="signal"),
        _make_trade_row("BTC/USDT", "2025-01-15T10:00:00", "2025-01-15T14:00:00", pnl_usd=-2000.0, reason="hard_stop"),
        _make_trade_row("BTC/USDT", "2025-02-05T10:00:00", "2025-02-05T14:00:00", pnl_usd=2000.0, reason="signal"),
        _make_trade_row("BTC/USDT", "2025-02-15T10:00:00", "2025-02-15T14:00:00", pnl_usd=-1500.0, reason="hard_stop"),
        _make_trade_row("BTC/USDT", "2025-03-05T10:00:00", "2025-03-05T14:00:00", pnl_usd=2500.0, reason="signal"),
        _make_trade_row("BTC/USDT", "2025-03-15T10:00:00", "2025-03-15T14:00:00", pnl_usd=-1000.0, reason="hard_stop"),
        _make_trade_row("BTC/USDT", "2025-04-05T10:00:00", "2025-04-05T14:00:00", pnl_usd=3000.0, reason="signal"),
        _make_trade_row("BTC/USDT", "2025-04-15T10:00:00", "2025-04-15T14:00:00", pnl_usd=-500.0, reason="hard_stop"),
        _make_trade_row("BTC/USDT", "2025-05-05T10:00:00", "2025-05-05T14:00:00", pnl_usd=2500.0, reason="signal"),
        _make_trade_row("BTC/USDT", "2025-05-15T10:00:00", "2025-05-15T14:00:00", pnl_usd=2000.0, reason="signal"),
    ]
    _write_csv(eval_dir / "trades.csv", rows)

    return run_dir


@pytest.fixture
def score_regression_runs(tmp_path):
    """Two runs for score regression check — prev and current."""
    # Previous run (better score)
    prev_dir = tmp_path / "results" / "20260306_120000"
    eval_dir_prev = prev_dir / "evaluation"
    eval_dir_prev.mkdir(parents=True)

    prev_pipeline = {
        "symbols": ["BTC/USDT"],
        "portfolio_equity": 155000.0,
        "total_pnl": 55000.0,
        "resilience_score": 82.5,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.92, "s1_sharpe": 3.5},
        },
        "per_pair_results": {
            "BTC/USDT": {"max_drawdown": 0.07, "total_pnl": 55000.0, "num_trades": 12},
        },
    }
    _write_json(eval_dir_prev / "pipeline.json", prev_pipeline)

    # Current run (worse score — regression)
    curr_dir = tmp_path / "results" / "20260307_120000"
    eval_dir_curr = curr_dir / "evaluation"
    eval_dir_curr.mkdir(parents=True)

    curr_pipeline = {
        "symbols": ["BTC/USDT"],
        "portfolio_equity": 140000.0,
        "total_pnl": 40000.0,
        "resilience_score": 71.0,
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.8},
        },
        "per_pair_results": {
            "BTC/USDT": {"max_drawdown": 0.09, "total_pnl": 40000.0, "num_trades": 10},
        },
    }
    _write_json(eval_dir_curr / "pipeline.json", curr_pipeline)

    rows = [_make_trade_row("BTC/USDT", f"2025-0{(i % 4) + 1}-{(i * 3 + 10):02d}T10:00:00",
                            f"2025-0{(i % 4) + 1}-{(i * 3 + 10):02d}T14:00:00", pnl_usd=4000.0)
            for i in range(10)]
    _write_csv(eval_dir_curr / "trades.csv", rows)

    return {"prev": prev_dir, "curr": curr_dir}
