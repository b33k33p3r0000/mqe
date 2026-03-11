from __future__ import annotations

import pytest
from mqe.html_report import (
    generate_html_report,
    PLOTLY_CDN,
    _render_hero_metrics,
    _render_portfolio_equity_curve,
    _render_concurrent_positions,
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
