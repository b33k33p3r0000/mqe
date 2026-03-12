"""
MQE Backtest Engine
===================
Numba-accelerated backtesting with 5-level exit system.

Exit priority (first-match wins per bar):
  1. HARD STOP — ATR-based (entry +/- hard_stop_mult x ATR)
  2. TRAILING STOP — activates after 1.5xATR profit, trails at trail_mult x ATR
  3. TIME EXIT — close after max_hold_bars
  4. OPPOSING SIGNAL — signal exit / flip
  5. FORCE CLOSE — end of data

Portfolio heat (exit #2 in design) is handled by portfolio.py, not here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

from mqe.config import (
    BACKTEST_POSITION_PCT,
    BASE_TF,
    FEE,
    GARCH_ADAPTIVE_STOPS,
    GARCH_STOP_FACTOR_MIN,
    GARCH_STOP_FACTOR_MAX,
    LONG_ONLY,
    MIN_HOLD_BARS,
    MIN_WARMUP_BARS,
    STARTING_EQUITY,
    TRAILING_ACTIVATION_MULT,
    get_slippage,
)

logger = logging.getLogger("mqe.backtest")

# Exit reason codes
EXIT_OPPOSING_SIGNAL = 0
EXIT_HARD_STOP = 1
EXIT_TRAILING_STOP = 2
EXIT_TIME_EXIT = 3
EXIT_PORTFOLIO_HEAT = 4  # handled by portfolio.py, not trading_loop
EXIT_FORCE_CLOSE = 5


@dataclass
class BacktestResult:
    """Backtest result."""
    equity: float
    trades: list[dict[str, Any]]
    backtest_days: int


def precompute_timeframe_indices(base_timestamps: np.ndarray, tf_timestamps: np.ndarray) -> np.ndarray:
    """Map base timeframe indices to higher timeframe indices."""
    indices = np.searchsorted(tf_timestamps, base_timestamps, side="right") - 1
    indices = np.clip(indices, 0, len(tf_timestamps) - 1)
    return indices.astype(np.int32)


@njit(cache=True)
def trading_loop_numba(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    buy_signal: np.ndarray,
    sell_signal: np.ndarray,
    atr_values: np.ndarray,
    min_hold: int,
    position_pct: float,
    slippage: float,
    fee: float,
    start_idx: int,
    end_idx: int,
    hard_stop_mult: float,
    trail_mult: float,
    max_hold_bars: int,
    trailing_activation_mult: float,
    long_only: bool,
    allow_flip: bool,
    starting_equity: float,
    vol_ratio: np.ndarray,
    vol_sensitivity: float,
    adaptive_stops: bool,
    stop_vol_factor: np.ndarray,
) -> tuple[float, np.ndarray, int]:
    """
    Numba trading loop with 5-level exit.

    Returns:
        (final_equity, trades_array, n_trades)
        trades_array columns: [entry_idx, exit_idx, entry_price, exit_price,
                               pnl_abs, pnl_pct, exit_reason, size, capital_at_entry,
                               direction, highest_price]
        exit_reason: 0=opposing_signal, 1=hard_stop, 2=trailing_stop,
                     3=time_exit, 5=force_close
        direction: +1=long, -1=short
    """
    cash = starting_equity
    position = 0  # 0=flat, 1=long, -1=short
    position_size = 0.0
    entry_bar_idx = 0
    entry_price = 0.0
    capital_at_entry = 0.0
    highest_price = 0.0   # for trailing stop (long)
    lowest_price = 1e18   # for trailing stop (short)
    trailing_active = False

    max_trades = (end_idx - start_idx) + 1
    trades = np.zeros((max_trades, 11), dtype=np.float64)
    n_trades = 0

    for bar in range(start_idx, end_idx):
        current_price = close[bar]
        current_high = high[bar]
        current_low = low[bar]
        current_atr = atr_values[bar] if atr_values[bar] > 0 else 1e-8

        if position != 0:
            # Update extreme prices for trailing
            if position == 1:
                if current_high > highest_price:
                    highest_price = current_high
            else:
                if current_low < lowest_price:
                    lowest_price = current_low

            bars_held = bar - entry_bar_idx

            # === EXIT 1: HARD STOP (highest priority) ===
            if adaptive_stops:
                effective_atr = current_atr * stop_vol_factor[bar]
            else:
                effective_atr = current_atr

            hard_stop_triggered = False
            if position == 1:
                stop_level = entry_price - hard_stop_mult * effective_atr
                if current_low <= stop_level:
                    exit_price = stop_level * (1.0 - slippage)
                    hard_stop_triggered = True
            elif position == -1:
                stop_level = entry_price + hard_stop_mult * effective_atr
                if current_high >= stop_level:
                    exit_price = stop_level * (1.0 + slippage)
                    hard_stop_triggered = True

            if hard_stop_triggered:
                if position == 1:
                    fee_cost = exit_price * position_size * fee
                    sell_proceeds = position_size * exit_price - fee_cost
                    pnl = sell_proceeds - capital_at_entry
                    cash += sell_proceeds
                else:
                    net_entry_rev = position_size * entry_price * (1.0 - fee)
                    net_exit_cost = position_size * exit_price * (1.0 + fee)
                    pnl = net_entry_rev - net_exit_cost
                    cash += capital_at_entry + pnl

                pnl_pct = pnl / capital_at_entry if capital_at_entry > 0 else 0.0
                trades[n_trades, 0] = entry_bar_idx
                trades[n_trades, 1] = bar
                trades[n_trades, 2] = entry_price
                trades[n_trades, 3] = exit_price
                trades[n_trades, 4] = pnl
                trades[n_trades, 5] = pnl_pct
                trades[n_trades, 6] = 1  # hard_stop
                trades[n_trades, 7] = position_size
                trades[n_trades, 8] = capital_at_entry
                trades[n_trades, 9] = position
                trades[n_trades, 10] = highest_price if position == 1 else lowest_price
                n_trades += 1
                position = 0
                position_size = 0.0
                trailing_active = False
                continue

            # === EXIT 2: TRAILING STOP ===
            # Check activation first
            if not trailing_active:
                if position == 1:
                    unrealized = current_high - entry_price
                    if unrealized >= trailing_activation_mult * effective_atr:
                        trailing_active = True
                elif position == -1:
                    unrealized = entry_price - current_low
                    if unrealized >= trailing_activation_mult * effective_atr:
                        trailing_active = True

            if trailing_active:
                trailing_triggered = False
                if position == 1:
                    trail_level = highest_price - trail_mult * effective_atr
                    if current_low <= trail_level:
                        exit_price = trail_level * (1.0 - slippage)
                        trailing_triggered = True
                elif position == -1:
                    trail_level = lowest_price + trail_mult * effective_atr
                    if current_high >= trail_level:
                        exit_price = trail_level * (1.0 + slippage)
                        trailing_triggered = True

                if trailing_triggered:
                    if position == 1:
                        fee_cost = exit_price * position_size * fee
                        sell_proceeds = position_size * exit_price - fee_cost
                        pnl = sell_proceeds - capital_at_entry
                        cash += sell_proceeds
                    else:
                        net_entry_rev = position_size * entry_price * (1.0 - fee)
                        net_exit_cost = position_size * exit_price * (1.0 + fee)
                        pnl = net_entry_rev - net_exit_cost
                        cash += capital_at_entry + pnl

                    pnl_pct = pnl / capital_at_entry if capital_at_entry > 0 else 0.0
                    trades[n_trades, 0] = entry_bar_idx
                    trades[n_trades, 1] = bar
                    trades[n_trades, 2] = entry_price
                    trades[n_trades, 3] = exit_price
                    trades[n_trades, 4] = pnl
                    trades[n_trades, 5] = pnl_pct
                    trades[n_trades, 6] = 2  # trailing_stop
                    trades[n_trades, 7] = position_size
                    trades[n_trades, 8] = capital_at_entry
                    trades[n_trades, 9] = position
                    trades[n_trades, 10] = highest_price if position == 1 else lowest_price
                    n_trades += 1
                    position = 0
                    position_size = 0.0
                    trailing_active = False
                    continue

            # === EXIT 3: TIME EXIT ===
            if bars_held >= max_hold_bars:
                exit_price = current_price
                if position == 1:
                    exit_price *= (1.0 - slippage)
                    fee_cost = exit_price * position_size * fee
                    sell_proceeds = position_size * exit_price - fee_cost
                    pnl = sell_proceeds - capital_at_entry
                    cash += sell_proceeds
                else:
                    exit_price *= (1.0 + slippage)
                    net_entry_rev = position_size * entry_price * (1.0 - fee)
                    net_exit_cost = position_size * exit_price * (1.0 + fee)
                    pnl = net_entry_rev - net_exit_cost
                    cash += capital_at_entry + pnl

                pnl_pct = pnl / capital_at_entry if capital_at_entry > 0 else 0.0
                trades[n_trades, 0] = entry_bar_idx
                trades[n_trades, 1] = bar
                trades[n_trades, 2] = entry_price
                trades[n_trades, 3] = exit_price
                trades[n_trades, 4] = pnl
                trades[n_trades, 5] = pnl_pct
                trades[n_trades, 6] = 3  # time_exit
                trades[n_trades, 7] = position_size
                trades[n_trades, 8] = capital_at_entry
                trades[n_trades, 9] = position
                trades[n_trades, 10] = highest_price if position == 1 else lowest_price
                n_trades += 1
                position = 0
                position_size = 0.0
                trailing_active = False
                continue

            # === EXIT 4: OPPOSING SIGNAL ===
            can_exit = bars_held >= min_hold

            if position == 1 and sell_signal[bar] and can_exit:
                exit_price = current_price * (1.0 - slippage)
                fee_cost = exit_price * position_size * fee
                sell_proceeds = position_size * exit_price - fee_cost
                pnl = sell_proceeds - capital_at_entry
                pnl_pct = pnl / capital_at_entry if capital_at_entry > 0 else 0.0

                trades[n_trades, 0] = entry_bar_idx
                trades[n_trades, 1] = bar
                trades[n_trades, 2] = entry_price
                trades[n_trades, 3] = exit_price
                trades[n_trades, 4] = pnl
                trades[n_trades, 5] = pnl_pct
                trades[n_trades, 6] = 0  # opposing_signal
                trades[n_trades, 7] = position_size
                trades[n_trades, 8] = capital_at_entry
                trades[n_trades, 9] = 1
                trades[n_trades, 10] = highest_price
                n_trades += 1

                cash += sell_proceeds
                position = 0
                position_size = 0.0
                trailing_active = False

                if allow_flip and not long_only and cash > 0:
                    entry_price = current_price * (1.0 - slippage)
                    adjusted_pct = position_pct * vol_ratio[bar] * vol_sensitivity
                    if adjusted_pct < 0.05:
                        adjusted_pct = 0.05
                    elif adjusted_pct > 0.30:
                        adjusted_pct = 0.30
                    capital_at_entry = cash * adjusted_pct
                    position_size = capital_at_entry / (entry_price * (1.0 + fee))
                    cash -= capital_at_entry
                    entry_bar_idx = bar
                    position = -1
                    highest_price = 0.0
                    lowest_price = current_low
                    trailing_active = False

            elif position == -1 and buy_signal[bar] and can_exit:
                exit_price = current_price * (1.0 + slippage)
                net_entry_rev = position_size * entry_price * (1.0 - fee)
                net_exit_cost = position_size * exit_price * (1.0 + fee)
                pnl = net_entry_rev - net_exit_cost
                pnl_pct = pnl / capital_at_entry if capital_at_entry > 0 else 0.0

                trades[n_trades, 0] = entry_bar_idx
                trades[n_trades, 1] = bar
                trades[n_trades, 2] = entry_price
                trades[n_trades, 3] = exit_price
                trades[n_trades, 4] = pnl
                trades[n_trades, 5] = pnl_pct
                trades[n_trades, 6] = 0  # opposing_signal
                trades[n_trades, 7] = position_size
                trades[n_trades, 8] = capital_at_entry
                trades[n_trades, 9] = -1
                trades[n_trades, 10] = lowest_price
                n_trades += 1

                cash += capital_at_entry + pnl
                position = 0
                position_size = 0.0
                trailing_active = False

                if allow_flip and cash > 0:
                    entry_price = current_price * (1.0 + slippage)
                    adjusted_pct = position_pct * vol_ratio[bar] * vol_sensitivity
                    if adjusted_pct < 0.05:
                        adjusted_pct = 0.05
                    elif adjusted_pct > 0.30:
                        adjusted_pct = 0.30
                    capital_at_entry = cash * adjusted_pct
                    position_size = capital_at_entry / (entry_price * (1.0 + fee))
                    cash -= capital_at_entry
                    entry_bar_idx = bar
                    position = 1
                    highest_price = current_high
                    lowest_price = 1e18
                    trailing_active = False

        # === OPEN NEW POSITION (if flat) ===
        if position == 0:
            if buy_signal[bar] and cash > 0:
                entry_price = current_price * (1.0 + slippage)
                adjusted_pct = position_pct * vol_ratio[bar] * vol_sensitivity
                if adjusted_pct < 0.05:
                    adjusted_pct = 0.05
                elif adjusted_pct > 0.30:
                    adjusted_pct = 0.30
                capital_at_entry = cash * adjusted_pct
                position_size = capital_at_entry / (entry_price * (1.0 + fee))
                cash -= capital_at_entry
                entry_bar_idx = bar
                position = 1
                highest_price = current_high
                lowest_price = 1e18
                trailing_active = False
            elif sell_signal[bar] and not long_only and cash > 0:
                entry_price = current_price * (1.0 - slippage)
                adjusted_pct = position_pct * vol_ratio[bar] * vol_sensitivity
                if adjusted_pct < 0.05:
                    adjusted_pct = 0.05
                elif adjusted_pct > 0.30:
                    adjusted_pct = 0.30
                capital_at_entry = cash * adjusted_pct
                position_size = capital_at_entry / (entry_price * (1.0 + fee))
                cash -= capital_at_entry
                entry_bar_idx = bar
                position = -1
                highest_price = 0.0
                lowest_price = current_low
                trailing_active = False

    # === FORCE CLOSE AT END ===
    if position != 0 and position_size > 0:
        final_idx = end_idx - 1
        if position == 1:
            exit_price = close[final_idx] * (1.0 - slippage)
            fee_cost = exit_price * position_size * fee
            sell_proceeds = position_size * exit_price - fee_cost
            pnl = sell_proceeds - capital_at_entry
            cash += sell_proceeds
            direction = 1.0
        else:
            exit_price = close[final_idx] * (1.0 + slippage)
            net_entry_rev = position_size * entry_price * (1.0 - fee)
            net_exit_cost = position_size * exit_price * (1.0 + fee)
            pnl = net_entry_rev - net_exit_cost
            cash += capital_at_entry + pnl
            direction = -1.0

        pnl_pct = pnl / capital_at_entry if capital_at_entry > 0 else 0.0
        trades[n_trades, 0] = entry_bar_idx
        trades[n_trades, 1] = final_idx
        trades[n_trades, 2] = entry_price
        trades[n_trades, 3] = exit_price
        trades[n_trades, 4] = pnl
        trades[n_trades, 5] = pnl_pct
        trades[n_trades, 6] = 5  # force_close
        trades[n_trades, 7] = position_size
        trades[n_trades, 8] = capital_at_entry
        trades[n_trades, 9] = direction
        trades[n_trades, 10] = highest_price if direction > 0 else lowest_price
        n_trades += 1

    return cash, trades[:n_trades], n_trades


def simulate_trades_fast(
    symbol: str,
    data: dict[str, pd.DataFrame],
    buy_signal: np.ndarray,
    sell_signal: np.ndarray,
    atr_values: np.ndarray,
    start_idx: int | None = None,
    end_idx: int | None = None,
    long_only: bool | None = None,
    allow_flip: bool | None = None,
    hard_stop_mult: float = 2.5,
    trail_mult: float = 3.0,
    max_hold_bars: int = 168,
    position_pct: float | None = None,
    vol_ratio: np.ndarray | None = None,
    vol_sensitivity: float = 1.0,
    adaptive_stops: bool | None = None,
) -> BacktestResult:
    """
    Backtest with 5-level exit system.

    Args:
        symbol: Trading pair (for slippage lookup).
        data: Dict with at least "1h" key containing OHLCV DataFrame.
        buy_signal: 1D boolean array — True where buy signal fires.
        sell_signal: 1D boolean array — True where sell signal fires.
        atr_values: 1D float array — pre-computed ATR(14) values.
        hard_stop_mult: Hard stop distance in ATR multiples.
        trail_mult: Trailing stop distance in ATR multiples.
        max_hold_bars: Max bars to hold a position.
        position_pct: Override position size (default: BACKTEST_POSITION_PCT).
    """
    if long_only is None:
        long_only = LONG_ONLY
    if allow_flip is None:
        allow_flip = False
    if position_pct is None:
        position_pct = BACKTEST_POSITION_PCT

    base = data[BASE_TF]

    if len(base) < MIN_WARMUP_BARS:
        logger.warning("Not enough data (%d bars)", len(base))
        return BacktestResult(equity=STARTING_EQUITY, trades=[], backtest_days=0)

    actual_start = start_idx if start_idx is not None else MIN_WARMUP_BARS
    actual_end = end_idx if end_idx is not None else len(base)

    backtest_start = base.index[actual_start]
    backtest_end = base.index[min(actual_end - 1, len(base) - 1)]
    backtest_days = (backtest_end - backtest_start).total_seconds() / (24 * 3600)

    close = base["close"].values.astype(np.float64)
    high_arr = base["high"].values.astype(np.float64)
    low_arr = base["low"].values.astype(np.float64)

    slippage = get_slippage(symbol)

    if vol_ratio is None:
        vol_ratio = np.ones(len(base), dtype=np.float64)

    if adaptive_stops is None:
        adaptive_stops = GARCH_ADAPTIVE_STOPS

    if adaptive_stops:
        stop_vol_factor = np.clip(1.0 / vol_ratio, GARCH_STOP_FACTOR_MIN, GARCH_STOP_FACTOR_MAX)
    else:
        stop_vol_factor = np.ones(len(base), dtype=np.float64)

    final_equity, trades_arr, n_trades = trading_loop_numba(
        close=close,
        high=high_arr,
        low=low_arr,
        buy_signal=buy_signal.astype(np.bool_),
        sell_signal=sell_signal.astype(np.bool_),
        atr_values=atr_values.astype(np.float64),
        min_hold=MIN_HOLD_BARS,
        position_pct=position_pct,
        slippage=slippage,
        fee=FEE,
        start_idx=actual_start,
        end_idx=actual_end,
        hard_stop_mult=hard_stop_mult,
        trail_mult=trail_mult,
        max_hold_bars=max_hold_bars,
        trailing_activation_mult=TRAILING_ACTIVATION_MULT,
        long_only=long_only,
        allow_flip=allow_flip,
        starting_equity=float(STARTING_EQUITY),
        vol_ratio=vol_ratio,
        vol_sensitivity=vol_sensitivity,
        adaptive_stops=adaptive_stops,
        stop_vol_factor=stop_vol_factor,
    )

    reason_map = {
        0: "opposing_signal",
        1: "hard_stop",
        2: "trailing_stop",
        3: "time_exit",
        4: "portfolio_heat",
        5: "force_close",
    }
    direction_map = {1: "long", -1: "short"}
    trades = []

    for i in range(n_trades):
        entry_idx = int(trades_arr[i, 0])
        exit_idx = int(trades_arr[i, 1])
        direction_code = int(trades_arr[i, 9])
        trades.append({
            "entry_ts": base.index[entry_idx].isoformat(),
            "entry_price": round(trades_arr[i, 2], 6),
            "exit_ts": base.index[exit_idx].isoformat(),
            "exit_price": round(trades_arr[i, 3], 6),
            "hold_bars": exit_idx - entry_idx,
            "size": round(trades_arr[i, 7], 8),
            "capital_at_entry": round(trades_arr[i, 8], 2),
            "pnl_abs": round(trades_arr[i, 4], 2),
            "pnl_pct": trades_arr[i, 5],
            "symbol": symbol,
            "reason": reason_map.get(int(trades_arr[i, 6]), "unknown"),
            "direction": direction_map.get(direction_code, "unknown"),
        })

    return BacktestResult(equity=float(final_equity), trades=trades, backtest_days=int(backtest_days))
