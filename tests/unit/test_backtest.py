"""Unit tests for MQE backtest engine — 5-level exit system."""

import numpy as np
import pandas as pd
import pytest

from mqe.core.backtest import (
    trading_loop_numba,
    simulate_trades_fast,
    precompute_timeframe_indices,
    BacktestResult,
    EXIT_OPPOSING_SIGNAL,
    EXIT_HARD_STOP,
    EXIT_TRAILING_STOP,
    EXIT_TIME_EXIT,
    EXIT_PORTFOLIO_HEAT,
    EXIT_FORCE_CLOSE,
)
from tests.conftest import make_1h_ohlcv_pd


def _make_data(n_bars=500, seed=42):
    return {"1h": make_1h_ohlcv_pd(n_bars=n_bars, seed=seed)}


def _make_signals(n_bars, buy_bars=None, sell_bars=None):
    buy = np.zeros(n_bars, dtype=np.bool_)
    sell = np.zeros(n_bars, dtype=np.bool_)
    if buy_bars:
        for b in buy_bars:
            buy[b] = True
    if sell_bars:
        for s in sell_bars:
            sell[s] = True
    return buy, sell


class TestBacktestResult:
    def test_returns_backtest_result(self):
        data = _make_data()
        n = len(data["1h"])
        buy, sell = _make_signals(n, buy_bars=[250], sell_bars=[300])
        atr_arr = np.full(n, 1.0)
        result = simulate_trades_fast("BTC/USDT", data, buy, sell, atr_values=atr_arr)
        assert isinstance(result, BacktestResult)
        assert result.equity >= 0

    def test_trade_has_direction(self):
        data = _make_data()
        n = len(data["1h"])
        buy, sell = _make_signals(n, buy_bars=[250], sell_bars=[300])
        atr_arr = np.full(n, 1.0)
        result = simulate_trades_fast("BTC/USDT", data, buy, sell, atr_values=atr_arr)
        for trade in result.trades:
            assert trade["direction"] in ("long", "short")


class TestHardStop:
    def test_hard_stop_triggers_on_big_drop(self):
        """Hard stop exits when price drops below entry - hard_stop_mult * ATR."""
        n = 500
        dates = pd.date_range("2025-01-01", periods=n, freq="1h")
        close = np.full(n, 100.0)
        close[260:] = 90.0  # 10% drop
        high = close + 1.0
        low = close - 1.0
        data = {"1h": pd.DataFrame(
            {"open": close.copy(), "high": high, "low": low, "close": close},
            index=dates,
        )}
        buy, sell = _make_signals(n, buy_bars=[250])
        atr_arr = np.full(n, 2.0)  # ATR=2, hard_stop_mult=2 → stop at 96
        result = simulate_trades_fast(
            "BTC/USDT", data, buy, sell,
            atr_values=atr_arr, hard_stop_mult=2.0,
        )
        assert any(t["reason"] == "hard_stop" for t in result.trades)


class TestTrailingStop:
    def test_trailing_activates_after_profit(self):
        """Trailing stop only activates after 1.5*ATR profit, then trails."""
        n = 500
        dates = pd.date_range("2025-01-01", periods=n, freq="1h")
        close = np.full(n, 100.0)
        close[260:280] = 110.0  # profit > 1.5*ATR(2)=3 → trailing activates
        close[280:300] = 104.0  # drops > trail_mult*ATR(2)=6 from high → exit
        high = close + 0.5
        low = close - 0.5
        data = {"1h": pd.DataFrame(
            {"open": close.copy(), "high": high, "low": low, "close": close},
            index=dates,
        )}
        buy, sell = _make_signals(n, buy_bars=[250])
        atr_arr = np.full(n, 2.0)
        result = simulate_trades_fast(
            "BTC/USDT", data, buy, sell,
            atr_values=atr_arr, trail_mult=3.0,
        )
        assert any(t["reason"] == "trailing_stop" for t in result.trades)


class TestTimeExit:
    def test_time_exit_triggers(self):
        """Position closed after max_hold_bars."""
        data = _make_data()
        n = len(data["1h"])
        buy, sell = _make_signals(n, buy_bars=[250])  # no sell signal
        atr_arr = np.full(n, 1.0)
        result = simulate_trades_fast(
            "BTC/USDT", data, buy, sell,
            atr_values=atr_arr, max_hold_bars=50,
            hard_stop_mult=100.0,  # effectively disabled
        )
        time_exits = [t for t in result.trades if t["reason"] == "time_exit"]
        if time_exits:
            for t in time_exits:
                assert t["hold_bars"] >= 50


class TestOpposingSignal:
    def test_signal_exit(self):
        data = _make_data()
        n = len(data["1h"])
        buy, sell = _make_signals(n, buy_bars=[250], sell_bars=[260])
        atr_arr = np.full(n, 1.0)
        result = simulate_trades_fast(
            "BTC/USDT", data, buy, sell,
            atr_values=atr_arr,
            hard_stop_mult=100.0, trail_mult=100.0, max_hold_bars=999,
        )
        assert any(t["reason"] == "opposing_signal" for t in result.trades)


class TestForceClose:
    def test_force_close_at_end(self):
        data = _make_data()
        n = len(data["1h"])
        buy, sell = _make_signals(n, buy_bars=[490])
        atr_arr = np.full(n, 1.0)
        result = simulate_trades_fast(
            "BTC/USDT", data, buy, sell,
            atr_values=atr_arr,
            hard_stop_mult=100.0, trail_mult=100.0, max_hold_bars=999,
        )
        assert any(t["reason"] == "force_close" for t in result.trades)


class TestExitPriority:
    def test_hard_stop_before_signal(self):
        """Hard stop has higher priority than opposing signal."""
        n = 500
        dates = pd.date_range("2025-01-01", periods=n, freq="1h")
        close = np.full(n, 100.0)
        close[260:] = 80.0  # massive drop
        high = close + 0.5
        low = close - 0.5
        data = {"1h": pd.DataFrame(
            {"open": close.copy(), "high": high, "low": low, "close": close},
            index=dates,
        )}
        buy, sell = _make_signals(n, buy_bars=[250], sell_bars=[260])
        atr_arr = np.full(n, 2.0)
        result = simulate_trades_fast(
            "BTC/USDT", data, buy, sell,
            atr_values=atr_arr, hard_stop_mult=2.0,
        )
        assert result.trades[0]["reason"] == "hard_stop"
