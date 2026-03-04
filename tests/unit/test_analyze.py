"""Tests for mqe.analyze — per-pair and portfolio health checks."""

from __future__ import annotations

import pytest

from mqe.analyze import _normalize_metrics, analyze_pair, analyze_portfolio, analyze_run


# ─── FIXTURES ─────────────────────────────────────────────────────────────────


def _good_metrics() -> dict:
    """Metrics that should produce PASS."""
    return {
        "trades_per_year": 80,
        "sharpe_equity": 1.5,
        "calmar": 3.0,
        "max_drawdown_pct": 5.0,
        "win_rate": 0.55,
    }


def _bad_metrics() -> dict:
    """Metrics that should produce FAIL."""
    return {
        "trades_per_year": 5,
        "sharpe_equity": 0.1,
        "calmar": 0.2,
        "max_drawdown_pct": 25.0,
        "win_rate": 0.30,
    }


def _warn_metrics() -> dict:
    """Metrics that should produce WARN (not FAIL, but concerning)."""
    return {
        "trades_per_year": 80,
        "sharpe_equity": 1.0,
        "calmar": 0.3,
        "max_drawdown_pct": 18.0,
        "win_rate": 0.45,
    }


def _good_stage2() -> dict:
    """Stage 2 result that should produce PASS."""
    return {
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
    }


def _bad_stage2() -> dict:
    """Stage 2 result that should produce FAIL."""
    return {
        "objectives": {
            "portfolio_calmar": 0.1,
            "worst_pair_calmar": 0.05,
        },
        "portfolio_params": {},
    }


# ─── PER-PAIR TESTS ──────────────────────────────────────────────────────────


class TestAnalyzePair:
    """Tests for analyze_pair()."""

    def test_good_metrics_produce_pass(self):
        result = analyze_pair("BTC/USDT", _good_metrics())
        assert result["verdict"] == "PASS"
        assert result["symbol"] == "BTC/USDT"
        assert result["failures"] == []

    def test_bad_metrics_produce_fail(self):
        result = analyze_pair("SOL/USDT", _bad_metrics())
        assert result["verdict"] == "FAIL"
        assert len(result["failures"]) > 0

    def test_warn_metrics_produce_warn(self):
        result = analyze_pair("ETH/USDT", _warn_metrics())
        assert result["verdict"] == "WARN"
        assert len(result["warnings"]) > 0

    def test_empty_trades_produces_fail(self):
        """No trades = trades_per_year=0 = FAIL."""
        metrics = {
            "trades_per_year": 0,
            "sharpe_equity": 0,
            "calmar": 0,
            "max_drawdown_pct": 0,
            "win_rate": 0,
        }
        result = analyze_pair("BTC/USDT", metrics)
        assert result["verdict"] == "FAIL"
        assert any("trades" in f.lower() for f in result["failures"])

    def test_suspect_sharpe_warns(self):
        """Sharpe above threshold produces warning."""
        metrics = _good_metrics()
        metrics["sharpe_equity"] = 5.0
        result = analyze_pair("BTC/USDT", metrics)
        assert any("suspiciously high" in w.lower() for w in result["warnings"])

    def test_metrics_summary_present(self):
        result = analyze_pair("BTC/USDT", _good_metrics())
        summary = result["metrics_summary"]
        assert "trades_per_year" in summary
        assert "sharpe" in summary
        assert "calmar" in summary
        assert "max_dd" in summary
        assert "win_rate" in summary

    def test_missing_metrics_default_to_zero(self):
        """Missing metrics should default to 0, resulting in FAIL."""
        result = analyze_pair("BTC/USDT", {})
        assert result["verdict"] == "FAIL"

    def test_low_sharpe_fails(self):
        """Sharpe < 0.5 = FAIL."""
        metrics = _good_metrics()
        metrics["sharpe_equity"] = 0.3
        result = analyze_pair("BTC/USDT", metrics)
        assert result["verdict"] == "FAIL"
        assert any("sharpe" in f.lower() for f in result["failures"])


# ─── PORTFOLIO TESTS ─────────────────────────────────────────────────────────


class TestAnalyzePortfolio:
    """Tests for analyze_portfolio()."""

    def test_good_portfolio_produces_pass(self):
        per_pair = [
            analyze_pair("BTC/USDT", _good_metrics()),
            analyze_pair("ETH/USDT", _good_metrics()),
            analyze_pair("SOL/USDT", _good_metrics()),
        ]
        result = analyze_portfolio(_good_stage2(), per_pair)
        assert result["verdict"] == "PASS"
        assert result["failures"] == []

    def test_bad_portfolio_calmar_fails(self):
        per_pair = [
            analyze_pair("BTC/USDT", _good_metrics()),
        ]
        result = analyze_portfolio(_bad_stage2(), per_pair)
        assert result["verdict"] == "FAIL"
        assert any("calmar" in f.lower() for f in result["failures"])

    def test_majority_pair_failures_fail_portfolio(self):
        """If more than half of pairs FAIL, portfolio should FAIL."""
        per_pair = [
            analyze_pair("BTC/USDT", _bad_metrics()),  # FAIL
            analyze_pair("ETH/USDT", _bad_metrics()),  # FAIL
            analyze_pair("SOL/USDT", _good_metrics()),  # PASS
        ]
        result = analyze_portfolio(_good_stage2(), per_pair)
        assert result["verdict"] == "FAIL"
        assert any("pairs failed" in f.lower() for f in result["failures"])

    def test_low_worst_pair_calmar_warns(self):
        stage2 = _good_stage2()
        stage2["objectives"]["worst_pair_calmar"] = 0.1
        per_pair = [analyze_pair("BTC/USDT", _good_metrics())]
        result = analyze_portfolio(stage2, per_pair)
        assert result["verdict"] == "WARN"
        assert any("worst pair" in w.lower() for w in result["warnings"])

    def test_portfolio_params_returned(self):
        per_pair = [analyze_pair("BTC/USDT", _good_metrics())]
        result = analyze_portfolio(_good_stage2(), per_pair)
        assert "portfolio_params" in result
        assert result["portfolio_params"]["max_concurrent"] == 3


# ─── ANALYZE_RUN TESTS ───────────────────────────────────────────────────────


class TestAnalyzeRun:
    """Tests for analyze_run() orchestrator."""

    def test_full_pipeline(self):
        """analyze_run with valid pipeline_result returns per_pair + portfolio."""
        pipeline_result = {
            "stage1_results": {
                "BTC/USDT": {"metrics": _good_metrics()},
                "ETH/USDT": {"metrics": _good_metrics()},
                "SOL/USDT": {"metrics": _warn_metrics()},
            },
            "stage2_results": _good_stage2(),
        }
        result = analyze_run(pipeline_result)
        assert "per_pair" in result
        assert "portfolio" in result
        assert len(result["per_pair"]) == 3
        # At least one WARN from SOL
        verdicts = [p["verdict"] for p in result["per_pair"]]
        assert "WARN" in verdicts

    def test_empty_stage1(self):
        """Empty stage1 results = empty per_pair list."""
        pipeline_result = {
            "stage1_results": {},
            "stage2_results": _good_stage2(),
        }
        result = analyze_run(pipeline_result)
        assert result["per_pair"] == []

    def test_all_pairs_fail(self):
        """All pairs failing should also fail portfolio (majority rule)."""
        pipeline_result = {
            "stage1_results": {
                "BTC/USDT": {"metrics": _bad_metrics()},
                "ETH/USDT": {"metrics": _bad_metrics()},
            },
            "stage2_results": _good_stage2(),
        }
        result = analyze_run(pipeline_result)
        # All pairs FAIL
        for pair_result in result["per_pair"]:
            assert pair_result["verdict"] == "FAIL"
        # Portfolio also FAIL because majority failed
        assert result["portfolio"]["verdict"] == "FAIL"

    def test_analyze_run_with_eval_result(self):
        """analyze_run uses eval_result metrics when provided."""
        pipeline_result = {
            "stage1_results": {
                "BTC/USDT": {"metrics": _bad_metrics()},
            },
            "stage2_results": _good_stage2(),
        }
        # eval_result overrides Stage 1 metrics with full backtest data
        eval_result = {
            "per_pair_metrics": {
                "BTC/USDT": _metrics_result_style(),
            },
            "portfolio_metrics": _metrics_result_style(),
        }
        result = analyze_run(pipeline_result, eval_result)
        # Should use eval metrics (PASS), not Stage 1 (FAIL)
        assert result["per_pair"][0]["verdict"] == "PASS"
        assert "portfolio_metrics" in result["portfolio"]


# ─── NORMALIZE METRICS TESTS ───────────────────────────────────────────────


def _metrics_result_style() -> dict:
    """Metrics dict matching MetricsResult key names."""
    return {
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
    }


class TestNormalizeMetrics:
    """Tests for _normalize_metrics()."""

    def test_legacy_keys(self):
        """Old format keys (sharpe_equity, calmar, max_drawdown_pct) work."""
        norm = _normalize_metrics(_good_metrics())
        assert norm["sharpe"] == 1.5
        assert norm["calmar"] == 3.0
        assert norm["max_dd"] == 5.0

    def test_metrics_result_keys(self):
        """MetricsResult-style keys work."""
        norm = _normalize_metrics(_metrics_result_style())
        assert norm["sharpe"] == 1.8
        assert norm["calmar"] == 4.0
        assert norm["max_dd"] == 6.0  # abs of -6.0
        assert norm["sortino"] == 2.5
        assert norm["profit_factor"] == 1.8

    def test_empty_dict_defaults_to_zero(self):
        """Empty dict produces all zeros."""
        norm = _normalize_metrics({})
        assert norm["sharpe"] == 0
        assert norm["calmar"] == 0
        assert norm["trades_per_year"] == 0

    def test_analyze_pair_with_metrics_result(self):
        """analyze_pair works with MetricsResult-style dict."""
        result = analyze_pair("BTC/USDT", _metrics_result_style())
        assert result["verdict"] == "PASS"
        assert result["metrics_summary"]["sharpe"] == 1.8
