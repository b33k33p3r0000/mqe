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
    _load_history, _quick_result_to_output, _full_result_to_output,
)


# ── Helpers ──────────────────────────────────────────────────────────

# Real CSV columns: entry_ts,entry_price,exit_ts,exit_price,hold_bars,size,
#                   capital_at_entry,pnl_abs,pnl_pct,symbol,reason,direction
TRADE_CSV_HEADER = (
    "entry_ts,entry_price,exit_ts,exit_price,hold_bars,size,"
    "capital_at_entry,pnl_abs,pnl_pct,symbol,reason,direction\n"
)


def _make_trade_row(
    symbol: str = "BTC_USDT",
    entry_ts: str = "2025-01-15T10:00:00",
    exit_ts: str = "2025-01-15T14:00:00",
    direction: str = "long",
    entry_price: float = 50000.0,
    exit_price: float = 52000.0,
    pnl_abs: float = 2000.0,
    pnl_pct: float = 0.04,
    hold_bars: int = 4,
    size: float = 1.0,
    capital_at_entry: float = 100000.0,
    reason: str = "opposing_signal",
) -> str:
    return (
        f"{entry_ts},{entry_price},{exit_ts},{exit_price},{hold_bars},{size},"
        f"{capital_at_entry},{pnl_abs},{pnl_pct},{symbol},{reason},{direction}\n"
    )


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _write_csv(path: Path, rows: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TRADE_CSV_HEADER + "".join(rows))


def _make_run_dir(
    tmp_path: Path,
    name: str,
    pipeline: dict,
    portfolio: dict,
    trade_rows_by_symbol: Dict[str, List[str]],
) -> Path:
    """Create a run directory with the real MQE layout."""
    run_dir = tmp_path / "results" / name
    eval_dir = run_dir / "evaluation"
    trades_dir = eval_dir / "per_pair_trades"
    trades_dir.mkdir(parents=True, exist_ok=True)

    _write_json(run_dir / "pipeline_result.json", pipeline)
    _write_json(eval_dir / "portfolio_metrics.json", portfolio)

    for symbol_file, rows in trade_rows_by_symbol.items():
        _write_csv(trades_dir / f"{symbol_file}.csv", rows)

    return run_dir


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def clean_run(tmp_path):
    """A healthy run with no issues — all checks should PASS."""
    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.90, "s1_sharpe": 3.2},
            "ETH/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.8},
            "SOL/USDT": {"degradation_ratio": 0.95, "s1_sharpe": 3.5},
        },
        "tier_assignments": {
            "BTC/USDT": {"tier": "S", "sharpe": 3.2},
            "ETH/USDT": {"tier": "S", "sharpe": 2.8},
            "SOL/USDT": {"tier": "A", "sharpe": 3.5},
        },
    }
    portfolio = {
        "total_pnl": 48000.0,
        "equity": 148000.0,
        "portfolio_max_drawdown": 0.08,
        "sortino_ratio": 2.5,
        "calmar_ratio": 2.0,
        "sharpe_ratio_equity_based": 2.2,
        "trades": 24,
        "win_rate": 0.625,
        "profitable_months_ratio": 0.75,
        "monthly_returns": [0.01, 0.02, -0.01, 0.03],
    }

    # 8 trades per pair spread across 4 quarters, total pnl = 48000
    months = ["01", "04", "07", "10"]
    trade_rows: Dict[str, List[str]] = {}
    for symbol_str, symbol_file in [
        ("BTC_USDT", "BTC_USDT"),
        ("ETH_USDT", "ETH_USDT"),
        ("SOL_USDT", "SOL_USDT"),
    ]:
        rows = []
        for i, month in enumerate(months):
            for j in range(2):
                day = 10 + j
                rows.append(_make_trade_row(
                    symbol=symbol_str,
                    entry_ts=f"2025-{month}-{day:02d}T10:00:00",
                    exit_ts=f"2025-{month}-{day:02d}T14:00:00",
                    pnl_abs=2000.0,
                    reason="opposing_signal",
                ))
        trade_rows[symbol_file] = rows

    return _make_run_dir(tmp_path, "20260307_120000", pipeline, portfolio, trade_rows)


@pytest.fixture
def overfit_run(tmp_path):
    """A run where WF degradation ratio is below 0.33 — strong overfit signal."""
    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.20, "s1_sharpe": 4.5},
            "ETH/USDT": {"degradation_ratio": 0.25, "s1_sharpe": 3.8},
        },
        "tier_assignments": {
            "BTC/USDT": {"tier": "S"},
            "ETH/USDT": {"tier": "S"},
        },
    }
    portfolio = {
        "total_pnl": 50000.0,
        "equity": 150000.0,
        "portfolio_max_drawdown": 0.06,
        "sortino_ratio": 3.0,
        "trades": 10,
        "win_rate": 0.6,
    }

    trade_rows: Dict[str, List[str]] = {}
    for symbol_file in ["BTC_USDT", "ETH_USDT"]:
        rows = []
        for month in ["01", "04", "07", "10"]:
            rows.append(_make_trade_row(
                symbol=symbol_file,
                entry_ts=f"2025-{month}-10T10:00:00",
                exit_ts=f"2025-{month}-10T14:00:00",
                pnl_abs=5000.0,
            ))
        rows.append(_make_trade_row(
            symbol=symbol_file,
            entry_ts="2025-11-10T10:00:00",
            exit_ts="2025-11-10T14:00:00",
            pnl_abs=5000.0,
        ))
        trade_rows[symbol_file] = rows

    return _make_run_dir(tmp_path, "20260307_130000", pipeline, portfolio, trade_rows)


@pytest.fixture
def dd_floor_gaming_run(tmp_path):
    """A run where portfolio_max_drawdown is suspiciously close to 5% (DD floor gaming)."""
    pipeline = {
        "symbols": ["BTC/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.88, "s1_sharpe": 3.0},
        },
        "tier_assignments": {
            "BTC/USDT": {"tier": "S"},
        },
    }
    portfolio = {
        "total_pnl": 40000.0,
        "equity": 140000.0,
        # Exactly at DD floor (5.00%) — suspicious
        "portfolio_max_drawdown": 0.0500,
        "sortino_ratio": 2.8,
        "trades": 10,
        "win_rate": 0.7,
    }

    rows = [
        _make_trade_row("BTC_USDT", f"2025-0{(i % 4) + 1}-10T10:00:00",
                        f"2025-0{(i % 4) + 1}-10T14:00:00", pnl_abs=4000.0)
        for i in range(10)
    ]

    return _make_run_dir(tmp_path, "20260307_140000", pipeline, portfolio,
                         {"BTC_USDT": rows})


@pytest.fixture
def equity_mismatch_run(tmp_path):
    """A run where sum of trade pnl_abs doesn't match portfolio total_pnl."""
    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.90, "s1_sharpe": 2.5},
            "ETH/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.3},
        },
        "tier_assignments": {
            "BTC/USDT": {"tier": "S"},
            "ETH/USDT": {"tier": "S"},
        },
    }
    portfolio = {
        # Reported total_pnl = 60000, but trade sum will be ~42000 (mismatch > 5%)
        "total_pnl": 60000.0,
        "equity": 160000.0,
        "portfolio_max_drawdown": 0.07,
        "sortino_ratio": 2.1,
        "trades": 6,
        "win_rate": 0.67,
    }

    btc_rows = [
        _make_trade_row("BTC_USDT", f"2025-0{m}-10T10:00:00",
                        f"2025-0{m}-10T14:00:00", pnl_abs=22000.0 / 3)
        for m in [1, 4, 7]
    ]
    eth_rows = [
        _make_trade_row("ETH_USDT", f"2025-0{m}-15T10:00:00",
                        f"2025-0{m}-15T14:00:00", pnl_abs=20000.0 / 3)
        for m in [1, 4, 7]
    ]

    return _make_run_dir(tmp_path, "20260307_150000", pipeline, portfolio,
                         {"BTC_USDT": btc_rows, "ETH_USDT": eth_rows})


@pytest.fixture
def concentrated_pnl_run(tmp_path):
    """A run where >50% of PnL comes from a single quarter — distribution concern."""
    pipeline = {
        "symbols": ["BTC/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.8},
        },
        "tier_assignments": {
            "BTC/USDT": {"tier": "S"},
        },
    }
    portfolio = {
        "total_pnl": 30000.0,
        "equity": 130000.0,
        "portfolio_max_drawdown": 0.08,
        "sortino_ratio": 2.3,
        "trades": 5,
        "win_rate": 0.8,
    }

    # Q1 gets 80% of PnL — highly concentrated
    rows = [
        _make_trade_row("BTC_USDT", "2025-01-10T10:00:00", "2025-01-10T14:00:00", pnl_abs=12000.0),
        _make_trade_row("BTC_USDT", "2025-01-20T10:00:00", "2025-01-20T14:00:00", pnl_abs=12000.0),
        _make_trade_row("BTC_USDT", "2025-04-10T10:00:00", "2025-04-10T14:00:00", pnl_abs=2000.0),
        _make_trade_row("BTC_USDT", "2025-07-10T10:00:00", "2025-07-10T14:00:00", pnl_abs=2000.0),
        _make_trade_row("BTC_USDT", "2025-10-10T10:00:00", "2025-10-10T14:00:00", pnl_abs=2000.0),
    ]

    return _make_run_dir(tmp_path, "20260307_160000", pipeline, portfolio,
                         {"BTC_USDT": rows})


@pytest.fixture
def high_hard_stop_run(tmp_path):
    """A run where >30% of exits are hard_stop — excessive forced exits."""
    pipeline = {
        "symbols": ["BTC/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.80, "s1_sharpe": 2.0},
        },
        "tier_assignments": {
            "BTC/USDT": {"tier": "S"},
        },
    }
    portfolio = {
        "total_pnl": 10000.0,
        "equity": 110000.0,
        "portfolio_max_drawdown": 0.10,
        "sortino_ratio": 1.8,
        "trades": 10,
        "win_rate": 0.5,
    }

    # 4 out of 10 trades exit via hard_stop = 40%
    rows = [
        _make_trade_row("BTC_USDT", "2025-01-05T10:00:00", "2025-01-05T14:00:00", pnl_abs=3000.0, reason="opposing_signal"),
        _make_trade_row("BTC_USDT", "2025-01-15T10:00:00", "2025-01-15T14:00:00", pnl_abs=-2000.0, reason="hard_stop"),
        _make_trade_row("BTC_USDT", "2025-02-05T10:00:00", "2025-02-05T14:00:00", pnl_abs=2000.0, reason="opposing_signal"),
        _make_trade_row("BTC_USDT", "2025-02-15T10:00:00", "2025-02-15T14:00:00", pnl_abs=-1500.0, reason="hard_stop"),
        _make_trade_row("BTC_USDT", "2025-03-05T10:00:00", "2025-03-05T14:00:00", pnl_abs=2500.0, reason="opposing_signal"),
        _make_trade_row("BTC_USDT", "2025-03-15T10:00:00", "2025-03-15T14:00:00", pnl_abs=-1000.0, reason="hard_stop"),
        _make_trade_row("BTC_USDT", "2025-04-05T10:00:00", "2025-04-05T14:00:00", pnl_abs=3000.0, reason="opposing_signal"),
        _make_trade_row("BTC_USDT", "2025-04-15T10:00:00", "2025-04-15T14:00:00", pnl_abs=-500.0, reason="hard_stop"),
        _make_trade_row("BTC_USDT", "2025-05-05T10:00:00", "2025-05-05T14:00:00", pnl_abs=2500.0, reason="opposing_signal"),
        _make_trade_row("BTC_USDT", "2025-05-15T10:00:00", "2025-05-15T14:00:00", pnl_abs=2000.0, reason="opposing_signal"),
    ]

    return _make_run_dir(tmp_path, "20260307_170000", pipeline, portfolio,
                         {"BTC_USDT": rows})


@pytest.fixture
def score_regression_runs(tmp_path):
    """Two runs for score regression check — prev (better) and curr (worse)."""
    prev_pipeline = {
        "symbols": ["BTC/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.92, "s1_sharpe": 3.5},
        },
        "tier_assignments": {"BTC/USDT": {"tier": "S"}},
    }
    prev_portfolio = {
        "total_pnl": 55000.0,
        "equity": 155000.0,
        "portfolio_max_drawdown": 0.05,
        "sortino_ratio": 4.0,
        "trades": 12,
        "win_rate": 0.67,
    }

    curr_pipeline = {
        "symbols": ["BTC/USDT"],
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 0.85, "s1_sharpe": 2.8},
        },
        "tier_assignments": {"BTC/USDT": {"tier": "S"}},
    }
    # Sortino dropped by 2.5 (>1.0 threshold) → FAIL
    curr_portfolio = {
        "total_pnl": 40000.0,
        "equity": 140000.0,
        "portfolio_max_drawdown": 0.09,
        "sortino_ratio": 1.5,
        "trades": 10,
        "win_rate": 0.55,
    }

    curr_rows = [
        _make_trade_row("BTC_USDT", f"2025-0{(i % 4) + 1}-{(i * 3 + 10):02d}T10:00:00",
                        f"2025-0{(i % 4) + 1}-{(i * 3 + 10):02d}T14:00:00", pnl_abs=4000.0)
        for i in range(10)
    ]

    prev_dir = _make_run_dir(tmp_path, "20260306_120000", prev_pipeline, prev_portfolio,
                              {"BTC_USDT": [
                                  _make_trade_row("BTC_USDT", f"2025-0{(i % 4) + 1}-10T10:00:00",
                                                  f"2025-0{(i % 4) + 1}-10T14:00:00", pnl_abs=5000.0)
                                  for i in range(10)
                              ]})
    curr_dir = _make_run_dir(tmp_path, "20260307_120000", curr_pipeline, curr_portfolio,
                              {"BTC_USDT": curr_rows})

    return {"prev": prev_dir, "curr": curr_dir}


# ── Task 2: Data Loading Tests ────────────────────────────────────────

class TestDataLoading:
    def test_load_run_data_returns_dict(self, clean_run):
        data = load_run_data(clean_run)
        assert isinstance(data, dict)

    def test_load_run_data_has_wf_eval_metrics(self, clean_run):
        data = load_run_data(clean_run)
        assert "wf_eval_metrics" in data
        assert "BTC/USDT" in data["wf_eval_metrics"]

    def test_load_run_data_has_tier_assignments(self, clean_run):
        data = load_run_data(clean_run)
        assert "tier_assignments" in data
        assert "BTC/USDT" in data["tier_assignments"]

    def test_load_run_data_has_portfolio(self, clean_run):
        data = load_run_data(clean_run)
        assert "portfolio" in data
        assert data["portfolio"]["total_pnl"] == 48000.0

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

    def test_load_trades_pnl_abs_is_float(self, clean_run):
        trades = load_trades(clean_run)
        for trade in trades:
            assert isinstance(trade["pnl_abs"], float)

    def test_load_trades_row_has_required_fields(self, clean_run):
        trades = load_trades(clean_run)
        required = {"symbol", "entry_ts", "exit_ts", "direction",
                    "entry_price", "exit_price", "pnl_abs", "pnl_pct", "reason"}
        for trade in trades:
            assert required.issubset(set(trade.keys()))

    def test_load_trades_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_trades(tmp_path / "nonexistent_run")


# ── Task 3: Check Function Tests ──────────────────────────────────────

class TestCheckWfDegradation:
    def test_clean_run_passes(self, clean_run):
        data = load_run_data(clean_run)
        result = check_wf_degradation(data)
        assert result["status"] == "PASS"
        assert result["name"] == "wf_degradation"

    def test_overfit_run_fails(self, overfit_run):
        data = load_run_data(overfit_run)
        result = check_wf_degradation(data)
        assert result["status"] == "FAIL"

    def test_overfit_result_has_value(self, overfit_run):
        data = load_run_data(overfit_run)
        result = check_wf_degradation(data)
        assert "value" in result
        assert result["value"] < 0.33

    def test_no_wf_metrics_warns(self):
        data = {"wf_eval_metrics": {}, "tier_assignments": {}}
        result = check_wf_degradation(data)
        assert result["status"] == "WARNING"

    def test_threshold_in_result(self, overfit_run):
        data = load_run_data(overfit_run)
        result = check_wf_degradation(data)
        assert "threshold" in result
        assert result["threshold"] == 0.33

    def test_x_tier_pairs_excluded(self):
        """X-tier pairs should not affect the WF degradation check."""
        data = {
            "wf_eval_metrics": {
                "BTC/USDT": {"degradation_ratio": 0.90},
                "WEAK/USDT": {"degradation_ratio": 0.10},  # would cause FAIL if included
            },
            "tier_assignments": {
                "BTC/USDT": {"tier": "S"},
                "WEAK/USDT": {"tier": "X"},  # excluded
            },
        }
        result = check_wf_degradation(data)
        assert result["status"] == "PASS"


class TestCheckDdFloorGaming:
    def test_clean_run_passes(self, clean_run):
        data = load_run_data(clean_run)
        result = check_dd_floor_gaming(data)
        assert result["status"] == "PASS"
        assert result["name"] == "dd_floor_gaming"

    def test_dd_floor_gaming_run_fails(self, dd_floor_gaming_run):
        data = load_run_data(dd_floor_gaming_run)
        result = check_dd_floor_gaming(data)
        assert result["status"] == "FAIL"

    def test_fail_detail_mentions_floor(self, dd_floor_gaming_run):
        data = load_run_data(dd_floor_gaming_run)
        result = check_dd_floor_gaming(data)
        assert "0.05" in result["detail"] or "floor" in result["detail"].lower()

    def test_no_portfolio_warns(self):
        data = {"portfolio": {}, "wf_eval_metrics": {}, "tier_assignments": {}}
        result = check_dd_floor_gaming(data)
        assert result["status"] == "WARNING"

    def test_dd_above_floor_passes(self):
        # DD at 8% — not near 5% floor
        data = {
            "portfolio": {"portfolio_max_drawdown": 0.08, "total_pnl": 5000.0},
        }
        result = check_dd_floor_gaming(data)
        assert result["status"] == "PASS"


class TestCheckEquityReconstruction:
    def test_clean_run_passes(self, clean_run):
        data = load_run_data(clean_run)
        trades = load_trades(clean_run)
        result = check_equity_reconstruction(data, trades)
        assert result["status"] == "PASS"
        assert result["name"] == "equity_reconstruction"

    def test_equity_mismatch_run_fails(self, equity_mismatch_run):
        data = load_run_data(equity_mismatch_run)
        trades = load_trades(equity_mismatch_run)
        result = check_equity_reconstruction(data, trades)
        assert result["status"] == "FAIL"

    def test_mismatch_value_in_result(self, equity_mismatch_run):
        data = load_run_data(equity_mismatch_run)
        trades = load_trades(equity_mismatch_run)
        result = check_equity_reconstruction(data, trades)
        assert "value" in result
        assert result["value"] > 0.05  # >5% mismatch

    def test_no_total_pnl_warns(self):
        data = {"portfolio": {}}
        result = check_equity_reconstruction(data, [])
        assert result["status"] == "WARNING"

    def test_no_trades_warns(self):
        data = {"portfolio": {"total_pnl": 5000.0}}
        result = check_equity_reconstruction(data, [])
        assert result["status"] == "WARNING"

    def test_exact_match_passes(self):
        data = {"portfolio": {"total_pnl": 10000.0}}
        trades = [
            {"pnl_abs": 6000.0, "pnl_pct": 0.06, "entry_ts": "2025-01-10T10:00:00", "reason": "opposing_signal"},
            {"pnl_abs": 4000.0, "pnl_pct": 0.04, "entry_ts": "2025-04-10T10:00:00", "reason": "opposing_signal"},
        ]
        result = check_equity_reconstruction(data, trades)
        assert result["status"] == "PASS"


class TestCheckTradeDistribution:
    def test_clean_run_passes(self, clean_run):
        trades = load_trades(clean_run)
        result = check_trade_distribution(trades)
        assert result["status"] == "PASS"
        assert result["name"] == "trade_distribution"

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

    def test_result_has_name_field(self, clean_run):
        trades = load_trades(clean_run)
        result = check_trade_distribution(trades)
        assert result["name"] == "trade_distribution"


class TestCheckHardStopRatio:
    def test_clean_run_passes(self, clean_run):
        trades = load_trades(clean_run)
        result = check_hard_stop_ratio(trades)
        assert result["status"] == "PASS"
        assert result["name"] == "hard_stop_ratio"

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
            {"pnl_abs": 1000.0, "pnl_pct": 0.01, "entry_ts": "2025-01-10T10:00:00",
             "symbol": "BTC_USDT", "reason": "opposing_signal", "direction": "long",
             "entry_price": "50000", "exit_price": "51000", "exit_ts": "2025-01-10T14:00:00"},
            {"pnl_abs": 1000.0, "pnl_pct": 0.01, "entry_ts": "2025-02-10T10:00:00",
             "symbol": "BTC_USDT", "reason": "trailing_stop", "direction": "long",
             "entry_price": "50000", "exit_price": "51000", "exit_ts": "2025-02-10T14:00:00"},
        ]
        result = check_hard_stop_ratio(trades)
        assert result["status"] == "PASS"
        assert result["value"] == 0.0


class TestCheckScoreRegression:
    def test_no_prev_data_passes(self, clean_run):
        data = load_run_data(clean_run)
        result = check_score_regression(data)
        assert result["status"] == "PASS"
        assert result["name"] == "score_regression"

    def test_regression_with_prev_data_fails(self, score_regression_runs):
        curr_data = load_run_data(score_regression_runs["curr"])
        prev_data = load_run_data(score_regression_runs["prev"])
        result = check_score_regression(curr_data, prev_data=prev_data)
        # Sortino dropped 4.0 → 1.5 = -2.5 delta < -1.0 → FAIL
        assert result["status"] == "FAIL"

    def test_no_portfolio_metrics_warns(self):
        data = {"portfolio": {}, "wf_eval_metrics": {}, "tier_assignments": {}}
        result = check_score_regression(data)
        assert result["status"] == "WARNING"

    def test_stable_metrics_passes(self):
        curr = {"portfolio": {"portfolio_max_drawdown": 0.07, "sortino_ratio": 3.0}}
        prev = {"portfolio": {"portfolio_max_drawdown": 0.06, "sortino_ratio": 2.9}}
        result = check_score_regression(curr, prev_data=prev)
        assert result["status"] == "PASS"

    def test_detail_field_present(self, clean_run):
        data = load_run_data(clean_run)
        result = check_score_regression(data)
        assert "detail" in result


# ── Task 4: Quick() Orchestrator Tests ───────────────────────────────

class TestQuick:
    def test_returns_list_of_dicts(self, clean_run):
        results = quick(clean_run)
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_returns_six_checks(self, clean_run):
        results = quick(clean_run)
        assert len(results) == 6

    def test_all_checks_have_required_fields(self, clean_run):
        results = quick(clean_run)
        for r in results:
            assert "name" in r
            assert "status" in r
            assert "detail" in r

    def test_check_names_are_correct(self, clean_run):
        results = quick(clean_run)
        names = {r["name"] for r in results}
        expected = {
            "wf_degradation",
            "dd_floor_gaming",
            "equity_reconstruction",
            "trade_distribution",
            "hard_stop_ratio",
            "score_regression",
        }
        assert names == expected

    def test_clean_run_all_pass(self, clean_run):
        results = quick(clean_run)
        statuses = {r["status"] for r in results}
        # Only PASS/WARNING expected — no FAIL for clean run
        assert "FAIL" not in statuses

    def test_overfit_run_has_fail(self, overfit_run):
        results = quick(overfit_run)
        statuses = [r["status"] for r in results]
        assert "FAIL" in statuses

    def test_with_prev_run_dir(self, score_regression_runs):
        curr_dir = score_regression_runs["curr"]
        prev_dir = score_regression_runs["prev"]
        results = quick(curr_dir, prev_run_dir=prev_dir)
        assert len(results) == 6
        # Score regression: Sortino 4.0 → 1.5 → should detect regression
        score_check = next(r for r in results if r["name"] == "score_regression")
        assert score_check["status"] == "FAIL"

    def test_without_prev_run_dir(self, clean_run):
        results = quick(clean_run)
        score_check = next(r for r in results if r["name"] == "score_regression")
        assert score_check["status"] in ("PASS", "WARNING")

    def test_full_returns_quick_results(self, clean_run):
        result = full(clean_run)
        assert "quick_results" in result
        assert "checks" in result["quick_results"]
        assert len(result["quick_results"]["checks"]) == 6

    def test_full_has_metrics(self, clean_run):
        result = full(clean_run)
        assert "metrics" in result
        assert result["metrics"] is not None

    def test_full_has_history_summary(self, clean_run):
        result = full(clean_run)
        assert "history_summary" in result

    def test_dd_gaming_run_has_fail(self, dd_floor_gaming_run):
        results = quick(dd_floor_gaming_run)
        dd_check = next(r for r in results if r["name"] == "dd_floor_gaming")
        assert dd_check["status"] == "FAIL"

    def test_equity_mismatch_run_has_fail(self, equity_mismatch_run):
        results = quick(equity_mismatch_run)
        eq_check = next(r for r in results if r["name"] == "equity_reconstruction")
        assert eq_check["status"] == "FAIL"

    def test_high_hard_stop_run_has_fail(self, high_hard_stop_run):
        results = quick(high_hard_stop_run)
        hs_check = next(r for r in results if r["name"] == "hard_stop_ratio")
        assert hs_check["status"] == "FAIL"


# ── Task 6: CLI Tests ─────────────────────────────────────────────────

CRITIC_PY = str(Path(__file__).resolve().parents[2] / "agent" / "critic.py")


class TestCLI:
    def test_quick_outputs_json(self, clean_run, tmp_path):
        """CLI quick mode outputs valid JSON to stdout."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(clean_run),
             "--history", str(history_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_quick_output_has_pass_field(self, clean_run, tmp_path):
        """CLI quick output includes top-level 'pass' field."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(clean_run),
             "--history", str(history_file)],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert "pass" in data
        assert isinstance(data["pass"], bool)

    def test_quick_clean_run_passes(self, clean_run, tmp_path):
        """Clean run yields pass=True from CLI."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(clean_run),
             "--history", str(history_file)],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert data["pass"] is True

    def test_quick_overfit_run_fails(self, overfit_run, tmp_path):
        """Overfit run yields pass=False from CLI."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(overfit_run),
             "--history", str(history_file)],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert data["pass"] is False

    def test_quick_output_has_checks_list(self, clean_run, tmp_path):
        """CLI quick output includes 'checks' list with 6 entries."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(clean_run),
             "--history", str(history_file)],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert "checks" in data
        assert len(data["checks"]) == 6

    def test_quick_with_devnull_history(self, clean_run):
        """CLI quick mode accepts /dev/null as history (empty)."""
        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(clean_run),
             "--history", "/dev/null"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["history_entries"] == 0

    def test_quick_with_prev_run_dir(self, score_regression_runs, tmp_path):
        """CLI quick --prev-run-dir passes previous run for score regression."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")
        curr = score_regression_runs["curr"]
        prev = score_regression_runs["prev"]

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(curr),
             "--history", str(history_file),
             "--prev-run-dir", str(prev)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Sortino regressed 4.0 → 1.5 = FAIL → pass=False
        assert data["pass"] is False

    def test_full_outputs_json(self, clean_run, tmp_path):
        """CLI full mode outputs valid JSON to stdout."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")
        diff_file = tmp_path / "diff.txt"
        diff_file.write_text("--- a/src/mqe/config.py\n+++ b/src/mqe/config.py\n")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "full",
             "--run-dir", str(clean_run),
             "--history", str(history_file),
             "--git-diff-file", str(diff_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_full_output_has_quick_checks(self, clean_run, tmp_path):
        """CLI full output includes 'quick_checks' list."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")
        diff_file = tmp_path / "diff.txt"
        diff_file.write_text("")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "full",
             "--run-dir", str(clean_run),
             "--history", str(history_file),
             "--git-diff-file", str(diff_file)],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert "quick_checks" in data
        assert len(data["quick_checks"]) == 6

    def test_full_output_has_git_diff_chars(self, clean_run, tmp_path):
        """CLI full output includes git_diff_chars count."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")
        diff_content = "some diff content"
        diff_file = tmp_path / "diff.txt"
        diff_file.write_text(diff_content)

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "full",
             "--run-dir", str(clean_run),
             "--history", str(history_file),
             "--git-diff-file", str(diff_file)],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert "git_diff_chars" in data
        assert data["git_diff_chars"] == len(diff_content)

    def test_full_with_missing_diff_file(self, clean_run, tmp_path):
        """CLI full mode handles missing diff file gracefully (0 chars)."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "full",
             "--run-dir", str(clean_run),
             "--history", str(history_file),
             "--git-diff-file", str(tmp_path / "nonexistent.diff")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["git_diff_chars"] == 0

    def test_quick_missing_run_dir_errors(self, tmp_path):
        """CLI quick mode exits non-zero for missing run directory."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")

        result = subprocess.run(
            [sys.executable, CRITIC_PY, "quick",
             "--run-dir", str(tmp_path / "nonexistent"),
             "--history", str(history_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_load_history_devnull_returns_empty(self):
        """_load_history returns [] for /dev/null."""
        assert _load_history("/dev/null") == []

    def test_load_history_nonexistent_returns_empty(self, tmp_path):
        """_load_history returns [] for nonexistent file."""
        assert _load_history(str(tmp_path / "missing.json")) == []

    def test_load_history_reads_entries(self, tmp_path):
        """_load_history reads JSON array from file."""
        h_file = tmp_path / "history.json"
        h_file.write_text('[{"iteration": 1, "result": "promote"}]')
        history = _load_history(str(h_file))
        assert len(history) == 1
        assert history[0]["iteration"] == 1
