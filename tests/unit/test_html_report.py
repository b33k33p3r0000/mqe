from __future__ import annotations

import pytest
from mqe.html_report import generate_html_report, PLOTLY_CDN


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
