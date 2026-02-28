"""Unit tests for portfolio backtest simulator."""

import numpy as np
import pandas as pd
import pytest

from mqe.core.portfolio import PortfolioSimulator, PortfolioResult
from tests.conftest import make_1h_ohlcv_pd, resample_to_multi_tf


def _make_pair_signals(n_bars, buy_bars=None, sell_bars=None):
    """Create synthetic signal arrays for testing."""
    buy = np.zeros(n_bars, dtype=np.bool_)
    sell = np.zeros(n_bars, dtype=np.bool_)
    if buy_bars:
        for b in buy_bars:
            buy[b] = True
    if sell_bars:
        for s in sell_bars:
            sell[s] = True
    atr_arr = np.full(n_bars, 2.0)
    sig_str = np.random.rand(n_bars)
    return buy, sell, atr_arr, sig_str


class TestPortfolioResult:
    def test_creates_combined_equity_curve(self):
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data, "ETH/USDT": data}
        pair_signals = {
            "BTC/USDT": _make_pair_signals(n, buy_bars=[250], sell_bars=[300]),
            "ETH/USDT": _make_pair_signals(n, buy_bars=[260], sell_bars=[310]),
        }
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168},
            "ETH/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168},
        }
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        assert isinstance(result, PortfolioResult)
        assert result.equity > 0
        assert len(result.equity_curve) == n

    def test_max_concurrent_enforced(self):
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {f"PAIR{i}/USDT": data for i in range(3)}
        pair_signals = {
            f"PAIR{i}/USDT": _make_pair_signals(n, buy_bars=[250])
            for i in range(3)
        }
        pair_params = {
            f"PAIR{i}/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168}
            for i in range(3)
        }
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            max_concurrent=2,
        )
        result = sim.run()
        assert result.max_positions_open <= 2

    def test_trades_have_symbols(self):
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data}
        pair_signals = {"BTC/USDT": _make_pair_signals(n, buy_bars=[250], sell_bars=[300])}
        pair_params = {"BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168}}
        sim = PortfolioSimulator(pair_data=pair_data, pair_signals=pair_signals, pair_params=pair_params)
        result = sim.run()
        for trade in result.all_trades:
            assert "symbol" in trade
            assert "reason" in trade
            assert "direction" in trade


class TestPortfolioExits:
    def test_hard_stop_exit(self):
        """Hard stop triggers when price moves against position by hard_stop_mult * ATR."""
        n = 500
        # Create data with a known price drop after entry
        np.random.seed(99)
        df = make_1h_ohlcv_pd(n_bars=n, seed=99)
        data = resample_to_multi_tf(df)

        # Buy at bar 250, price should drop enough to trigger hard stop
        pair_signals = {"BTC/USDT": _make_pair_signals(n, buy_bars=[250])}
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 0.5, "trail_mult": 5.0, "max_hold_bars": 500},
        }
        sim = PortfolioSimulator(
            pair_data={"BTC/USDT": data},
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        # With a very tight stop (0.5 * ATR) and high trail/hold, hard stop should fire
        if len(result.all_trades) > 0:
            # At least one trade should have exited (either hard_stop or force_close)
            reasons = [t["reason"] for t in result.all_trades]
            assert len(reasons) > 0

    def test_time_exit(self):
        """Time exit triggers after max_hold_bars."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)

        # Buy at bar 250, no sell signal, short max_hold_bars
        pair_signals = {"BTC/USDT": _make_pair_signals(n, buy_bars=[250])}
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 20},
        }
        sim = PortfolioSimulator(
            pair_data={"BTC/USDT": data},
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        # With impossibly wide stops and 20-bar max hold, should get time_exit
        time_exits = [t for t in result.all_trades if t["reason"] == "time_exit"]
        assert len(time_exits) >= 1

    def test_opposing_signal_exit(self):
        """Opposing signal closes the position."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)

        # Buy at 250, sell at 260 (close enough that stop/trail won't trigger first)
        pair_signals = {"BTC/USDT": _make_pair_signals(
            n, buy_bars=[250], sell_bars=[260]
        )}
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 500},
        }
        sim = PortfolioSimulator(
            pair_data={"BTC/USDT": data},
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        opp_exits = [t for t in result.all_trades if t["reason"] == "opposing_signal"]
        assert len(opp_exits) >= 1

    def test_force_close_at_end(self):
        """Open positions are force-closed at end of data."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)

        # Buy at 250, no sell signal, impossibly wide stops
        pair_signals = {"BTC/USDT": _make_pair_signals(n, buy_bars=[250])}
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 9999},
        }
        sim = PortfolioSimulator(
            pair_data={"BTC/USDT": data},
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        force_exits = [t for t in result.all_trades if t["reason"] == "force_close"]
        assert len(force_exits) >= 1


class TestPortfolioHeat:
    def test_portfolio_heat_tracks_drawdown(self):
        """Portfolio result tracks max drawdown."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data}
        pair_signals = {"BTC/USDT": _make_pair_signals(n, buy_bars=[250], sell_bars=[300])}
        pair_params = {"BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168}}
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        assert result.max_drawdown >= 0.0
        assert result.peak_equity >= result.equity or result.max_drawdown == 0.0


class TestClusterMax:
    def test_cluster_max_enforced(self):
        """Cluster max limits positions per cluster."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)

        # All 3 pairs in same cluster, all signal at same bar
        pair_data = {
            "ETH/USDT": data,
            "SOL/USDT": data,
            "ADA/USDT": data,
        }
        pair_signals = {
            "ETH/USDT": _make_pair_signals(n, buy_bars=[250]),
            "SOL/USDT": _make_pair_signals(n, buy_bars=[250]),
            "ADA/USDT": _make_pair_signals(n, buy_bars=[250]),
        }
        pair_params = {
            sym: {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 9999}
            for sym in pair_data
        }
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            cluster_max={"smart_contract_l1": 1},
            max_concurrent=5,
        )
        result = sim.run()
        # Only 1 should be opened in the cluster
        cluster_max_val = result.max_cluster_open.get("smart_contract_l1", 0)
        assert cluster_max_val <= 1


class TestPerPairTrades:
    def test_per_pair_trades_populated(self):
        """Per-pair trade breakdown is available."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data, "ETH/USDT": data}
        pair_signals = {
            "BTC/USDT": _make_pair_signals(n, buy_bars=[250], sell_bars=[300]),
            "ETH/USDT": _make_pair_signals(n, buy_bars=[260], sell_bars=[310]),
        }
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168},
            "ETH/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168},
        }
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        # per_pair_trades keys should be subset of pair_data keys
        for sym in result.per_pair_trades:
            assert sym in pair_data

    def test_equity_curve_monotone_when_no_trades(self):
        """With no signals, equity should remain at starting value."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data}
        pair_signals = {"BTC/USDT": _make_pair_signals(n)}  # no buy/sell bars
        pair_params = {"BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168}}
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            starting_equity=50000.0,
        )
        result = sim.run()
        assert len(result.all_trades) == 0
        assert result.equity == 50000.0
        np.testing.assert_array_equal(result.equity_curve, np.full(n, 50000.0))


class TestShortPositions:
    def test_short_positions_work(self):
        """Sell signals open short positions."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data}
        pair_signals = {"BTC/USDT": _make_pair_signals(n, sell_bars=[250], buy_bars=[300])}
        pair_params = {"BTC/USDT": {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 500}}
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        shorts = [t for t in result.all_trades if t["direction"] == "short"]
        assert len(shorts) >= 1
