from __future__ import annotations

import pytest
from mqe.html_report import (
    generate_html_report,
    PLOTLY_CDN,
    _render_hero_metrics,
    _render_portfolio_equity_curve,
    _render_concurrent_positions,
    _build_equity_curve_from_trades,
    _render_per_pair_table,
    _render_per_pair_equity_curves,
    _render_tier_table,
    _render_wf_evaluation,
    _render_s1_params_table,
    _render_s1_bullet_chart,
    _render_s1_top_trials,
    _render_s1_optimization_history,
    _render_s2_params,
    _render_pareto_front,
    _render_s2_optimization_history,
    _render_pnl_contribution,
    _render_correlation_heatmap,
    _render_monthly_returns,
    _render_trade_analysis,
)


@pytest.fixture
def minimal_report_args():
    return dict(
        pipeline_result={"run_tag": "test-run-20260307", "timestamp": "2026-03-07T22:47:41", "symbols": ["BTC/USDT", "SOL/USDT"], "s1_trials": 100, "s2_trials": 50, "duration_hours": 2.5},
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


def test_returns_string(minimal_report_args):
    result = generate_html_report(**minimal_report_args)
    assert isinstance(result, str)


def test_contains_doctype(minimal_report_args):
    result = generate_html_report(**minimal_report_args)
    assert "<!DOCTYPE html>" in result


def test_contains_plotly_cdn(minimal_report_args):
    result = generate_html_report(**minimal_report_args)
    assert PLOTLY_CDN in result


def test_contains_tokyonight_color(minimal_report_args):
    result = generate_html_report(**minimal_report_args)
    assert "#222436" in result


def test_contains_run_tag(minimal_report_args):
    result = generate_html_report(**minimal_report_args)
    assert "test-run-20260307" in result


def test_contains_section_dividers(minimal_report_args):
    result = generate_html_report(**minimal_report_args)
    assert "Stage 1 — Per-Pair" in result
    assert "Stage 2 — Portfolio" in result
    assert "Trade Analysis" in result


# ─── Hero Metrics Tests ───


@pytest.fixture
def eval_result_with_metrics():
    return {
        "portfolio_result_summary": {
            "equity": 148742.27,
            "max_drawdown": 0.083,
            "total_trades": 338,
        },
        "portfolio_metrics": {
            "total_pnl_pct": 48.74,
            "calmar_ratio": 5.82,
            "sharpe_ratio_equity_based": 3.92,
        },
    }


def test_hero_metrics_renders_6_cards(eval_result_with_metrics):
    html = _render_hero_metrics({}, eval_result_with_metrics, {})
    assert html.count('class="hero-card"') == 6


def test_hero_metrics_contains_specific_values(eval_result_with_metrics):
    html = _render_hero_metrics({}, eval_result_with_metrics, {})
    assert "$148,742.27" in html
    assert "+48.7%" in html
    assert "5.82" in html
    assert "3.92" in html
    assert "-8.3%" in html
    assert "338" in html


def test_hero_metrics_positive_pnl_class(eval_result_with_metrics):
    html = _render_hero_metrics({}, eval_result_with_metrics, {})
    assert "positive" in html


def test_hero_metrics_negative_pnl_class():
    eval_result = {
        "portfolio_metrics": {"total_pnl_pct": -12.5},
        "portfolio_result_summary": {},
    }
    html = _render_hero_metrics({}, eval_result, {})
    assert "negative" in html


def test_hero_metrics_dd_warning_class():
    eval_result = {
        "portfolio_result_summary": {"max_drawdown": 0.04},
        "portfolio_metrics": {},
    }
    html = _render_hero_metrics({}, eval_result, {})
    assert "warning" in html


def test_hero_metrics_dd_negative_class():
    eval_result = {
        "portfolio_result_summary": {"max_drawdown": 0.08},
        "portfolio_metrics": {},
    }
    html = _render_hero_metrics({}, eval_result, {})
    assert "negative" in html


def test_hero_metrics_empty_data_no_crash():
    html = _render_hero_metrics({}, {}, {})
    assert 'class="hero-grid"' in html
    assert html.count('class="hero-card"') == 6


# ─── Portfolio Equity Curve Tests ───


def test_portfolio_equity_curve_empty_data():
    html = _render_portfolio_equity_curve([], [])
    assert "no-data" in html
    assert "No equity data available" in html


def test_portfolio_equity_curve_has_plotly():
    equity = [100000, 102000, 101000, 105000, 103000]
    ts = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    html = _render_portfolio_equity_curve(equity, ts)
    assert "Plotly.newPlot" in html


def test_portfolio_equity_curve_contains_equity_trace():
    equity = [100000, 102000, 101000, 105000, 103000]
    ts = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    html = _render_portfolio_equity_curve(equity, ts)
    assert "'Equity'" in html


def test_portfolio_equity_curve_contains_hwm_trace():
    equity = [100000, 102000, 101000, 105000, 103000]
    ts = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    html = _render_portfolio_equity_curve(equity, ts)
    assert "High-Water Mark" in html


def test_portfolio_equity_curve_contains_drawdown_trace():
    equity = [100000, 102000, 101000, 105000, 103000]
    ts = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    html = _render_portfolio_equity_curve(equity, ts)
    assert "Drawdown" in html


def test_portfolio_equity_curve_div_id():
    equity = [100000, 102000]
    html = _render_portfolio_equity_curve(equity, ["2026-01-01", "2026-01-02"])
    assert 'id="portfolio-equity-chart"' in html


def test_portfolio_equity_curve_without_timestamps():
    equity = [100000, 102000, 101000]
    html = _render_portfolio_equity_curve(equity, [])
    assert "Plotly.newPlot" in html


# ─── Concurrent Positions Tests ───


def test_concurrent_positions_empty_trades():
    html = _render_concurrent_positions([], [])
    assert "no-data" in html
    assert "No trade data available" in html


def test_concurrent_positions_has_plotly():
    trades = [
        {"entry_time": "2026-01-01T00:00", "exit_time": "2026-01-02T00:00"},
        {"entry_time": "2026-01-01T12:00", "exit_time": "2026-01-03T00:00"},
    ]
    html = _render_concurrent_positions(trades, [])
    assert "Plotly.newPlot" in html


def test_concurrent_positions_div_id():
    trades = [
        {"entry_time": "2026-01-01T00:00", "exit_time": "2026-01-02T00:00"},
    ]
    html = _render_concurrent_positions(trades, [])
    assert 'id="concurrent-positions-chart"' in html


def test_concurrent_positions_max_concurrent_line():
    trades = [
        {"entry_time": "2026-01-01T00:00", "exit_time": "2026-01-03T00:00"},
        {"entry_time": "2026-01-01T12:00", "exit_time": "2026-01-02T00:00"},
        {"entry_time": "2026-01-01T12:00", "exit_time": "2026-01-04T00:00"},
    ]
    html = _render_concurrent_positions(trades, [])
    assert "Max Concurrent" in html
    # Max concurrent should be 3 (all 3 trades overlap at 2026-01-01T12:00)
    assert "maxConc = 3" in html


def test_concurrent_positions_no_valid_timestamps():
    trades = [{"symbol": "BTC/USDT"}]  # No entry/exit times
    html = _render_concurrent_positions(trades, [])
    assert "no-data" in html


# ─── Equity Curve From Trades Helper (Task 11) ───


def test_build_equity_curve_empty_list():
    result = _build_equity_curve_from_trades([])
    assert result == []


def test_build_equity_curve_monotonic_for_all_wins():
    trades = [
        {"exit_bar": 1, "pnl_abs": 500},
        {"exit_bar": 2, "pnl_abs": 300},
        {"exit_bar": 3, "pnl_abs": 200},
    ]
    curve = _build_equity_curve_from_trades(trades, start_equity=100_000.0)
    assert len(curve) == 4  # start + 3 trades
    for i in range(1, len(curve)):
        assert curve[i] >= curve[i - 1]


def test_build_equity_curve_correct_final_value():
    trades = [
        {"exit_bar": 1, "pnl_abs": 1000},
        {"exit_bar": 2, "pnl_abs": -500},
        {"exit_bar": 3, "pnl_abs": 750},
    ]
    curve = _build_equity_curve_from_trades(trades, start_equity=100_000.0)
    assert curve[-1] == 101_250.0


def test_build_equity_curve_custom_start_equity():
    trades = [{"exit_bar": 1, "pnl_abs": 100}]
    curve = _build_equity_curve_from_trades(trades, start_equity=50_000.0)
    assert curve[0] == 50_000.0
    assert curve[1] == 50_100.0


# ─── Per-Pair Summary Table (Task 12) ───


@pytest.fixture
def per_pair_eval_result():
    return {
        "per_pair_metrics": {
            "BTC/USDT": {
                "sharpe_ratio_equity_based": 3.92,
                "calmar_ratio": 5.82,
                "max_drawdown": 0.083,
                "win_rate": 0.627,
                "profit_factor": 2.1,
                "trades_per_year": 169,
                "total_pnl_pct": 48.74,
            },
            "SOL/USDT": {
                "sharpe_ratio_equity_based": 2.50,
                "calmar_ratio": 3.10,
                "max_drawdown": 0.12,
                "win_rate": 0.55,
                "profit_factor": 1.5,
                "trades_per_year": 120,
                "total_pnl_pct": 22.3,
            },
        }
    }


@pytest.fixture
def per_pair_pipeline_result():
    return {
        "tier_assignments": {
            "BTC/USDT": {"tier": "A"},
            "SOL/USDT": {"tier": "B"},
        },
        "analysis": {
            "per_pair": [
                {"symbol": "BTC/USDT", "verdict": "PASS"},
                {"symbol": "SOL/USDT", "verdict": "WARN"},
            ]
        },
    }


def test_per_pair_table_column_headers(per_pair_pipeline_result, per_pair_eval_result):
    html = _render_per_pair_table(per_pair_pipeline_result, per_pair_eval_result)
    for header in ["Symbol", "Tier", "Verdict", "Trades/yr", "Sharpe", "Calmar", "Max DD%", "PnL%", "Win Rate", "PF"]:
        assert header in html


def test_per_pair_table_verdict_css_classes(per_pair_pipeline_result, per_pair_eval_result):
    html = _render_per_pair_table(per_pair_pipeline_result, per_pair_eval_result)
    assert "verdict-pass" in html
    assert "verdict-warn" in html


def test_per_pair_table_tier_css_classes(per_pair_pipeline_result, per_pair_eval_result):
    html = _render_per_pair_table(per_pair_pipeline_result, per_pair_eval_result)
    assert "tier-a" in html
    assert "tier-b" in html


def test_per_pair_table_empty_data():
    html = _render_per_pair_table({}, {})
    assert "no-data" in html


def test_per_pair_table_verdict_fail():
    pipeline = {
        "analysis": {"per_pair": [{"symbol": "ETH/USDT", "verdict": "FAIL"}]}
    }
    eval_r = {
        "per_pair_metrics": {
            "ETH/USDT": {
                "sharpe_ratio_equity_based": 0.5,
                "calmar_ratio": 0.3,
                "max_drawdown": 0.25,
                "win_rate": 0.4,
                "profit_factor": 0.8,
                "trades_per_year": 50,
                "total_pnl_pct": -15.0,
            }
        }
    }
    html = _render_per_pair_table(pipeline, eval_r)
    assert "verdict-fail" in html


# ─── Per-Pair Equity Curves Grid (Task 13) ───


def test_per_pair_equity_curves_with_data():
    curves = {
        "BTCUSDT": [100000, 101000, 100500, 102000],
        "SOLUSDT": [100000, 99000, 99500, 101000],
    }
    html = _render_per_pair_equity_curves(curves, [])
    assert "Plotly.newPlot" in html
    assert "grid-3col" in html


def test_per_pair_equity_curves_div_ids():
    curves = {"BTCUSDT": [100000, 101000]}
    html = _render_per_pair_equity_curves(curves, [])
    assert 'id="pair-equity-BTCUSDT"' in html


def test_per_pair_equity_curves_empty_data():
    html = _render_per_pair_equity_curves({}, [])
    assert "no-data" in html


def test_per_pair_equity_curves_with_timestamps():
    curves = {"BTCUSDT": [100000, 101000, 99000]}
    ts = ["2026-01-01", "2026-01-02", "2026-01-03"]
    html = _render_per_pair_equity_curves(curves, ts)
    assert "Plotly.newPlot" in html
    assert "2026-01-01" in html


# ─── Tier Assignments Table (Task 14) ───


@pytest.fixture
def tier_analysis():
    return {
        "tier_assignments": {
            "BTC/USDT": {
                "tier": "A",
                "multiplier": 1.0,
                "sharpe": 3.5,
                "degradation": 0.3,
                "consistency": 0.15,
                "worst_sharpe": 1.2,
            },
            "SOL/USDT": {
                "tier": "C",
                "multiplier": 0.5,
                "sharpe": 1.8,
                "degradation": 0.6,
                "consistency": 0.4,
                "worst_sharpe": 0.3,
            },
        }
    }


def test_tier_table_column_headers(tier_analysis):
    html = _render_tier_table(tier_analysis)
    for header in ["Symbol", "Tier", "Multiplier", "OOS Sharpe", "Degradation", "Consistency", "Worst Sharpe"]:
        assert header in html


def test_tier_table_tier_css_classes(tier_analysis):
    html = _render_tier_table(tier_analysis)
    assert "tier-a" in html
    assert "tier-c" in html


def test_tier_table_empty_data():
    html = _render_tier_table({})
    assert "no-data" in html


def test_tier_table_tier_x():
    analysis = {
        "tier_assignments": {
            "JUNKUSDT": {"tier": "X", "multiplier": 0, "sharpe": -0.5, "degradation": 1.5, "consistency": 1.0, "worst_sharpe": -2.0}
        }
    }
    html = _render_tier_table(analysis)
    assert "tier-x" in html


# ─── Walk-Forward Evaluation (Task 15) ───


@pytest.fixture
def wf_eval_result():
    return {
        "wf_eval_metrics": {
            "BTC/USDT": {
                "wf_sharpe_median": 2.5,
                "wf_sharpe_std": 0.8,
                "wf_worst_sharpe": 0.5,
                "degradation_ratio": 0.3,
                "n_windows": 5,
            },
            "SOL/USDT": {
                "wf_sharpe_median": 1.2,
                "wf_sharpe_std": 1.5,
                "wf_worst_sharpe": -0.2,
                "degradation_ratio": 0.9,
                "n_windows": 5,
            },
        }
    }


def test_wf_evaluation_pair_names(wf_eval_result):
    html = _render_wf_evaluation(wf_eval_result)
    assert "BTC/USDT" in html
    assert "SOL/USDT" in html


def test_wf_evaluation_metric_values(wf_eval_result):
    html = _render_wf_evaluation(wf_eval_result)
    assert "2.50" in html  # median sharpe
    assert "0.30" in html  # degradation


def test_wf_evaluation_degradation_colors(wf_eval_result):
    html = _render_wf_evaluation(wf_eval_result)
    assert "verdict-pass" in html   # BTC degradation 0.3 < 0.5
    assert "verdict-fail" in html   # SOL degradation 0.9 > 0.8


def test_wf_evaluation_empty_data():
    html = _render_wf_evaluation({})
    assert "no-data" in html


def test_wf_evaluation_grid_layout(wf_eval_result):
    html = _render_wf_evaluation(wf_eval_result)
    assert "grid-3col" in html


# ─── S1 Parameters Table (Task 16) ───


@pytest.fixture
def s1_pipeline_result():
    return {
        "stage1_results": {
            "BTC/USDT": {
                "macd_fast": 2.5,
                "macd_slow": 26,
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
            },
            "SOL/USDT": {
                "macd_fast": 3.1,
                "macd_slow": 30,
                "macd_signal": 7,
                "rsi_period": 10,
                "rsi_lower": 25,
                "rsi_upper": 75,
                "rsi_lookback": 3,
                "trend_tf": "8h",
                "adx_threshold": 20,
                "trail_mult": 1.8,
                "hard_stop_mult": 2.5,
                "max_hold_bars": 36,
                "allow_flip": 0,
                "trend_strict": 1,
            },
        }
    }


def test_s1_params_table_param_names(s1_pipeline_result):
    html = _render_s1_params_table(s1_pipeline_result)
    for param in ["macd_fast", "macd_slow", "macd_signal", "rsi_period", "rsi_lower", "rsi_upper", "rsi_lookback", "trend_tf", "adx_threshold", "trail_mult", "hard_stop_mult", "max_hold_bars"]:
        assert param in html


def test_s1_params_table_symbol_headers(s1_pipeline_result):
    html = _render_s1_params_table(s1_pipeline_result)
    assert "BTC/USDT" in html
    assert "SOL/USDT" in html


def test_s1_params_table_pill_badges(s1_pipeline_result):
    html = _render_s1_params_table(s1_pipeline_result)
    assert "pill" in html
    assert "pill-green" in html
    assert "allow_flip: 0" in html
    assert "trend_strict: 1" in html


def test_s1_params_table_empty_data():
    html = _render_s1_params_table({})
    assert "no-data" in html


def test_s1_params_table_values_present(s1_pipeline_result):
    html = _render_s1_params_table(s1_pipeline_result)
    assert "2.5" in html   # macd_fast for BTC
    assert "4h" in html    # trend_tf for BTC


# ─── S1 Bullet Chart (Task 17) ───


def test_s1_bullet_chart_has_plotly(s1_pipeline_result):
    html = _render_s1_bullet_chart(s1_pipeline_result)
    assert "Plotly.newPlot" in html


def test_s1_bullet_chart_param_names(s1_pipeline_result):
    html = _render_s1_bullet_chart(s1_pipeline_result)
    for param in ["macd_fast", "macd_slow", "rsi_period", "rsi_lower", "rsi_upper"]:
        assert param in html


def test_s1_bullet_chart_empty_data():
    html = _render_s1_bullet_chart({})
    assert "no-data" in html


def test_s1_bullet_chart_div_id(s1_pipeline_result):
    html = _render_s1_bullet_chart(s1_pipeline_result)
    assert 's1-bullet-chart' in html


def test_s1_bullet_chart_symbol_names(s1_pipeline_result):
    html = _render_s1_bullet_chart(s1_pipeline_result)
    assert "BTC/USDT" in html
    assert "SOL/USDT" in html


# ─── S1 Top Trials (Task 18) ───


@pytest.fixture
def s1_top_trials_data():
    return {
        "BTC/USDT": {
            "n_trials_total": 500,
            "trials": [
                {
                    "number": 42,
                    "objective": 3.8,
                    "params": {"macd_fast": 2.5, "macd_slow": 26, "rsi_period": 14},
                    "metrics": {
                        "sharpe_ratio_equity_based": 3.92,
                        "max_drawdown": 0.083,
                        "total_pnl_pct": 48.7,
                        "trades_per_year": 169,
                    },
                },
                {
                    "number": 88,
                    "objective": 3.5,
                    "params": {"macd_fast": 3.0, "macd_slow": 28, "rsi_period": 12},
                    "metrics": {
                        "sharpe_ratio_equity_based": 3.50,
                        "max_drawdown": 0.095,
                        "total_pnl_pct": 40.2,
                        "trades_per_year": 155,
                    },
                },
            ],
        },
    }


def test_s1_top_trials_has_plotly(s1_top_trials_data):
    html = _render_s1_top_trials(s1_top_trials_data)
    assert "Plotly.newPlot" in html


def test_s1_top_trials_table_headers(s1_top_trials_data):
    html = _render_s1_top_trials(s1_top_trials_data)
    for header in ["Rank", "Objective", "Sharpe", "Max DD", "PnL%", "Trades/yr"]:
        assert header in html


def test_s1_top_trials_empty_data():
    html = _render_s1_top_trials({})
    assert "no-data" in html


def test_s1_top_trials_parcoords_div(s1_top_trials_data):
    html = _render_s1_top_trials(s1_top_trials_data)
    assert "s1-parcoords-BTCUSDT" in html


def test_s1_top_trials_scatter_div(s1_top_trials_data):
    html = _render_s1_top_trials(s1_top_trials_data)
    assert "s1-scatter-BTCUSDT" in html


def test_s1_top_trials_shows_trial_count(s1_top_trials_data):
    html = _render_s1_top_trials(s1_top_trials_data)
    assert "500" in html


# ─── S1 Optimization History (Task 19) ───


@pytest.fixture
def s1_history_data():
    return {
        "BTC/USDT": {
            "trial_numbers": [1, 2, 3, 4, 5],
            "objective_values": [1.0, 1.5, 1.2, 2.0, 1.8],
            "best_so_far": [1.0, 1.5, 1.5, 2.0, 2.0],
        },
        "SOL/USDT": {
            "trial_numbers": [1, 2, 3],
            "objective_values": [0.5, 1.0, 0.8],
            "best_so_far": [0.5, 1.0, 1.0],
        },
    }


def test_s1_history_has_plotly(s1_history_data):
    html = _render_s1_optimization_history(s1_history_data)
    assert "Plotly.newPlot" in html


def test_s1_history_empty_data():
    html = _render_s1_optimization_history({})
    assert "no-data" in html


def test_s1_history_per_pair_div_ids(s1_history_data):
    html = _render_s1_optimization_history(s1_history_data)
    assert "s1-history-BTCUSDT" in html
    assert "s1-history-SOLUSDT" in html


def test_s1_history_grid_layout(s1_history_data):
    html = _render_s1_optimization_history(s1_history_data)
    assert "grid-2col" in html


def test_s1_history_best_trial_marker(s1_history_data):
    html = _render_s1_optimization_history(s1_history_data)
    assert "star" in html


# ─── S2 Portfolio Parameters Card (Task 20) ───


@pytest.fixture
def pareto_front_with_params():
    return {
        "portfolio_params": {
            "max_concurrent": 6,
            "cluster_max": 2,
            "portfolio_heat": 0.06,
            "corr_gate_threshold": 0.65,
        },
        "selected_trial": 10,
        "trials": [
            {
                "number": 10,
                "params": {
                    "max_concurrent": 6,
                    "cluster_max": 2,
                    "portfolio_heat": 0.06,
                    "corr_gate_threshold": 0.65,
                },
                "objectives": {
                    "portfolio_calmar": 4.5,
                    "worst_pair_calmar": 2.1,
                    "neg_overfit_penalty": -0.3,
                },
            },
        ],
    }


def test_s2_params_shows_param_names(pareto_front_with_params):
    html = _render_s2_params(pareto_front_with_params)
    for name in ["max_concurrent", "cluster_max", "portfolio_heat", "corr_gate_threshold"]:
        assert name in html


def test_s2_params_shows_values(pareto_front_with_params):
    html = _render_s2_params(pareto_front_with_params)
    assert "6" in html
    assert "0.06" in html
    assert "0.65" in html


def test_s2_params_empty_data():
    html = _render_s2_params({})
    assert "no-data" in html


def test_s2_params_fallback_to_selected_trial():
    data = {
        "selected_trial": 5,
        "trials": [
            {
                "number": 5,
                "params": {"max_concurrent": 8, "cluster_max": 3, "portfolio_heat": 0.07, "corr_gate_threshold": 0.70},
                "objectives": {},
            },
        ],
    }
    html = _render_s2_params(data)
    assert "max_concurrent" in html
    assert "8" in html


def test_s2_params_shows_ranges(pareto_front_with_params):
    html = _render_s2_params(pareto_front_with_params)
    # Ranges should be present in the output
    assert "3" in html  # min of max_concurrent range
    assert "10" in html  # max of max_concurrent range


# ─── Pareto Front Scatter (Task 21) ───


def test_pareto_front_has_plotly(pareto_front_with_params):
    html = _render_pareto_front(pareto_front_with_params)
    assert "Plotly.newPlot" in html


def test_pareto_front_star_marker(pareto_front_with_params):
    html = _render_pareto_front(pareto_front_with_params)
    assert "star" in html


def test_pareto_front_empty_trials():
    html = _render_pareto_front({"trials": []})
    assert "no-data" in html


def test_pareto_front_empty_dict():
    html = _render_pareto_front({})
    assert "no-data" in html


def test_pareto_front_div_id(pareto_front_with_params):
    html = _render_pareto_front(pareto_front_with_params)
    assert 'id="pareto-front-chart"' in html


def test_pareto_front_multiple_trials():
    data = {
        "selected_trial": 1,
        "trials": [
            {"number": 1, "objectives": {"portfolio_calmar": 4.5, "worst_pair_calmar": 2.1, "neg_overfit_penalty": -0.3}},
            {"number": 2, "objectives": {"portfolio_calmar": 3.8, "worst_pair_calmar": 1.9, "neg_overfit_penalty": -0.5}},
            {"number": 3, "objectives": {"portfolio_calmar": 5.0, "worst_pair_calmar": 2.5, "neg_overfit_penalty": -0.1}},
        ],
    }
    html = _render_pareto_front(data)
    assert "Plotly.newPlot" in html
    assert "star" in html
    assert "Viridis" in html


# ─── S2 Optimization History (Task 22) ───


@pytest.fixture
def s2_history_data():
    return {
        "trial_numbers": [1, 2, 3, 4, 5],
        "portfolio_calmar_values": [2.0, 2.5, 2.3, 3.0, 2.8],
        "best_calmar_so_far": [2.0, 2.5, 2.5, 3.0, 3.0],
    }


def test_s2_history_has_plotly(s2_history_data):
    html = _render_s2_optimization_history(s2_history_data)
    assert "Plotly.newPlot" in html


def test_s2_history_both_traces(s2_history_data):
    html = _render_s2_optimization_history(s2_history_data)
    assert "Portfolio Calmar" in html
    assert "Best Calmar so far" in html


def test_s2_history_empty_data():
    html = _render_s2_optimization_history({})
    assert "no-data" in html


def test_s2_history_div_id(s2_history_data):
    html = _render_s2_optimization_history(s2_history_data)
    assert 'id="s2-opt-history-chart"' in html


def test_s2_history_empty_trial_numbers():
    html = _render_s2_optimization_history({"trial_numbers": [], "portfolio_calmar_values": [], "best_calmar_so_far": []})
    assert "no-data" in html


# ─── PnL Contribution (Task 23) ───


@pytest.fixture
def pnl_per_pair_trades():
    return {
        "BTC/USDT": [
            {"pnl_abs": 5000.0},
            {"pnl_abs": 3000.0},
            {"pnl_abs": -1000.0},
        ],
        "SOL/USDT": [
            {"pnl_abs": -2000.0},
            {"pnl_abs": 1000.0},
        ],
        "ETH/USDT": [
            {"pnl_abs": 4000.0},
        ],
    }


def test_pnl_contribution_has_plotly(pnl_per_pair_trades):
    html = _render_pnl_contribution([], pnl_per_pair_trades)
    assert "Plotly.newPlot" in html


def test_pnl_contribution_pair_names(pnl_per_pair_trades):
    html = _render_pnl_contribution([], pnl_per_pair_trades)
    assert "BTC/USDT" in html
    assert "SOL/USDT" in html
    assert "ETH/USDT" in html


def test_pnl_contribution_div_id(pnl_per_pair_trades):
    html = _render_pnl_contribution([], pnl_per_pair_trades)
    assert 'id="pnl-contribution-chart"' in html


def test_pnl_contribution_empty_data():
    html = _render_pnl_contribution([], {})
    assert "no-data" in html


def test_pnl_contribution_percentage_labels(pnl_per_pair_trades):
    html = _render_pnl_contribution([], pnl_per_pair_trades)
    # Should have percentage labels in output
    assert "%" in html


def test_pnl_contribution_sorted_by_size(pnl_per_pair_trades):
    html = _render_pnl_contribution([], pnl_per_pair_trades)
    # BTC has |7000|, ETH has |4000|, SOL has |-1000|
    # BTC should appear before ETH, ETH before SOL
    btc_pos = html.index("BTC/USDT")
    eth_pos = html.index("ETH/USDT")
    sol_pos = html.index("SOL/USDT")
    assert btc_pos < eth_pos < sol_pos


# ─── Correlation Heatmap (Task 24) ───


@pytest.fixture
def corr_matrix_data():
    return {
        "symbols": ["BTC/USDT", "SOL/USDT", "ETH/USDT"],
        "matrix": [
            [1.0, 0.65, 0.80],
            [0.65, 1.0, 0.55],
            [0.80, 0.55, 1.0],
        ],
        "corr_gate_threshold": 0.72,
    }


def test_correlation_heatmap_has_plotly(corr_matrix_data):
    html = _render_correlation_heatmap(corr_matrix_data)
    assert "Plotly.newPlot" in html


def test_correlation_heatmap_type(corr_matrix_data):
    html = _render_correlation_heatmap(corr_matrix_data)
    assert "heatmap" in html


def test_correlation_heatmap_threshold(corr_matrix_data):
    html = _render_correlation_heatmap(corr_matrix_data)
    assert "0.72" in html


def test_correlation_heatmap_div_id(corr_matrix_data):
    html = _render_correlation_heatmap(corr_matrix_data)
    assert 'id="correlation-heatmap"' in html


def test_correlation_heatmap_empty_data():
    html = _render_correlation_heatmap({})
    assert "no-data" in html


def test_correlation_heatmap_empty_symbols():
    html = _render_correlation_heatmap({"symbols": [], "matrix": []})
    assert "no-data" in html


def test_correlation_heatmap_rdbu_colorscale(corr_matrix_data):
    html = _render_correlation_heatmap(corr_matrix_data)
    assert "RdBu" in html


def test_correlation_heatmap_annotations(corr_matrix_data):
    html = _render_correlation_heatmap(corr_matrix_data)
    # Annotation values should be present
    assert "1.00" in html
    assert "0.65" in html
    assert "0.80" in html


# ─── Monthly Returns (Task 25) ───


@pytest.fixture
def monthly_trades():
    return [
        {"exit_ts": "2025-01-15T10:00:00", "pnl_abs": 2000.0},
        {"exit_ts": "2025-01-20T10:00:00", "pnl_abs": -500.0},
        {"exit_ts": "2025-02-10T10:00:00", "pnl_abs": 3000.0},
        {"exit_ts": "2025-06-05T10:00:00", "pnl_abs": -1000.0},
        {"exit_ts": "2026-01-08T10:00:00", "pnl_abs": 5000.0},
    ]


def test_monthly_returns_month_headers(monthly_trades):
    html = _render_monthly_returns(monthly_trades, [])
    for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
        assert month in html


def test_monthly_returns_year_rows(monthly_trades):
    html = _render_monthly_returns(monthly_trades, [])
    assert "2025" in html
    assert "2026" in html


def test_monthly_returns_empty_data():
    html = _render_monthly_returns([], [])
    assert "no-data" in html


def test_monthly_returns_has_year_total(monthly_trades):
    html = _render_monthly_returns(monthly_trades, [])
    assert "Year Total" in html


def test_monthly_returns_color_styles(monthly_trades):
    html = _render_monthly_returns(monthly_trades, [])
    # Positive returns should have green background
    assert "rgba(195, 232, 141" in html
    # Negative returns should have red background
    assert "rgba(255, 117, 127" in html


def test_monthly_returns_percentage_values(monthly_trades):
    html = _render_monthly_returns(monthly_trades, [])
    # Jan 2025: (2000 - 500) / 100000 * 100 = +1.5%
    assert "+1.5%" in html
    # Feb 2025: 3000 / 100000 * 100 = +3.0%
    assert "+3.0%" in html


# ─── Trade Analysis (Task 26) ───


@pytest.fixture
def trade_analysis_trades():
    return [
        {"direction": "long", "reason": "trailing_stop", "pnl_abs": 2000.0, "pnl_pct": 2.0, "hold_bars": 24, "entry_ts": "2025-01-01", "exit_ts": "2025-01-02"},
        {"direction": "long", "reason": "trailing_stop", "pnl_abs": -500.0, "pnl_pct": -0.5, "hold_bars": 12, "entry_ts": "2025-01-03", "exit_ts": "2025-01-04"},
        {"direction": "short", "reason": "hard_stop", "pnl_abs": -1000.0, "pnl_pct": -1.0, "hold_bars": 6, "entry_ts": "2025-01-05", "exit_ts": "2025-01-06"},
        {"direction": "long", "reason": "max_hold", "pnl_abs": 500.0, "pnl_pct": 0.5, "hold_bars": 48, "entry_ts": "2025-01-07", "exit_ts": "2025-01-08"},
        {"direction": "short", "reason": "trailing_stop", "pnl_abs": 3000.0, "pnl_pct": 3.0, "hold_bars": 36, "entry_ts": "2025-01-09", "exit_ts": "2025-01-10"},
    ]


def test_trade_analysis_long_short_cards(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    assert "Long Trades" in html
    assert "Short Trades" in html


def test_trade_analysis_exit_reasons_chart(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    assert 'id="exit-reasons-chart"' in html
    assert "Plotly.newPlot" in html


def test_trade_analysis_pnl_distribution(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    assert 'id="pnl-distribution-chart"' in html


def test_trade_analysis_hold_duration(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    assert 'id="hold-duration-chart"' in html


def test_trade_analysis_empty_data():
    html = _render_trade_analysis([], {})
    assert "no-data" in html


def test_trade_analysis_grid_2col(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    assert "grid-2col" in html


def test_trade_analysis_long_count(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    # 3 long trades
    # Check that the long card contains "3"
    long_idx = html.index("Long Trades")
    short_idx = html.index("Short Trades")
    long_section = html[long_idx:short_idx]
    assert ">3<" in long_section


def test_trade_analysis_short_count(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    # 2 short trades
    short_idx = html.index("Short Trades")
    short_section = html[short_idx:short_idx + 500]
    assert ">2<" in short_section


def test_trade_analysis_exit_reason_names(trade_analysis_trades):
    html = _render_trade_analysis(trade_analysis_trades, {})
    assert "trailing_stop" in html
    assert "hard_stop" in html
    assert "max_hold" in html
