"""Unit tests for MQE metrics module — Sharpe, Calmar, Sortino, Monte Carlo."""

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from mqe.core.metrics import (
    MonteCarloResult,
    MetricsResult,
    calculate_annualized_trades,
    calculate_calmar_ratio,
    calculate_equity_based_sharpe,
    calculate_metrics,
    calculate_recovery_factor,
    calculate_short_hold_ratio,
    calculate_sortino_ratio,
    calculate_streaks,
    monte_carlo_validation,
    aggregate_mc_results,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_trades(
    n: int = 50,
    win_rate: float = 0.6,
    avg_pnl: float = 100.0,
    seed: int = 42,
    days: int = 365,
) -> list:
    """Generate synthetic trades with specified win rate, spread over `days`."""
    rng = np.random.default_rng(seed)
    trades = []
    start = datetime(2024, 1, 1)
    for i in range(n):
        is_win = rng.random() < win_rate
        pnl = abs(rng.normal(avg_pnl, avg_pnl * 0.3)) if is_win else -abs(rng.normal(avg_pnl * 0.7, avg_pnl * 0.3))
        entry_ts = start + timedelta(hours=i * (days * 24 // n))
        exit_ts = entry_ts + timedelta(hours=int(rng.integers(2, 48)))
        trades.append({
            "entry_ts": entry_ts.isoformat(),
            "exit_ts": exit_ts.isoformat(),
            "entry_price": 50000.0,
            "exit_price": 50000.0 + pnl,
            "pnl_abs": pnl,
            "pnl_pct": pnl / 50000.0 * 100,
            "hold_bars": int(rng.integers(2, 48)),
            "direction": "long",
        })
    return trades


def _make_profitable_trades(n: int = 60, days: int = 400) -> list:
    """Generate trades that are definitely profitable overall."""
    return _make_trades(n=n, win_rate=0.65, avg_pnl=150.0, seed=123, days=days)


def _make_losing_trades(n: int = 40, days: int = 365) -> list:
    """Generate trades that are definitely losing overall."""
    return _make_trades(n=n, win_rate=0.25, avg_pnl=100.0, seed=99, days=days)


# ── MetricsResult (calculate_metrics) ────────────────────────────────────────


class TestCalculateMetrics:
    def test_empty_trades_returns_zeros(self):
        result = calculate_metrics([], backtest_days=365)
        assert isinstance(result, MetricsResult)
        assert result.trades == 0
        assert result.total_pnl == 0.0
        assert result.sharpe_ratio == 0.0
        assert result.calmar_ratio == 0.0
        assert result.sortino_ratio == 0.0

    def test_profitable_trades_positive_pnl(self):
        trades = _make_profitable_trades()
        result = calculate_metrics(trades, backtest_days=400)
        assert result.total_pnl > 0
        assert result.equity > 50_000.0
        assert result.trades == len(trades)

    def test_win_rate_bounded(self):
        trades = _make_profitable_trades()
        result = calculate_metrics(trades, backtest_days=400)
        assert 0.0 <= result.win_rate <= 100.0

    def test_trades_per_year_positive(self):
        trades = _make_profitable_trades(n=60, days=400)
        result = calculate_metrics(trades, backtest_days=400)
        assert result.trades_per_year > 0

    def test_time_in_market_bounded(self):
        trades = _make_profitable_trades()
        result = calculate_metrics(trades, backtest_days=400)
        assert 0.0 <= result.time_in_market <= 1.0


# ── Sharpe (equity-based) ────────────────────────────────────────────────────


class TestSharpeEquityBased:
    def test_sharpe_equity_positive_for_profitable_trades(self):
        trades = _make_profitable_trades(n=60, days=400)
        sharpe = calculate_equity_based_sharpe(trades, start_equity=50_000.0, backtest_days=400)
        assert sharpe > 0.0, f"Expected positive Sharpe for profitable trades, got {sharpe}"

    def test_sharpe_equity_zero_for_no_trades(self):
        assert calculate_equity_based_sharpe([], start_equity=50_000.0, backtest_days=365) == 0.0

    def test_sharpe_equity_zero_for_short_backtest(self):
        trades = _make_profitable_trades(n=10, days=20)
        assert calculate_equity_based_sharpe(trades, start_equity=50_000.0, backtest_days=20) == 0.0


# ── Calmar ───────────────────────────────────────────────────────────────────


class TestCalmarRatio:
    def test_calmar_annualized(self):
        """Calmar with >365 backtest_days should annualize the return."""
        total_return = 60.0  # 60% total
        max_dd = -10.0       # -10% drawdown
        backtest_days = 730  # 2 years

        calmar = calculate_calmar_ratio(total_return, max_dd, backtest_days)
        # annual_return = 60 / (730/365.25) ~ 30.04%
        # calmar = 30.04 / 10 ~ 3.0
        assert 2.5 < calmar < 3.5, f"Expected ~3.0, got {calmar}"

    def test_calmar_no_drawdown_returns_zero(self):
        assert calculate_calmar_ratio(50.0, 0.0) == 0.0

    def test_calmar_short_backtest_no_annualize(self):
        """Backtest < 365 days: return treated as already annualized."""
        calmar = calculate_calmar_ratio(30.0, -5.0, backtest_days=200)
        assert calmar == pytest.approx(6.0, rel=0.01)


# ── Sortino ──────────────────────────────────────────────────────────────────


class TestSortinoRatio:
    def test_sortino_positive(self):
        trades = _make_profitable_trades(n=60, days=400)
        sortino = calculate_sortino_ratio(trades, start_equity=50_000.0, backtest_days=400)
        assert sortino > 0.0, f"Expected positive Sortino, got {sortino}"

    def test_sortino_zero_for_no_trades(self):
        assert calculate_sortino_ratio([], start_equity=50_000.0, backtest_days=365) == 0.0

    def test_sortino_zero_for_short_backtest(self):
        trades = _make_profitable_trades(n=10, days=20)
        assert calculate_sortino_ratio(trades, start_equity=50_000.0, backtest_days=20) == 0.0


# ── Max Drawdown ─────────────────────────────────────────────────────────────


class TestMaxDrawdown:
    def test_max_drawdown_bounded(self):
        """Drawdown should be negative or zero (percentage from peak)."""
        trades = _make_profitable_trades()
        result = calculate_metrics(trades, backtest_days=400)
        assert result.max_drawdown <= 0.0, f"Drawdown should be <= 0, got {result.max_drawdown}"

    def test_max_drawdown_zero_for_all_winners(self):
        """If every trade is a winner, drawdown is 0."""
        trades = []
        start = datetime(2024, 1, 1)
        for i in range(20):
            entry_ts = start + timedelta(days=i * 10)
            exit_ts = entry_ts + timedelta(hours=5)
            trades.append({
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": exit_ts.isoformat(),
                "entry_price": 50000.0,
                "exit_price": 50100.0,
                "pnl_abs": 100.0,
                "pnl_pct": 0.2,
                "hold_bars": 5,
                "direction": "long",
            })
        result = calculate_metrics(trades, backtest_days=200)
        assert result.max_drawdown == 0.0


# ── Monte Carlo ──────────────────────────────────────────────────────────────


class TestMonteCarlo:
    def test_monte_carlo_returns_result(self):
        trades = _make_profitable_trades(n=60, days=400)
        mc = monte_carlo_validation(trades, n_simulations=100, backtest_days=400)
        assert isinstance(mc, MonteCarloResult)
        assert mc.n_simulations == 100
        assert mc.confidence_level in ("HIGH", "MEDIUM", "LOW")
        assert 0.0 <= mc.robustness_score <= 1.0

    def test_monte_carlo_too_few_trades(self):
        trades = _make_profitable_trades(n=5, days=100)
        mc = monte_carlo_validation(trades[:5], n_simulations=100)
        assert mc.n_simulations == 0
        assert mc.confidence_level == "LOW"

    def test_monte_carlo_deterministic_with_seed(self):
        trades = _make_profitable_trades(n=60, days=400)
        mc1 = monte_carlo_validation(trades, n_simulations=100, seed=42, backtest_days=400)
        mc2 = monte_carlo_validation(trades, n_simulations=100, seed=42, backtest_days=400)
        assert mc1.sharpe_mean == mc2.sharpe_mean
        assert mc1.robustness_score == mc2.robustness_score


# ── Aggregate MC Results ─────────────────────────────────────────────────────


class TestAggregateMCResults:
    def test_aggregate_empty(self):
        result = aggregate_mc_results([])
        assert result.n_simulations == 0
        assert result.confidence_level == "INSUFFICIENT_DATA"

    def test_aggregate_uses_worst_case(self):
        r1 = MonteCarloResult(
            sharpe_mean=1.5, sharpe_std=0.2,
            sharpe_ci_low=1.0, sharpe_ci_high=2.0,
            max_dd_mean=-5.0, max_dd_std=1.0,
            max_dd_ci_low=-3.0, max_dd_ci_high=-7.0,
            win_rate_mean=60.0, win_rate_ci_low=55.0, win_rate_ci_high=65.0,
            confidence_level="HIGH", n_simulations=100,
            robustness_score=0.8,
        )
        r2 = MonteCarloResult(
            sharpe_mean=0.8, sharpe_std=0.3,
            sharpe_ci_low=0.2, sharpe_ci_high=1.5,
            max_dd_mean=-8.0, max_dd_std=2.0,
            max_dd_ci_low=-5.0, max_dd_ci_high=-12.0,
            win_rate_mean=52.0, win_rate_ci_low=48.0, win_rate_ci_high=58.0,
            confidence_level="MEDIUM", n_simulations=100,
            robustness_score=0.5,
        )
        agg = aggregate_mc_results([r1, r2])
        # Should use worst-case (min) for CI low, robustness, confidence
        assert agg.sharpe_ci_low == 0.2  # min of 1.0, 0.2
        assert agg.robustness_score == 0.5  # min of 0.8, 0.5
        assert agg.confidence_level == "MEDIUM"  # weakest


# ── Helper functions ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_annualized_trades(self):
        trades = _make_profitable_trades(n=50, days=365)
        result = calculate_annualized_trades(trades, backtest_days=365)
        assert result == pytest.approx(50.0, rel=0.01)

    def test_annualized_trades_empty(self):
        assert calculate_annualized_trades([], backtest_days=365) == 0.0

    def test_short_hold_ratio_all_long(self):
        trades = [{"hold_bars": 100} for _ in range(10)]
        assert calculate_short_hold_ratio(trades, min_hold=5) == 0.0

    def test_short_hold_ratio_all_short(self):
        trades = [{"hold_bars": 1} for _ in range(10)]
        assert calculate_short_hold_ratio(trades, min_hold=5) == 1.0

    def test_streaks(self):
        trades = [
            {"pnl_abs": 10}, {"pnl_abs": 20}, {"pnl_abs": 30},  # 3 win streak
            {"pnl_abs": -5}, {"pnl_abs": -10},                    # 2 loss streak
            {"pnl_abs": 15},
        ]
        win, loss = calculate_streaks(trades)
        assert win == 3
        assert loss == 2

    def test_streaks_empty(self):
        assert calculate_streaks([]) == (0, 0)

    def test_recovery_factor(self):
        # total_pnl=5000, max_dd=-10%, start_equity=50000
        # max_dd_abs = 10 * 50000 / 100 = 5000
        # recovery = 5000 / 5000 = 1.0
        rf = calculate_recovery_factor(5000.0, -10.0, 50_000.0)
        assert rf == pytest.approx(1.0, rel=0.01)

    def test_recovery_factor_no_drawdown(self):
        assert calculate_recovery_factor(5000.0, 0.0, 50_000.0) == 0.0
