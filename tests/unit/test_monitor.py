"""Unit tests for MQE Monitor."""

import json
from pathlib import Path

import pytest

from mqe.monitor import RunInfo, load_run, scan_results, render_table


# ─── helpers ────────────────────────────────────────────────────────────────


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def _make_completed_run(run_dir: Path, tag: str = "test", n_symbols: int = 3) -> None:
    """Create a minimal completed run directory."""
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"][:n_symbols]

    pipeline = {
        "symbols": symbols,
        "stage1_trials": 1000,
        "stage2_trials": 500,
        "tag": tag,
        "hours": 8760,
        "timestamp": "2026-02-28 12:00:00",
        "stage1_results": {
            sym: {
                "symbol": sym,
                "objective_value": 2.5,
                "sharpe_equity": 1.5,
                "max_drawdown": -5.0,
                "total_pnl_pct": 10.0,
                "trades_per_year": 80.0,
            }
            for sym in symbols
        },
    }
    _write_json(run_dir / "pipeline_result.json", pipeline)

    s2 = {
        "portfolio_params": {
            "max_concurrent": 5,
            "cluster_max": 2,
            "portfolio_heat": 0.05,
            "corr_gate_threshold": 0.75,
        },
        "objectives": {
            "portfolio_calmar": 5.0,
            "worst_pair_calmar": 1.2,
            "neg_overfit_penalty": 0.0,
        },
        "n_trials": 500,
        "pareto_front_size": 5,
    }
    _write_json(run_dir / "stage2_result.json", s2)

    metrics = {
        "sharpe_ratio_equity_based": 2.5,
        "calmar_ratio": 8.0,
        "max_drawdown": -3.5,
        "total_pnl_pct": 25.0,
        "trades": 500,
        "equity": 62500.0,
    }
    _write_json(run_dir / "evaluation" / "portfolio_metrics.json", metrics)

    # Stage 1 files
    s1_dir = run_dir / "stage1"
    s1_dir.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        safe = sym.replace("/", "_")
        _write_json(s1_dir / f"{safe}.json", {"symbol": sym})


def _make_running_run(run_dir: Path, n_pairs_done: int = 5) -> None:
    """Create a minimal running run directory (no pipeline_result.json)."""
    s1_dir = run_dir / "stage1"
    s1_dir.mkdir(parents=True, exist_ok=True)
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT",
               "LINK/USDT", "SUI/USDT", "AVAX/USDT"]
    for sym in symbols[:n_pairs_done]:
        safe = sym.replace("/", "_")
        _write_json(s1_dir / f"{safe}.json", {
            "symbol": sym,
            "n_trials_requested": 10000,
        })


# ─── load_run ───────────────────────────────────────────────────────────────


class TestLoadRun:
    def test_completed_run(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_120000"
        _make_completed_run(run_dir)

        info = load_run(run_dir)
        assert info is not None
        assert info.status == "completed"
        assert info.n_symbols == 3
        assert info.tag == "test"
        assert info.s1_trials == 1000
        assert info.s2_trials == 500
        assert info.portfolio_sharpe == 2.5
        assert info.portfolio_calmar == 8.0
        assert info.portfolio_dd == -3.5
        assert info.portfolio_pnl == 25.0
        assert info.portfolio_trades == 500
        assert info.portfolio_equity == 62500.0

    def test_running_run(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_130000"
        _make_running_run(run_dir, n_pairs_done=5)

        info = load_run(run_dir)
        assert info is not None
        assert info.status == "running"
        assert info.s1_completed == 5
        assert info.s1_trials == 10000

    def test_empty_dir_returns_none(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_140000"
        run_dir.mkdir()

        info = load_run(run_dir)
        assert info is None

    def test_nonexistent_dir_returns_none(self, tmp_path: Path) -> None:
        info = load_run(tmp_path / "nonexistent")
        assert info is None

    def test_verdicts(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_150000"
        _make_completed_run(run_dir)
        info = load_run(run_dir)
        assert info is not None
        # All 3 pairs have Sharpe 1.5, trades 80, DD 5% -> all PASS
        assert info.n_pass == 3
        assert info.n_warn == 0
        assert info.n_fail == 0


# ─── scan_results ───────────────────────────────────────────────────────────


class TestScanResults:
    def test_scan_mixed(self, tmp_path: Path) -> None:
        _make_completed_run(tmp_path / "20260228_120000", tag="run-a")
        _make_completed_run(tmp_path / "20260228_130000", tag="run-b")
        _make_running_run(tmp_path / "20260228_140000", n_pairs_done=3)
        # Empty dir — should be skipped
        (tmp_path / "20260228_150000").mkdir()

        runs = scan_results(tmp_path)
        assert len(runs) == 3

    def test_scan_with_filter(self, tmp_path: Path) -> None:
        _make_completed_run(tmp_path / "20260228_120000", tag="smoke")
        _make_completed_run(tmp_path / "20260228_130000", tag="main")

        runs = scan_results(tmp_path, name_filter="smoke")
        assert len(runs) == 1
        assert runs[0].tag == "smoke"

    def test_scan_empty(self, tmp_path: Path) -> None:
        runs = scan_results(tmp_path)
        assert len(runs) == 0

    def test_scan_nonexistent(self, tmp_path: Path) -> None:
        runs = scan_results(tmp_path / "nope")
        assert len(runs) == 0


# ─── render_table ───────────────────────────────────────────────────────────


class TestRenderTable:
    def test_render_completed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_120000"
        _make_completed_run(run_dir)
        info = load_run(run_dir)
        table = render_table([info])
        assert table.row_count == 1

    def test_render_running(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_130000"
        _make_running_run(run_dir)
        info = load_run(run_dir)
        table = render_table([info])
        assert table.row_count == 1

    def test_render_empty(self) -> None:
        table = render_table([])
        assert table.row_count == 0
