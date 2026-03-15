"""Behavior tests for mqe.html_report.

Tests verify observable behavior (no crash, required sections present,
file output) — NOT internal HTML structure, CSS classes, or DOM details.
"""

from __future__ import annotations

import pytest

from mqe.html_report import generate_html_report, save_html_report


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def minimal_args():
    """Bare-minimum kwargs that generate_html_report accepts."""
    return dict(
        pipeline_result={
            "run_tag": "test-run-20260315",
            "timestamp": "2026-03-15T09:00:00",
            "symbols": ["BTC/USDT", "SOL/USDT"],
            "s1_trials": 100,
            "s2_trials": 50,
            "duration_hours": 2.5,
        },
        eval_result={},
        analysis={},
        portfolio_trades=[],
        per_pair_trades={},
        s1_top_trials={},
        s1_history={},
        pareto_front={},
        s2_history={},
        corr_matrix={},
        pair_equity_curves={},
        portfolio_equity_curve=[],
        timestamps=[],
    )


def _make_realistic_args(symbols=None):
    """Build a full set of report kwargs with realistic synthetic data."""
    if symbols is None:
        symbols = ["BTC/USDT", "ETH/USDT"]

    trades = [
        {
            "symbol": sym,
            "direction": "long",
            "entry_bar": i * 10,
            "exit_bar": i * 10 + 10,
            "entry_ts": f"2024-0{i + 1}-01T00:00:00",
            "exit_ts": f"2024-0{i + 1}-11T00:00:00",
            "entry_time": f"2024-0{i + 1}-01T00:00",
            "exit_time": f"2024-0{i + 1}-11T00:00",
            "entry_price": 40000 + i * 1000,
            "exit_price": 42000 + i * 1000,
            "hold_bars": 10,
            "size": 0.5,
            "capital_at_entry": 20000,
            "pnl_abs": 1000 + i * 500,
            "pnl_pct": 5.0 + i,
            "reason": "trailing_stop",
        }
        for i, sym in enumerate(symbols)
    ]

    per_pair_trades = {}
    for t in trades:
        per_pair_trades.setdefault(t["symbol"], []).append(t)

    per_pair_metrics = {}
    for i, sym in enumerate(symbols):
        per_pair_metrics[sym] = {
            "sharpe_ratio_equity_based": 1.8 + i * 0.3,
            "calmar_ratio": 4.5 - i * 0.5,
            "max_drawdown": 0.06 + i * 0.01,
            "win_rate": 62.0 - i * 2,
            "profit_factor": 1.8 - i * 0.1,
            "trades_per_year": 90 - i * 10,
            "total_pnl_pct": 45.0 - i * 5,
            "trades": 180 - i * 20,
        }

    equity_curve = [100000, 101000, 101500, 102000, 103000]
    timestamps = [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]

    return dict(
        pipeline_result={
            "run_tag": "behavior-test",
            "timestamp": "2026-03-15T10:00:00",
            "symbols": symbols,
            "s1_trials": 500,
            "s2_trials": 200,
            "duration_hours": 3.0,
            "stage1_results": {
                sym: {
                    "macd_fast": 2.1 + i,
                    "macd_slow": 28 + i,
                    "macd_signal": 9,
                    "rsi_period": 14,
                    "rsi_lower": 30,
                    "rsi_upper": 70,
                    "rsi_lookback": 4,
                    "trend_tf": "4h",
                    "adx_threshold": 25,
                    "trail_mult": 2.0,
                    "hard_stop_mult": 3.0,
                    "max_hold_bars": 48,
                    "allow_flip": 0,
                    "trend_strict": 1,
                }
                for i, sym in enumerate(symbols)
            },
            "tier_assignments": {
                sym: {
                    "tier": "A" if i == 0 else "B",
                    "multiplier": 1.0 - i * 0.2,
                    "sharpe": 1.8 - i * 0.3,
                    "degradation": 0.3 + i * 0.2,
                    "consistency": 0.3,
                    "worst_sharpe": 0.9 - i * 0.2,
                }
                for i, sym in enumerate(symbols)
            },
            "analysis": {
                "per_pair": [
                    {"symbol": sym, "verdict": "PASS"} for sym in symbols
                ],
            },
            "wf_eval_metrics": {
                sym: {
                    "wf_sharpe_median": 1.5 - i * 0.3,
                    "wf_sharpe_std": 0.3 + i * 0.1,
                    "wf_worst_sharpe": 0.9 - i * 0.3,
                    "degradation_ratio": 0.3 + i * 0.2,
                    "n_windows": 3,
                }
                for i, sym in enumerate(symbols)
            },
        },
        eval_result={
            "per_pair_metrics": per_pair_metrics,
            "portfolio_metrics": {
                "sharpe_ratio_equity_based": 2.14,
                "calmar_ratio": 5.82,
                "total_pnl_pct": 48.7,
            },
            "portfolio_result_summary": {
                "equity": 148742,
                "max_drawdown": 0.083,
                "total_trades": 338,
            },
        },
        analysis={"per_pair": [], "portfolio": {"verdict": "PASS"}},
        portfolio_trades=trades,
        per_pair_trades=per_pair_trades,
        s1_top_trials={},
        s1_history={},
        pareto_front={
            "selected_trial": 1,
            "trials": [
                {
                    "number": 1,
                    "params": {"max_concurrent": 6},
                    "objectives": {
                        "portfolio_calmar": 5.21,
                        "worst_pair_calmar": 0.83,
                        "neg_overfit_penalty": -0.01,
                    },
                }
            ],
        },
        s2_history={
            "trial_numbers": [0, 1, 2],
            "portfolio_calmar_values": [1.0, 2.0, 5.21],
            "best_calmar_so_far": [1.0, 2.0, 5.21],
        },
        corr_matrix={
            "symbols": symbols,
            "matrix": [[1.0, 0.65], [0.65, 1.0]] if len(symbols) == 2 else [],
            "corr_gate_threshold": 0.72,
        },
        pair_equity_curves={},
        portfolio_equity_curve=equity_curve,
        timestamps=timestamps,
    )


# ─── Behavior Tests ─────────────────────────────────────────────────


class TestGenerateReportNoCrash:
    """Main generation function runs without error on valid input."""

    def test_returns_non_empty_string(self, minimal_args):
        html = generate_html_report(**minimal_args)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_realistic_data_no_crash(self):
        html = generate_html_report(**_make_realistic_args())
        assert isinstance(html, str)
        assert len(html) > 1000


class TestReportContainsRequiredSections:
    """Output contains key section headings / structural markers."""

    def test_section_headings_present(self):
        html = generate_html_report(**_make_realistic_args())
        expected_sections = [
            "Portfolio Overview",
            "Stage 1",
            "Stage 2",
            "Trade Analysis",
        ]
        for section in expected_sections:
            assert section in html, f"Missing section: {section}"

    def test_run_tag_appears(self, minimal_args):
        html = generate_html_report(**minimal_args)
        assert "test-run-20260315" in html

    def test_symbol_names_appear(self):
        html = generate_html_report(**_make_realistic_args(["BTC/USDT", "SOL/USDT"]))
        assert "BTC/USDT" in html
        assert "SOL/USDT" in html

    def test_plotly_cdn_included(self, minimal_args):
        html = generate_html_report(**minimal_args)
        assert "plotly" in html.lower()


class TestReportEmptyData:
    """Handles empty / missing data gracefully (no crash)."""

    def test_all_empty(self, minimal_args):
        html = generate_html_report(**minimal_args)
        assert "<!DOCTYPE html>" in html

    def test_empty_eval_result(self, minimal_args):
        minimal_args["eval_result"] = {}
        html = generate_html_report(**minimal_args)
        assert isinstance(html, str)

    def test_empty_pipeline_result(self):
        html = generate_html_report(
            pipeline_result={},
            eval_result={},
            analysis={},
            portfolio_trades=[],
            per_pair_trades={},
            s1_top_trials={},
            s1_history={},
            pareto_front={},
            s2_history={},
            corr_matrix={},
            pair_equity_curves={},
            portfolio_equity_curve=[],
            timestamps=[],
        )
        assert isinstance(html, str)


class TestReportSinglePair:
    """Works correctly with just 1 pair."""

    def test_single_pair_no_crash(self):
        html = generate_html_report(**_make_realistic_args(["BTC/USDT"]))
        assert isinstance(html, str)
        assert "BTC/USDT" in html

    def test_single_pair_has_sections(self):
        html = generate_html_report(**_make_realistic_args(["BTC/USDT"]))
        assert "Portfolio Overview" in html
        assert "Stage 1" in html


class TestReportMultiPair:
    """Works correctly with multiple pairs."""

    def test_two_pairs(self):
        symbols = ["BTC/USDT", "ETH/USDT"]
        html = generate_html_report(**_make_realistic_args(symbols))
        for sym in symbols:
            assert sym in html

    def test_five_pairs(self):
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT"]
        args = _make_realistic_args(symbols)
        # Correlation matrix must match the symbol count
        n = len(symbols)
        args["corr_matrix"] = {
            "symbols": symbols,
            "matrix": [[1.0 if i == j else 0.5 for j in range(n)] for i in range(n)],
            "corr_gate_threshold": 0.72,
        }
        html = generate_html_report(**args)
        for sym in symbols:
            assert sym in html


class TestReportMissingMetrics:
    """Handles partial / incomplete metrics without crash."""

    def test_partial_eval_result(self, minimal_args):
        minimal_args["eval_result"] = {
            "portfolio_result_summary": {"equity": 150000},
            # missing portfolio_metrics, per_pair_metrics
        }
        html = generate_html_report(**minimal_args)
        assert isinstance(html, str)

    def test_partial_pipeline_result(self, minimal_args):
        minimal_args["pipeline_result"] = {"run_tag": "partial-test"}
        html = generate_html_report(**minimal_args)
        assert "partial-test" in html

    def test_missing_per_pair_metrics(self):
        args = _make_realistic_args()
        args["eval_result"]["per_pair_metrics"] = {}
        html = generate_html_report(**args)
        assert isinstance(html, str)


class TestReportMetricsPresent:
    """Key numeric metrics from eval_result appear in the output."""

    def test_hero_metrics_values(self):
        html = generate_html_report(**_make_realistic_args())
        # Portfolio equity and key metrics should be rendered somewhere
        assert "148,742" in html
        assert "5.82" in html  # calmar

    def test_hero_section_labels(self):
        html = generate_html_report(**_make_realistic_args())
        # Key metric labels should appear
        assert "Sharpe" in html
        assert "Calmar" in html


class TestReportFileWritten:
    """When given output path, file is created with valid HTML."""

    def test_file_created(self, tmp_path, minimal_args):
        path = tmp_path / "report.html"
        save_html_report(path, **minimal_args)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>") or content.startswith("<html")

    def test_nested_dirs_created(self, tmp_path, minimal_args):
        path = tmp_path / "a" / "b" / "report.html"
        save_html_report(path, **minimal_args)
        assert path.exists()

    def test_realistic_file_non_empty(self, tmp_path):
        path = tmp_path / "full_report.html"
        save_html_report(path, **_make_realistic_args())
        content = path.read_text(encoding="utf-8")
        assert len(content) > 5000


class TestEquityCurveFromTrades:
    """Build equity curve helper produces correct results."""

    def test_empty_trades(self):
        from mqe.html_report import _build_equity_curve_from_trades

        assert _build_equity_curve_from_trades([]) == []

    def test_cumulative_pnl(self):
        from mqe.html_report import _build_equity_curve_from_trades

        trades = [
            {"exit_bar": 1, "pnl_abs": 1000},
            {"exit_bar": 2, "pnl_abs": -500},
            {"exit_bar": 3, "pnl_abs": 750},
        ]
        curve = _build_equity_curve_from_trades(trades, start_equity=100_000.0)
        assert curve[0] == 100_000.0
        assert curve[-1] == 101_250.0
        assert len(curve) == 4
