"""Unit tests for MQE Monitor."""

import json
from pathlib import Path

import pytest

from mqe.monitor import (
    RunInfo, load_run, scan_results, render_table,
    LivePairStatus, load_live_run, render_live_table, find_active_run,
    _format_elapsed, _progress_bar,
)


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
               "LINK/USDT", "SUI/USDT", "DOT/USDT"]
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


# ─── _format_elapsed ────────────────────────────────────────────────────────


class TestFormatElapsed:
    def test_hours_and_minutes(self) -> None:
        assert _format_elapsed(6120) == "1h42m"

    def test_minutes_only(self) -> None:
        assert _format_elapsed(300) == "5m"

    def test_zero(self) -> None:
        assert _format_elapsed(0) == "0m"

    def test_large_hours(self) -> None:
        assert _format_elapsed(36000) == "10h00m"


# ─── _progress_bar ──────────────────────────────────────────────────────────


class TestProgressBar:
    def test_full(self) -> None:
        bar = _progress_bar(100, 100, width=8)
        assert bar == "\u2588" * 8

    def test_empty(self) -> None:
        bar = _progress_bar(0, 100, width=8)
        assert bar == "\u2591" * 8

    def test_half(self) -> None:
        bar = _progress_bar(50, 100, width=8)
        assert bar == "\u2588" * 4 + "\u2591" * 4

    def test_zero_total(self) -> None:
        bar = _progress_bar(0, 0, width=8)
        assert bar == " " * 8

    def test_over_100_clamped(self) -> None:
        bar = _progress_bar(200, 100, width=8)
        assert bar == "\u2588" * 8


# ─── load_live_run ──────────────────────────────────────────────────────────


class TestLoadLiveRun:
    def test_detects_running_pairs(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_210000"
        s1_dir = run_dir / "stage1"
        s1_dir.mkdir(parents=True)

        # One completed pair
        _write_json(s1_dir / "BTC_USDT.json", {
            "symbol": "BTC/USDT",
            "objective_value": 3.45,
            "sharpe_equity": 2.81,
            "max_drawdown": -4.2,
            "n_trials_completed": 50000,
            "n_trials_requested": 50000,
        })

        # One running pair
        _write_json(s1_dir / "ETH_USDT_progress.json", {
            "symbol": "ETH/USDT",
            "trials_completed": 31000,
            "trials_total": 50000,
            "best_value": 2.91,
            "best_sharpe": 2.34,
            "best_drawdown": -6.1,
            "best_trades": 98,
            "best_pnl_pct": 35.0,
            "timestamp": "2026-02-28T22:15:30",
        })

        pairs = load_live_run(run_dir)
        assert len(pairs) == 2

        btc = next(p for p in pairs if p.symbol == "BTC/USDT")
        assert btc.status == "done"
        assert btc.trials_completed == 50000

        eth = next(p for p in pairs if p.symbol == "ETH/USDT")
        assert eth.status == "running"
        assert eth.trials_completed == 31000
        assert eth.best_sharpe == 2.34

    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_220000"
        run_dir.mkdir(parents=True)
        pairs = load_live_run(run_dir)
        assert pairs == []

    def test_no_stage1_dir_returns_empty(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_230000"
        run_dir.mkdir(parents=True)
        pairs = load_live_run(run_dir)
        assert pairs == []

    def test_done_pairs_sorted_first(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "20260228_210000"
        s1_dir = run_dir / "stage1"
        s1_dir.mkdir(parents=True)

        _write_json(s1_dir / "ETH_USDT_progress.json", {
            "symbol": "ETH/USDT",
            "trials_completed": 10000,
            "trials_total": 50000,
            "best_value": 1.0,
            "best_sharpe": 1.0,
            "best_drawdown": -5.0,
            "best_trades": 50,
            "best_pnl_pct": 10.0,
            "timestamp": "2026-02-28T22:00:00",
        })

        _write_json(s1_dir / "BTC_USDT.json", {
            "symbol": "BTC/USDT",
            "objective_value": 3.0,
            "sharpe_equity": 2.0,
            "max_drawdown": -3.0,
            "n_trials_completed": 50000,
            "n_trials_requested": 50000,
        })

        pairs = load_live_run(run_dir)
        assert pairs[0].status == "done"
        assert pairs[1].status == "running"

    def test_pending_pairs_for_missing_symbols(self, tmp_path: Path) -> None:
        """Pairs with neither done nor progress file are not listed (no way to know)."""
        run_dir = tmp_path / "20260228_210000"
        s1_dir = run_dir / "stage1"
        s1_dir.mkdir(parents=True)

        _write_json(s1_dir / "BTC_USDT.json", {
            "symbol": "BTC/USDT",
            "objective_value": 3.0,
            "sharpe_equity": 2.0,
            "max_drawdown": -3.0,
            "n_trials_completed": 50000,
            "n_trials_requested": 50000,
        })

        pairs = load_live_run(run_dir)
        assert len(pairs) == 1


# ─── render_live_table ──────────────────────────────────────────────────────


class TestRenderLiveTable:
    def test_render_with_pairs(self) -> None:
        pairs = [
            LivePairStatus(
                symbol="BTC/USDT", status="done",
                trials_completed=50000, trials_total=50000,
                best_value=3.45, best_sharpe=2.81, best_drawdown=-4.2,
            ),
            LivePairStatus(
                symbol="ETH/USDT", status="running",
                trials_completed=31000, trials_total=50000,
                best_value=2.91, best_sharpe=2.34, best_drawdown=-6.1,
            ),
        ]
        table = render_live_table(pairs, tag="15pair-50k", elapsed_s=6120)
        assert table is not None
        assert table.row_count == 2

    def test_render_empty_list(self) -> None:
        table = render_live_table([], tag="test", elapsed_s=0)
        assert table is not None
        assert table.row_count == 0

    def test_render_with_pending(self) -> None:
        pairs = [
            LivePairStatus(symbol="BTC/USDT", status="pending"),
        ]
        table = render_live_table(pairs, tag="test", elapsed_s=60)
        assert table is not None
        assert table.row_count == 1


# ─── find_active_run ────────────────────────────────────────────────────────


class TestFindActiveRun:
    def test_finds_running_run(self, tmp_path: Path) -> None:
        # Completed run
        completed = tmp_path / "20260228_120000"
        completed.mkdir()
        _write_json(completed / "pipeline_result.json", {"symbols": []})

        # Running run (no pipeline_result.json, has stage1/)
        running = tmp_path / "20260228_210000"
        s1_dir = running / "stage1"
        s1_dir.mkdir(parents=True)
        _write_json(s1_dir / "BTC_USDT.json", {"symbol": "BTC/USDT"})

        result = find_active_run(tmp_path)
        assert result is not None
        assert result.name == "20260228_210000"

    def test_returns_none_when_all_complete(self, tmp_path: Path) -> None:
        completed = tmp_path / "20260228_120000"
        completed.mkdir()
        _write_json(completed / "pipeline_result.json", {"symbols": []})

        result = find_active_run(tmp_path)
        assert result is None

    def test_returns_none_for_empty_dir(self, tmp_path: Path) -> None:
        result = find_active_run(tmp_path)
        assert result is None

    def test_picks_most_recent(self, tmp_path: Path) -> None:
        # Two running runs — should pick most recent
        older = tmp_path / "20260228_100000"
        (older / "stage1").mkdir(parents=True)
        _write_json(older / "stage1" / "BTC_USDT.json", {"symbol": "BTC/USDT"})

        newer = tmp_path / "20260228_200000"
        (newer / "stage1").mkdir(parents=True)
        _write_json(newer / "stage1" / "ETH_USDT.json", {"symbol": "ETH/USDT"})

        result = find_active_run(tmp_path)
        assert result is not None
        assert result.name == "20260228_200000"
