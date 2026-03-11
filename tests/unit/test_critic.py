# tests/unit/test_critic.py
"""Tests for agent/critic.py — quick mode deterministic checks."""
import json
import os
import subprocess
import sys
import pytest
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))
from critic import (
    load_run_data, load_trades,
    check_wf_degradation, check_dd_floor_gaming,
    check_equity_reconstruction, check_trade_distribution,
    check_hard_stop_ratio, check_score_regression,
    quick, full,
)


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
        _make_trade_row("ETH/USDT", "2025-01-10T10:00:00", "2025-01-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-04-10T10:00:00", "2025-04-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-07-10T10:00:00", "2025-07-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-10-10T10:00:00", "2025-10-10T14:00:00", pnl_usd=5000.0),
        _make_trade_row("ETH/USDT", "2025-11-10T10:00:00", "2025-11-10T14:00:00", pnl_usd=5000.0),
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
        _make_trade_row("ETH/USDT", "2025-01-15T10:00:00", "2025-01-15T14:00:00", pnl_usd=20000.0 / 3),
        _make_trade_row("ETH/USDT", "2025-04-15T10:00:00", "2025-04-15T14:00:00", pnl_usd=20000.0 / 3),
        _make_trade_row("ETH/USDT", "2025-07-15T10:00:00", "2025-07-15T14:00:00", pnl_usd=20000.0 / 3),
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


# ── Task 2: Data Loading Tests ────────────────────────────────────────

class TestDataLoading:
    def test_load_run_data_returns_dict(self, clean_run):
        data = load_run_data(clean_run)
        assert isinstance(data, dict)

    def test_load_run_data_has_symbols(self, clean_run):
        data = load_run_data(clean_run)
        assert "symbols" in data
        assert data["symbols"] == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    def test_load_run_data_has_total_pnl(self, clean_run):
        data = load_run_data(clean_run)
        assert "total_pnl" in data
        assert data["total_pnl"] == 48000.0

    def test_load_run_data_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_run_data(tmp_path / "nonexistent_run")

    def test_load_trades_returns_list(self, clean_run):
        trades = load_trades(clean_run)
        assert isinstance(trades, list)

    def test_load_trades_has_correct_count(self, clean_run):
        trades = load_trades(clean_run)
        # 3 pairs × 8 trades = 24
        assert len(trades) == 24

    def test_load_trades_row_has_required_fields(self, clean_run):
        trades = load_trades(clean_run)
        required = {"symbol", "entry_ts", "exit_ts", "direction",
                    "entry_price", "exit_price", "pnl_usd", "reason"}
        for trade in trades:
            assert required.issubset(set(trade.keys()))

    def test_load_trades_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_trades(tmp_path / "nonexistent_run")


# ── Task 3: Check Function Tests ──────────────────────────────────────

class TestCheckWfDegradation:
    def test_clean_run_passes(self, clean_run):
        data = load_run_data(clean_run)
        result = check_wf_degradation(data)
        assert result["status"] == "PASS"
        assert result["check"] == "wf_degradation"

    def test_overfit_run_fails(self, overfit_run):
        data = load_run_data(overfit_run)
        result = check_wf_degradation(data)
        assert result["status"] == "FAIL"

    def test_overfit_result_has_value(self, overfit_run):
        data = load_run_data(overfit_run)
        result = check_wf_degradation(data)
        assert "value" in result
        assert result["value"] < 0.33

    def test_no_wf_metrics_warns(self, tmp_path):
        data = {"symbols": ["BTC/USDT"], "total_pnl": 10000.0}
        result = check_wf_degradation(data)
        assert result["status"] == "WARNING"

    def test_threshold_in_result(self, overfit_run):
        data = load_run_data(overfit_run)
        result = check_wf_degradation(data)
        assert "threshold" in result
        assert result["threshold"] == 0.33


class TestCheckDdFloorGaming:
    def test_clean_run_passes(self, clean_run):
        data = load_run_data(clean_run)
        result = check_dd_floor_gaming(data)
        assert result["status"] == "PASS"
        assert result["check"] == "dd_floor_gaming"

    def test_dd_floor_gaming_run_fails(self, dd_floor_gaming_run):
        data = load_run_data(dd_floor_gaming_run)
        result = check_dd_floor_gaming(data)
        assert result["status"] == "FAIL"

    def test_fail_message_mentions_floor(self, dd_floor_gaming_run):
        data = load_run_data(dd_floor_gaming_run)
        result = check_dd_floor_gaming(data)
        assert "0.05" in result["message"] or "floor" in result["message"].lower()

    def test_no_per_pair_warns(self):
        data = {"symbols": ["BTC/USDT"], "total_pnl": 10000.0}
        result = check_dd_floor_gaming(data)
        assert result["status"] == "WARNING"

    def test_dd_slightly_above_floor_passes(self):
        # DD at 6% — not near 5% floor
        data = {
            "per_pair_results": {
                "BTC/USDT": {"max_drawdown": 0.06, "total_pnl": 5000.0},
            }
        }
        result = check_dd_floor_gaming(data)
        assert result["status"] == "PASS"


class TestCheckEquityReconstruction:
    def test_clean_run_passes(self, clean_run):
        data = load_run_data(clean_run)
        result = check_equity_reconstruction(data)
        assert result["status"] == "PASS"
        assert result["check"] == "equity_reconstruction"

    def test_equity_mismatch_run_fails(self, equity_mismatch_run):
        data = load_run_data(equity_mismatch_run)
        result = check_equity_reconstruction(data)
        assert result["status"] == "FAIL"

    def test_mismatch_value_in_result(self, equity_mismatch_run):
        data = load_run_data(equity_mismatch_run)
        result = check_equity_reconstruction(data)
        assert "value" in result
        assert result["value"] > 0.05  # >5% mismatch

    def test_no_total_pnl_warns(self):
        data = {
            "per_pair_results": {"BTC/USDT": {"total_pnl": 5000.0}},
        }
        result = check_equity_reconstruction(data)
        assert result["status"] == "WARNING"

    def test_no_per_pair_warns(self):
        data = {"total_pnl": 5000.0}
        result = check_equity_reconstruction(data)
        assert result["status"] == "WARNING"

    def test_exact_match_passes(self):
        data = {
            "total_pnl": 10000.0,
            "per_pair_results": {
                "BTC/USDT": {"total_pnl": 6000.0},
                "ETH/USDT": {"total_pnl": 4000.0},
            },
        }
        result = check_equity_reconstruction(data)
        assert result["status"] == "PASS"


class TestCheckTradeDistribution:
    def test_clean_run_passes(self, clean_run):
        trades = load_trades(clean_run)
        result = check_trade_distribution(trades)
        assert result["status"] == "PASS"
        assert result["check"] == "trade_distribution"

    def test_concentrated_pnl_fails(self, concentrated_pnl_run):
        trades = load_trades(concentrated_pnl_run)
        result = check_trade_distribution(trades)
        # Q1 has 80% of PnL (12000+12000 = 24000 / 30000 = 80%)
        assert result["status"] in ("FAIL", "WARNING")

    def test_concentrated_pnl_value_above_threshold(self, concentrated_pnl_run):
        trades = load_trades(concentrated_pnl_run)
        result = check_trade_distribution(trades)
        assert "value" in result
        assert result["value"] > 0.50

    def test_no_trades_warns(self):
        result = check_trade_distribution([])
        assert result["status"] == "WARNING"

    def test_result_has_check_name(self, clean_run):
        trades = load_trades(clean_run)
        result = check_trade_distribution(trades)
        assert result["check"] == "trade_distribution"


class TestCheckHardStopRatio:
    def test_clean_run_passes(self, clean_run):
        trades = load_trades(clean_run)
        result = check_hard_stop_ratio(trades)
        assert result["status"] == "PASS"
        assert result["check"] == "hard_stop_ratio"

    def test_high_hard_stop_run_fails(self, high_hard_stop_run):
        trades = load_trades(high_hard_stop_run)
        result = check_hard_stop_ratio(trades)
        # 4/10 = 40% hard_stop > 30% threshold
        assert result["status"] == "FAIL"

    def test_fail_result_has_value(self, high_hard_stop_run):
        trades = load_trades(high_hard_stop_run)
        result = check_hard_stop_ratio(trades)
        assert "value" in result
        assert result["value"] > 0.30

    def test_no_trades_warns(self):
        result = check_hard_stop_ratio([])
        assert result["status"] == "WARNING"

    def test_zero_hard_stops_passes(self):
        trades = [
            {"symbol": "BTC/USDT", "entry_ts": "2025-01-10T10:00:00",
             "exit_ts": "2025-01-10T14:00:00", "direction": "long",
             "entry_price": "50000", "exit_price": "51000",
             "pnl_usd": "1000", "reason": "signal"},
            {"symbol": "BTC/USDT", "entry_ts": "2025-02-10T10:00:00",
             "exit_ts": "2025-02-10T14:00:00", "direction": "long",
             "entry_price": "50000", "exit_price": "51000",
             "pnl_usd": "1000", "reason": "trailing_stop"},
        ]
        result = check_hard_stop_ratio(trades)
        assert result["status"] == "PASS"
        assert result["value"] == 0.0


class TestCheckScoreRegression:
    def test_score_in_run_data_passes_without_prev(self, score_regression_runs):
        curr_data = load_run_data(score_regression_runs["curr"])
        result = check_score_regression(curr_data)
        # No prev_score → PASS with note about no comparison
        assert result["status"] == "PASS"
        assert result["check"] == "score_regression"

    def test_regression_with_prev_score_fails(self, score_regression_runs):
        curr_data = load_run_data(score_regression_runs["curr"])
        prev_data = load_run_data(score_regression_runs["prev"])
        prev_score = prev_data["resilience_score"]  # 82.5
        result = check_score_regression(curr_data, prev_score=prev_score)
        # 71.0 vs 82.5 = -11.5 delta → FAIL
        assert result["status"] == "FAIL"

    def test_skip_when_both_explicit_and_current_lower(self):
        # When both params provided and current <= prev, skip
        data = {"resilience_score": 75.0}
        result = check_score_regression(data, current_score=75.0, prev_score=80.0)
        assert result["status"] == "SKIP"

    def test_no_score_warns(self):
        data = {"symbols": ["BTC/USDT"]}
        result = check_score_regression(data)
        assert result["status"] == "WARNING"

    def test_improvement_passes(self):
        data = {"resilience_score": 85.0}
        result = check_score_regression(data, prev_score=80.0)
        assert result["status"] == "PASS"
        assert result["value"] == 85.0

    def test_minor_regression_warns(self):
        data = {"resilience_score": 78.0}
        result = check_score_regression(data, prev_score=80.0)
        # -2.0 delta → WARNING (< 0 but > -5)
        assert result["status"] == "WARNING"
