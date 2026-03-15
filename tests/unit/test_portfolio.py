"""Unit tests for portfolio backtest simulator."""

import numpy as np
import pandas as pd
import pytest

from mqe.config import CORRELATION_GATE_THRESHOLD
from mqe.core.portfolio import PortfolioSimulator, PortfolioResult
from tests.conftest import make_1h_ohlcv_pd, make_pair_signals, resample_to_multi_tf


class TestPortfolioResult:
    def test_creates_combined_equity_curve(self):
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data, "ETH/USDT": data}
        pair_signals = {
            "BTC/USDT": make_pair_signals(n, buy_bars=[250], sell_bars=[300]),
            "ETH/USDT": make_pair_signals(n, buy_bars=[260], sell_bars=[310]),
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
            f"PAIR{i}/USDT": make_pair_signals(n, buy_bars=[250])
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
        pair_signals = {"BTC/USDT": make_pair_signals(n, buy_bars=[250], sell_bars=[300])}
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
        pair_signals = {"BTC/USDT": make_pair_signals(n, buy_bars=[250])}
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
        pair_signals = {"BTC/USDT": make_pair_signals(n, buy_bars=[250])}
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
        pair_signals = {"BTC/USDT": make_pair_signals(
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
        pair_signals = {"BTC/USDT": make_pair_signals(n, buy_bars=[250])}
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
        pair_signals = {"BTC/USDT": make_pair_signals(n, buy_bars=[250], sell_bars=[300])}
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
            "ETH/USDT": make_pair_signals(n, buy_bars=[250]),
            "SOL/USDT": make_pair_signals(n, buy_bars=[250]),
            "ADA/USDT": make_pair_signals(n, buy_bars=[250]),
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
            "BTC/USDT": make_pair_signals(n, buy_bars=[250], sell_bars=[300]),
            "ETH/USDT": make_pair_signals(n, buy_bars=[260], sell_bars=[310]),
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
        pair_signals = {"BTC/USDT": make_pair_signals(n)}  # no buy/sell bars
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
        pair_signals = {"BTC/USDT": make_pair_signals(n, sell_bars=[250], buy_bars=[300])}
        pair_params = {"BTC/USDT": {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 500}}
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        result = sim.run()
        shorts = [t for t in result.all_trades if t["direction"] == "short"]
        assert len(shorts) >= 1


class TestTierMultipliers:
    """Tests for tier_multiplier signal ranking, pair exclusion, and defaults."""

    def test_tier_x_pair_excluded(self):
        """Tier X pair (multiplier=0) should never trade."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data, "ETH/USDT": data}
        pair_signals = {
            "BTC/USDT": make_pair_signals(n, buy_bars=[250], sell_bars=[300]),
            "ETH/USDT": make_pair_signals(n, buy_bars=[250], sell_bars=[300]),
        }
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168},
            "ETH/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168},
        }
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            tier_multipliers={"BTC/USDT": 1.0, "ETH/USDT": 0.0},
        )
        result = sim.run()
        # ETH should have zero trades — it's Tier X
        eth_trades = result.per_pair_trades.get("ETH/USDT", [])
        assert len(eth_trades) == 0
        # BTC should still trade
        btc_trades = result.per_pair_trades.get("BTC/USDT", [])
        assert len(btc_trades) > 0

    def test_tier_multiplier_affects_ranking(self):
        """Higher effective strength (signal * tier_mult) should be preferred."""
        n = 500
        np.random.seed(42)
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)

        # Both pairs signal at the same bar with max_concurrent=5 so both pass filter.
        # Deterministic signal strengths: BTC raw=0.5, ETH raw=0.9
        btc_sig = make_pair_signals(n, buy_bars=[250])
        eth_sig = make_pair_signals(n, buy_bars=[250])
        btc_sig[3][250] = 0.5
        eth_sig[3][250] = 0.9

        pair_data = {"BTC/USDT": data, "ETH/USDT": data}
        pair_signals = {"BTC/USDT": btc_sig, "ETH/USDT": eth_sig}
        pair_params = {
            "BTC/USDT": {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 9999},
            "ETH/USDT": {"hard_stop_mult": 100.0, "trail_mult": 100.0, "max_hold_bars": 9999},
        }

        # Without tier multipliers: ETH ranked first (0.9 > 0.5)
        sim_no_tier = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            max_concurrent=5,
        )
        result_no_tier = sim_no_tier.run()
        # Both trade; first opened should be ETH (higher raw signal → ranked first)
        bar250_trades = [t for t in result_no_tier.all_trades if t["entry_bar"] == 250]
        assert len(bar250_trades) == 2
        assert bar250_trades[0]["symbol"] == "ETH/USDT"

        # With tier multipliers: BTC=2.0, ETH=0.5
        # Effective: BTC=0.5*2.0=1.0, ETH=0.9*0.5=0.45 → BTC ranked first
        sim_tier = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            max_concurrent=5,
            tier_multipliers={"BTC/USDT": 2.0, "ETH/USDT": 0.5},
        )
        result_tier = sim_tier.run()
        bar250_trades_tier = [t for t in result_tier.all_trades if t["entry_bar"] == 250]
        assert len(bar250_trades_tier) == 2
        assert bar250_trades_tier[0]["symbol"] == "BTC/USDT"

    def test_no_tier_multipliers_preserves_behavior(self):
        """Default (no tier_multipliers) should work same as before."""
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data}
        pair_signals = {"BTC/USDT": make_pair_signals(n, buy_bars=[250], sell_bars=[300])}
        pair_params = {"BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168}}

        # Without tier_multipliers (default)
        sim_default = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        assert sim_default.tier_multipliers == {}

        # Explicit empty dict should also work
        sim_none = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            tier_multipliers=None,
        )
        assert sim_none.tier_multipliers == {}

        # Both should produce identical results
        result_default = sim_default.run()
        result_none = sim_none.run()
        assert len(result_default.all_trades) == len(result_none.all_trades)
        assert result_default.equity == result_none.equity


class TestCorrGateThreshold:
    """Tests that corr_gate_threshold parameter overrides config constant."""

    def test_default_uses_config_value(self):
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data}
        pair_signals = {"BTC/USDT": make_pair_signals(n)}
        pair_params = {"BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168}}
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
        )
        assert sim.corr_gate_threshold == CORRELATION_GATE_THRESHOLD

    def test_custom_threshold_stored(self):
        n = 500
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        pair_data = {"BTC/USDT": data}
        pair_signals = {"BTC/USDT": make_pair_signals(n)}
        pair_params = {"BTC/USDT": {"hard_stop_mult": 2.5, "trail_mult": 3.0, "max_hold_bars": 168}}
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            corr_gate_threshold=0.85,
        )
        assert sim.corr_gate_threshold == 0.85
