"""Tests for mqe.compare — cross-run comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mqe.compare import (
    compare_runs,
    generate_comparison_markdown,
    load_run,
)


# ─── FIXTURES ─────────────────────────────────────────────────────────────────


def _pipeline_result(tag: str = "run-A", symbols: list[str] | None = None) -> dict:
    if symbols is None:
        symbols = ["BTC/USDT", "ETH/USDT"]
    return {
        "tag": tag,
        "timestamp": "2026-02-28 12:00:00",
        "symbols": symbols,
        "stage1_trials": 100,
        "stage2_trials": 50,
        "hours": 8760,
        "stage1_results": {
            sym: {
                "metrics": {
                    "trades_per_year": 80,
                    "sharpe_equity": 1.5,
                    "calmar": 3.0,
                    "max_drawdown_pct": 5.0,
                    "win_rate": 0.55,
                },
            }
            for sym in symbols
        },
        "stage2_results": {
            "objectives": {
                "portfolio_calmar": 3.0,
                "worst_pair_calmar": 1.5,
            },
            "portfolio_params": {
                "max_concurrent": 3,
                "cluster_max": 2,
                "portfolio_heat": 0.05,
                "corr_gate_threshold": 0.75,
            },
        },
    }


def _eval_metrics() -> dict:
    return {
        "BTC/USDT": {
            "trades_per_year": 100.0,
            "sharpe_ratio_equity_based": 1.8,
            "calmar_ratio": 4.0,
            "max_drawdown": -6.0,
            "win_rate": 55.0,
            "sortino_ratio": 2.5,
            "profit_factor": 1.8,
            "total_pnl_pct": 25.0,
            "trades": 100,
            "expectancy": 50.0,
        },
        "ETH/USDT": {
            "trades_per_year": 90.0,
            "sharpe_ratio_equity_based": 1.6,
            "calmar_ratio": 3.5,
            "max_drawdown": -7.0,
            "win_rate": 52.0,
            "sortino_ratio": 2.0,
            "profit_factor": 1.5,
            "total_pnl_pct": 20.0,
            "trades": 90,
            "expectancy": 40.0,
        },
    }


def _portfolio_metrics() -> dict:
    return {
        "trades_per_year": 180.0,
        "sharpe_ratio_equity_based": 1.7,
        "calmar_ratio": 3.2,
        "max_drawdown": -5.5,
        "win_rate": 53.0,
        "sortino_ratio": 2.2,
        "profit_factor": 1.6,
        "total_pnl_pct": 35.0,
        "trades": 180,
        "expectancy": 45.0,
    }


def _create_run_dir(
    tmp_path: Path,
    name: str,
    tag: str = "",
    with_eval: bool = True,
) -> Path:
    """Create a mock run directory with JSON files."""
    run_dir = tmp_path / name
    run_dir.mkdir()

    symbols = ["BTC/USDT", "ETH/USDT"]
    pr = _pipeline_result(tag=tag, symbols=symbols)
    (run_dir / "pipeline_result.json").write_text(
        json.dumps(pr, indent=2), encoding="utf-8"
    )

    if with_eval:
        eval_dir = run_dir / "evaluation"
        eval_dir.mkdir()
        (eval_dir / "per_pair_metrics.json").write_text(
            json.dumps(_eval_metrics(), indent=2), encoding="utf-8"
        )
        (eval_dir / "portfolio_metrics.json").write_text(
            json.dumps(_portfolio_metrics(), indent=2), encoding="utf-8"
        )

    return run_dir


# ─── LOAD_RUN TESTS ─────────────────────────────────────────────────────────


class TestLoadRun:
    """Tests for load_run()."""

    def test_loads_pipeline_result(self, tmp_path: Path):
        run_dir = _create_run_dir(tmp_path, "run1", tag="test-tag")
        result = load_run(run_dir)
        assert result["tag"] == "test-tag"
        assert result["timestamp"] == "2026-02-28 12:00:00"
        assert result["symbols"] == ["BTC/USDT", "ETH/USDT"]
        assert result["stage1_trials"] == 100

    def test_loads_eval_metrics(self, tmp_path: Path):
        run_dir = _create_run_dir(tmp_path, "run1", tag="A", with_eval=True)
        result = load_run(run_dir)
        assert "BTC/USDT" in result["per_pair_metrics"]
        assert result["portfolio_metrics"] is not None

    def test_handles_missing_eval_dir(self, tmp_path: Path):
        run_dir = _create_run_dir(tmp_path, "run1", tag="A", with_eval=False)
        result = load_run(run_dir)
        assert result["per_pair_metrics"] == {}
        assert result["portfolio_metrics"] is None

    def test_empty_tag_uses_dir_name(self, tmp_path: Path):
        run_dir = _create_run_dir(tmp_path, "20260228_120000", tag="")
        result = load_run(run_dir)
        assert result["tag"] == "20260228_120000"


# ─── COMPARE_RUNS TESTS ─────────────────────────────────────────────────────


class TestCompareRuns:
    """Tests for compare_runs()."""

    def test_two_runs_compared(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        d2 = _create_run_dir(tmp_path, "run2", tag="B")
        result = compare_runs([d1, d2])

        assert len(result["runs"]) == 2
        assert "BTC/USDT" in result["per_pair_comparison"]
        assert "ETH/USDT" in result["per_pair_comparison"]
        assert len(result["portfolio_comparison"]) == 2

    def test_per_pair_entries_per_run(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        d2 = _create_run_dir(tmp_path, "run2", tag="B")
        result = compare_runs([d1, d2])

        btc = result["per_pair_comparison"]["BTC/USDT"]
        assert len(btc) == 2
        assert btc[0]["run_tag"] == "A"
        assert btc[1]["run_tag"] == "B"

    def test_eval_metrics_preferred(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A", with_eval=True)
        result = compare_runs([d1])

        btc = result["per_pair_comparison"]["BTC/USDT"][0]
        # Eval metrics have sharpe=1.8, stage1 has sharpe=1.5
        assert btc["sharpe"] == 1.8

    def test_fallback_to_stage1(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A", with_eval=False)
        result = compare_runs([d1])

        btc = result["per_pair_comparison"]["BTC/USDT"][0]
        # Falls back to stage1: sharpe_equity=1.5
        assert btc["sharpe"] == 1.5

    def test_portfolio_comparison_has_calmar(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        result = compare_runs([d1])

        pc = result["portfolio_comparison"][0]
        assert pc["portfolio_calmar"] == 3.0
        assert pc["worst_pair_calmar"] == 1.5

    def test_portfolio_eval_metrics_included(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A", with_eval=True)
        result = compare_runs([d1])

        pc = result["portfolio_comparison"][0]
        assert pc["sharpe"] == 1.7  # from portfolio_metrics


# ─── MARKDOWN OUTPUT TESTS ──────────────────────────────────────────────────


class TestComparisonMarkdown:
    """Tests for generate_comparison_markdown()."""

    def test_markdown_not_empty(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        d2 = _create_run_dir(tmp_path, "run2", tag="B")
        comparison = compare_runs([d1, d2])
        md = generate_comparison_markdown(comparison)
        assert len(md) > 100

    def test_markdown_has_header(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        d2 = _create_run_dir(tmp_path, "run2", tag="B")
        comparison = compare_runs([d1, d2])
        md = generate_comparison_markdown(comparison)
        assert "# Cross-Run Comparison" in md
        assert "A vs B" in md

    def test_markdown_has_per_pair_section(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        comparison = compare_runs([d1])
        md = generate_comparison_markdown(comparison)
        assert "BTC/USDT" in md
        assert "ETH/USDT" in md
        assert "Sharpe" in md

    def test_markdown_has_portfolio_section(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        comparison = compare_runs([d1])
        md = generate_comparison_markdown(comparison)
        assert "## Portfolio Comparison" in md
        assert "Portfolio Calmar" in md

    def test_markdown_has_overview(self, tmp_path: Path):
        d1 = _create_run_dir(tmp_path, "run1", tag="A")
        comparison = compare_runs([d1])
        md = generate_comparison_markdown(comparison)
        assert "## Run Overview" in md
        assert "S1 Trials" in md
