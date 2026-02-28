"""Tests for mqe.report — Markdown report generation + Discord formatting."""

from __future__ import annotations

from pathlib import Path

import pytest

from mqe.analyze import analyze_pair, analyze_portfolio, analyze_run
from mqe.report import (
    format_discord_summary,
    generate_markdown_report,
    save_markdown_report,
)


# ─── FIXTURES ─────────────────────────────────────────────────────────────────


def _good_metrics() -> dict:
    return {
        "trades_per_year": 80,
        "sharpe_equity": 1.5,
        "calmar": 3.0,
        "max_drawdown_pct": 5.0,
        "win_rate": 0.55,
    }


def _good_stage2() -> dict:
    return {
        "objectives": {
            "portfolio_calmar": 3.0,
            "worst_pair_calmar": 1.5,
            "neg_overfit_penalty": -0.05,
        },
        "portfolio_params": {
            "max_concurrent": 3,
            "cluster_max": 2,
            "portfolio_heat": 0.05,
            "corr_gate_threshold": 0.75,
        },
    }


def _pipeline_result() -> dict:
    return {
        "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "stage1_trials": 100,
        "stage2_trials": 50,
        "hours": 8760,
        "tag": "test-run",
        "timestamp": "2026-02-28 12:00:00",
        "stage1_results": {
            "BTC/USDT": {
                "metrics": _good_metrics(),
                "macd_fast": 1.5,
                "macd_slow": 26,
                "macd_signal": 9,
                "rsi_period": 14,
                "rsi_lower": 30,
                "rsi_upper": 70,
                "rsi_lookback": 3,
                "trend_tf": 1,
                "adx_threshold": 25,
                "trail_mult": 3.0,
                "hard_stop_mult": 2.5,
                "max_hold_bars": 168,
            },
            "ETH/USDT": {
                "metrics": _good_metrics(),
                "macd_fast": 2.0,
                "macd_slow": 30,
                "macd_signal": 7,
                "rsi_period": 10,
                "rsi_lower": 25,
                "rsi_upper": 75,
                "rsi_lookback": 4,
                "trend_tf": 2,
                "adx_threshold": 20,
                "trail_mult": 2.8,
                "hard_stop_mult": 2.0,
                "max_hold_bars": 120,
            },
            "SOL/USDT": {
                "metrics": _good_metrics(),
                "macd_fast": 1.2,
                "macd_slow": 28,
                "macd_signal": 5,
                "rsi_period": 8,
                "rsi_lower": 35,
                "rsi_upper": 65,
                "rsi_lookback": 2,
                "trend_tf": 1,
                "adx_threshold": 30,
                "trail_mult": 3.5,
                "hard_stop_mult": 3.0,
                "max_hold_bars": 200,
            },
        },
        "stage2_results": _good_stage2(),
    }


def _eval_result() -> dict:
    return {
        "per_pair_metrics": {},
        "portfolio_metrics": {
            "trades_per_year": 200,
            "sharpe_ratio_equity_based": 1.6,
            "calmar_ratio": 2.5,
            "max_drawdown": -8.0,
            "win_rate": 52.0,
            "sortino_ratio": 2.0,
            "profit_factor": 1.5,
            "total_pnl_pct": 30.0,
            "trades": 200,
            "expectancy": 45.0,
        },
        "portfolio_result_summary": {
            "equity": 130000.0,
            "max_drawdown": 0.08,
            "total_trades": 200,
            "max_positions_open": 3,
            "peak_equity": 135000.0,
        },
    }


def _analysis() -> dict:
    """Pre-built analysis result with portfolio metrics."""
    pr = _pipeline_result()
    return analyze_run(pr, _eval_result())


# ─── MARKDOWN REPORT TESTS ──────────────────────────────────────────────────


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report()."""

    def test_report_not_empty(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert len(md) > 100

    def test_header_sections_present(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "# MQE Run Report" in md
        assert "test-run" in md
        assert "2026-02-28 12:00:00" in md
        assert "BTC/USDT" in md

    def test_per_pair_table_present(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "## Stage 1" in md
        assert "| Symbol |" in md
        assert "BTC/USDT" in md
        assert "ETH/USDT" in md
        assert "SOL/USDT" in md

    def test_params_table_present(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "### Parameters" in md
        assert "`macd_fast`" in md
        assert "`rsi_period`" in md

    def test_portfolio_section_present(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "## Stage 2" in md
        assert "Portfolio Calmar" in md
        assert "### Verdict" in md

    def test_portfolio_metrics_present(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "### Portfolio Metrics" in md
        assert "Sharpe" in md
        assert "Sortino" in md
        assert "Profit factor" in md

    def test_s2_params_present(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "`max_concurrent`" in md
        assert "`portfolio_heat`" in md

    def test_data_hours_formatted(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "8760h" in md
        assert "1.0yr" in md

    def test_trial_counts_present(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "100" in md  # s1_trials
        assert "50" in md   # s2_trials

    def test_portfolio_result_summary(self):
        md = generate_markdown_report(_pipeline_result(), _eval_result(), _analysis())
        assert "$130,000" in md
        assert "200" in md  # total trades


class TestSaveMarkdownReport:
    """Tests for save_markdown_report()."""

    def test_saves_file(self, tmp_path: Path):
        out = tmp_path / "report.md"
        save_markdown_report(
            out, _pipeline_result(), _eval_result(), _analysis(),
        )
        assert out.exists()
        content = out.read_text()
        assert "# MQE Run Report" in content

    def test_creates_parent_dirs(self, tmp_path: Path):
        out = tmp_path / "subdir" / "nested" / "report.md"
        save_markdown_report(
            out, _pipeline_result(), _eval_result(), _analysis(),
        )
        assert out.exists()


# ─── DISCORD FORMAT TESTS ──────────────────────────────────────────────────


class TestFormatDiscord:
    """Tests for format_discord_summary()."""

    def test_code_block_wrapping(self):
        result = format_discord_summary(_analysis())
        assert result.startswith("```")
        assert result.endswith("```")

    def test_contains_pair_data(self):
        result = format_discord_summary(_analysis())
        assert "BTC/USDT" in result
        assert "ETH/USDT" in result
        assert "SOL/USDT" in result

    def test_contains_portfolio_verdict(self):
        result = format_discord_summary(_analysis())
        assert "PORTFOLIO:" in result
        assert "PASS" in result

    def test_length_under_discord_limit(self):
        result = format_discord_summary(_analysis())
        assert len(result) <= 2000
