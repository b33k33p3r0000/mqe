"""
MQE Portfolio Backtest Simulator
================================
Multi-pair shared-equity bar-by-bar backtest.

This is a Python loop (NOT Numba) because portfolio-level logic requires
dynamic data structures (dict of open positions, cluster counting, etc.)
that Numba cannot handle.

Exit priority per bar (for each open position):
  1. HARD STOP -- entry +/- hard_stop_mult x ATR
  2. PORTFOLIO HEAT -- close worst performer when portfolio DD > threshold
  3. TRAILING STOP -- activates after 1.5xATR profit, trails at trail_mult x ATR
  4. TIME EXIT -- max_hold_bars
  5. OPPOSING SIGNAL -- signal exit
  6. FORCE CLOSE -- end of data

Entry logic per bar:
  1. Collect all buy/sell signals across pairs
  2. Filter: skip if max_concurrent reached
  3. Filter: skip if cluster_max reached for pair's cluster
  4. Correlation gate: if >=3 corr>0.75 pairs open, need signal_strength > 1.5
  5. Rank remaining by signal_strength (descending)
  6. Open with inverse-vol sizing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from mqe.config import (
    BASE_TF,
    CORRELATION_GATE_MAX_OPEN,
    CORRELATION_GATE_THRESHOLD,
    FEE,
    MIN_HOLD_BARS,
    SIGNAL_STRENGTH_GATED,
    STARTING_EQUITY,
    TRAILING_ACTIVATION_MULT,
    get_cluster,
    get_slippage,
)
from mqe.risk.sizing import compute_position_size

logger = logging.getLogger("mqe.portfolio")

# Exit reason labels
REASON_HARD_STOP = "hard_stop"
REASON_PORTFOLIO_HEAT = "portfolio_heat"
REASON_TRAILING_STOP = "trailing_stop"
REASON_TIME_EXIT = "time_exit"
REASON_OPPOSING_SIGNAL = "opposing_signal"
REASON_FORCE_CLOSE = "force_close"


@dataclass
class OpenPosition:
    """Tracks a single open position."""

    symbol: str
    direction: int  # +1=long, -1=short
    entry_bar: int
    entry_price: float
    size: float
    capital: float
    highest_price: float
    lowest_price: float
    trailing_active: bool = False
    hard_stop_mult: float = 2.5
    trail_mult: float = 3.0
    max_hold_bars: int = 168


@dataclass
class PortfolioResult:
    """Result of a portfolio-level backtest."""

    equity: float
    equity_curve: np.ndarray
    all_trades: list[dict[str, Any]]
    per_pair_trades: dict[str, list[dict[str, Any]]]
    max_positions_open: int
    max_cluster_open: dict[str, int]
    peak_equity: float
    max_drawdown: float


class PortfolioSimulator:
    """
    Bar-by-bar multi-pair portfolio backtest simulator.

    Iterates across all pairs simultaneously on shared equity.
    """

    def __init__(
        self,
        pair_data: dict[str, dict[str, pd.DataFrame]],
        pair_signals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
        pair_params: dict[str, dict[str, Any]],
        max_concurrent: int = 5,
        cluster_max: dict[str, int] | None = None,
        portfolio_heat: float = 0.05,
        starting_equity: float = STARTING_EQUITY,
        corr_matrix: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.pair_data = pair_data
        self.pair_signals = pair_signals
        self.pair_params = pair_params
        self.max_concurrent = max_concurrent
        self.cluster_max = cluster_max or {}
        self.portfolio_heat = portfolio_heat
        self.starting_equity = starting_equity
        self.corr_matrix = corr_matrix or {}

        # Pre-extract base TF arrays per pair for fast bar access
        self.symbols = list(pair_data.keys())
        self._close: dict[str, np.ndarray] = {}
        self._high: dict[str, np.ndarray] = {}
        self._low: dict[str, np.ndarray] = {}
        self._timestamps: dict[str, pd.DatetimeIndex] = {}
        self._n_bars: int = 0

        for sym in self.symbols:
            base = pair_data[sym][BASE_TF]
            self._close[sym] = base["close"].values.astype(np.float64)
            self._high[sym] = base["high"].values.astype(np.float64)
            self._low[sym] = base["low"].values.astype(np.float64)
            self._timestamps[sym] = base.index
            n = len(base)
            if self._n_bars == 0:
                self._n_bars = n
            else:
                self._n_bars = min(self._n_bars, n)

        # Unpack signals per pair
        self._buy: dict[str, np.ndarray] = {}
        self._sell: dict[str, np.ndarray] = {}
        self._atr: dict[str, np.ndarray] = {}
        self._sig_str: dict[str, np.ndarray] = {}

        for sym in self.symbols:
            signals = pair_signals[sym]
            self._buy[sym] = signals[0]
            self._sell[sym] = signals[1]
            self._atr[sym] = signals[2]
            self._sig_str[sym] = signals[3]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _count_cluster(
        self, cluster: str, open_positions: list[OpenPosition]
    ) -> int:
        """Count open positions in a given cluster."""
        count = 0
        for pos in open_positions:
            if get_cluster(pos.symbol) == cluster:
                count += 1
        return count

    def _correlated_open_count(
        self, symbol: str, open_positions: list[OpenPosition]
    ) -> int:
        """Count open positions highly correlated with symbol."""
        if not self.corr_matrix or symbol not in self.corr_matrix:
            return 0
        count = 0
        for pos in open_positions:
            if pos.symbol in self.corr_matrix[symbol]:
                if abs(self.corr_matrix[symbol][pos.symbol]) > CORRELATION_GATE_THRESHOLD:
                    count += 1
        return count

    def _close_position(
        self,
        pos: OpenPosition,
        bar: int,
        reason: str,
        exit_price: float,
    ) -> tuple[float, dict[str, Any]]:
        """
        Close a position and compute PnL.

        Returns:
            (capital_returned, trade_dict)
        """
        slippage = get_slippage(pos.symbol)

        if pos.direction == 1:  # long
            adj_exit = exit_price * (1.0 - slippage)
            fee_cost = adj_exit * pos.size * FEE
            sell_proceeds = pos.size * adj_exit - fee_cost
            pnl = sell_proceeds - pos.capital
            capital_returned = sell_proceeds
        else:  # short
            adj_exit = exit_price * (1.0 + slippage)
            net_entry_rev = pos.size * pos.entry_price * (1.0 - FEE)
            net_exit_cost = pos.size * adj_exit * (1.0 + FEE)
            pnl = net_entry_rev - net_exit_cost
            capital_returned = pos.capital + pnl

        pnl_pct = pnl / pos.capital if pos.capital > 0 else 0.0

        # Convert bar indices to ISO timestamps for metrics compatibility
        ts = self._timestamps[pos.symbol]
        entry_ts = ts[pos.entry_bar].isoformat() if pos.entry_bar < len(ts) else ""
        exit_ts = ts[bar].isoformat() if bar < len(ts) else ""

        trade = {
            "symbol": pos.symbol,
            "direction": "long" if pos.direction == 1 else "short",
            "entry_bar": pos.entry_bar,
            "exit_bar": bar,
            "entry_ts": entry_ts,
            "exit_ts": exit_ts,
            "entry_price": round(pos.entry_price, 6),
            "exit_price": round(exit_price, 6),
            "hold_bars": bar - pos.entry_bar,
            "size": round(pos.size, 8),
            "capital_at_entry": round(pos.capital, 2),
            "pnl_abs": round(pnl, 2),
            "pnl_pct": pnl_pct,
            "reason": reason,
        }
        return capital_returned, trade

    def _unrealized_pnl(self, pos: OpenPosition, bar: int) -> float:
        """Compute unrealized PnL for an open position at a given bar."""
        current_price = self._close[pos.symbol][bar]
        if pos.direction == 1:
            return (current_price - pos.entry_price) / pos.entry_price * pos.capital
        else:
            return (pos.entry_price - current_price) / pos.entry_price * pos.capital

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------

    def run(self) -> PortfolioResult:
        """Run the portfolio backtest bar-by-bar."""
        n_bars = self._n_bars
        equity = self.starting_equity
        cash = self.starting_equity

        equity_curve = np.full(n_bars, self.starting_equity)
        open_positions: list[OpenPosition] = []
        all_trades: list[dict[str, Any]] = []
        per_pair_trades: dict[str, list[dict[str, Any]]] = {
            sym: [] for sym in self.symbols
        }

        peak_equity = self.starting_equity
        max_drawdown = 0.0
        max_positions_open = 0
        max_cluster_open: dict[str, int] = {}

        # Track which symbols have an open position
        open_symbols: set = set()

        for bar in range(n_bars):
            # ── 1. Update position tracking (highest/lowest for trailing) ──
            for pos in open_positions:
                sym = pos.symbol
                if bar < len(self._high[sym]):
                    current_high = self._high[sym][bar]
                    current_low = self._low[sym][bar]
                    if pos.direction == 1:
                        if current_high > pos.highest_price:
                            pos.highest_price = current_high
                    else:
                        if current_low < pos.lowest_price:
                            pos.lowest_price = current_low

            # ── 2. Check exits for all open positions ──
            to_close: list[tuple[int, str, float]] = []  # (index, reason, exit_price)

            for i, pos in enumerate(open_positions):
                sym = pos.symbol
                if bar >= len(self._close[sym]):
                    continue

                current_price = self._close[sym][bar]
                current_high = self._high[sym][bar]
                current_low = self._low[sym][bar]
                current_atr = self._atr[sym][bar] if self._atr[sym][bar] > 0 else 1e-8
                bars_held = bar - pos.entry_bar

                # === EXIT 1: HARD STOP ===
                if pos.direction == 1:
                    stop_level = pos.entry_price - pos.hard_stop_mult * current_atr
                    if current_low <= stop_level:
                        to_close.append((i, REASON_HARD_STOP, stop_level))
                        continue
                else:
                    stop_level = pos.entry_price + pos.hard_stop_mult * current_atr
                    if current_high >= stop_level:
                        to_close.append((i, REASON_HARD_STOP, stop_level))
                        continue

                # === EXIT 3: TRAILING STOP ===
                # Check activation
                if not pos.trailing_active:
                    if pos.direction == 1:
                        unrealized = current_high - pos.entry_price
                        if unrealized >= TRAILING_ACTIVATION_MULT * current_atr:
                            pos.trailing_active = True
                    else:
                        unrealized = pos.entry_price - current_low
                        if unrealized >= TRAILING_ACTIVATION_MULT * current_atr:
                            pos.trailing_active = True

                if pos.trailing_active:
                    if pos.direction == 1:
                        trail_level = pos.highest_price - pos.trail_mult * current_atr
                        if current_low <= trail_level:
                            to_close.append((i, REASON_TRAILING_STOP, trail_level))
                            continue
                    else:
                        trail_level = pos.lowest_price + pos.trail_mult * current_atr
                        if current_high >= trail_level:
                            to_close.append((i, REASON_TRAILING_STOP, trail_level))
                            continue

                # === EXIT 4: TIME EXIT ===
                if bars_held >= pos.max_hold_bars:
                    to_close.append((i, REASON_TIME_EXIT, current_price))
                    continue

                # === EXIT 5: OPPOSING SIGNAL ===
                can_exit = bars_held >= MIN_HOLD_BARS
                if can_exit:
                    if pos.direction == 1 and self._sell[sym][bar]:
                        to_close.append((i, REASON_OPPOSING_SIGNAL, current_price))
                        continue
                    elif pos.direction == -1 and self._buy[sym][bar]:
                        to_close.append((i, REASON_OPPOSING_SIGNAL, current_price))
                        continue

            # Process exits (reverse order to keep indices valid)
            for idx, reason, exit_price in sorted(to_close, key=lambda x: x[0], reverse=True):
                pos = open_positions[idx]
                capital_returned, trade = self._close_position(pos, bar, reason, exit_price)
                cash += capital_returned
                all_trades.append(trade)
                per_pair_trades[pos.symbol].append(trade)
                open_symbols.discard(pos.symbol)
                open_positions.pop(idx)

            # === EXIT 2: PORTFOLIO HEAT (after individual exits) ===
            # Check if portfolio DD from peak exceeds threshold
            # Compute current equity (cash + unrealized)
            total_unrealized = sum(
                self._unrealized_pnl(pos, bar) for pos in open_positions
            )
            current_equity = cash + sum(pos.capital for pos in open_positions) + total_unrealized
            if current_equity > peak_equity:
                peak_equity = current_equity
            dd_from_peak = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0

            if dd_from_peak > self.portfolio_heat and len(open_positions) > 0:
                # Close worst performer
                worst_idx = -1
                worst_pnl = float("inf")
                for i, pos in enumerate(open_positions):
                    unrealized = self._unrealized_pnl(pos, bar)
                    if unrealized < worst_pnl:
                        worst_pnl = unrealized
                        worst_idx = i
                if worst_idx >= 0:
                    pos = open_positions[worst_idx]
                    current_price = self._close[pos.symbol][bar]
                    capital_returned, trade = self._close_position(
                        pos, bar, REASON_PORTFOLIO_HEAT, current_price
                    )
                    cash += capital_returned
                    all_trades.append(trade)
                    per_pair_trades[pos.symbol].append(trade)
                    open_symbols.discard(pos.symbol)
                    open_positions.pop(worst_idx)

            # ── 3. Collect entry candidates ──
            candidates: list[tuple[str, int, float]] = []  # (symbol, direction, signal_strength)

            for sym in self.symbols:
                if sym in open_symbols:
                    continue
                if bar >= len(self._buy[sym]):
                    continue
                if self._buy[sym][bar]:
                    candidates.append((sym, 1, float(self._sig_str[sym][bar])))
                elif self._sell[sym][bar]:
                    candidates.append((sym, -1, float(self._sig_str[sym][bar])))

            # ── 4. Filter candidates ──
            filtered: list[tuple[str, int, float]] = []
            for sym, direction, strength in candidates:
                # Max concurrent check
                if len(open_positions) >= self.max_concurrent:
                    break

                # Cluster max check
                cluster = get_cluster(sym)
                if cluster in self.cluster_max:
                    if self._count_cluster(cluster, open_positions) >= self.cluster_max[cluster]:
                        continue

                # Correlation gate
                corr_open = self._correlated_open_count(sym, open_positions)
                if corr_open >= CORRELATION_GATE_MAX_OPEN:
                    if strength < SIGNAL_STRENGTH_GATED:
                        continue

                filtered.append((sym, direction, strength))

            # ── 5. Rank by signal_strength descending ──
            filtered.sort(key=lambda x: x[2], reverse=True)

            # ── 6. Open positions ──
            for sym, direction, strength in filtered:
                if len(open_positions) >= self.max_concurrent:
                    break

                # Re-check cluster after earlier openings this bar
                cluster = get_cluster(sym)
                if cluster in self.cluster_max:
                    if self._count_cluster(cluster, open_positions) >= self.cluster_max[cluster]:
                        continue

                current_price = self._close[sym][bar]
                slippage = get_slippage(sym)

                # Position sizing: inverse-vol + correlation haircut + OI/MC penalty
                atr_dict = {
                    s: float(self._atr[s][bar]) / self._close[s][bar]
                    if self._close[s][bar] > 0 and self._atr[s][bar] > 0
                    else 0.01
                    for s in self.symbols
                }
                open_pair_list = [p.symbol for p in open_positions]
                capital = compute_position_size(
                    sym, open_pair_list, cash, atr_dict, self.corr_matrix,
                )
                if capital <= 0:
                    continue

                if direction == 1:
                    entry_price = current_price * (1.0 + slippage)
                else:
                    entry_price = current_price * (1.0 - slippage)

                position_size = capital / (entry_price * (1.0 + FEE))
                cash -= capital

                params = self.pair_params.get(sym, {})
                pos = OpenPosition(
                    symbol=sym,
                    direction=direction,
                    entry_bar=bar,
                    entry_price=entry_price,
                    size=position_size,
                    capital=capital,
                    highest_price=self._high[sym][bar] if direction == 1 else 0.0,
                    lowest_price=self._low[sym][bar] if direction == -1 else 1e18,
                    trailing_active=False,
                    hard_stop_mult=float(params.get("hard_stop_mult", 2.5)),
                    trail_mult=float(params.get("trail_mult", 3.0)),
                    max_hold_bars=int(params.get("max_hold_bars", 168)),
                )
                open_positions.append(pos)
                open_symbols.add(sym)

            # ── Track stats ──
            if len(open_positions) > max_positions_open:
                max_positions_open = len(open_positions)

            # Track cluster maximums
            cluster_counts: dict[str, int] = {}
            for pos in open_positions:
                c = get_cluster(pos.symbol)
                cluster_counts[c] = cluster_counts.get(c, 0) + 1
            for c, cnt in cluster_counts.items():
                if cnt > max_cluster_open.get(c, 0):
                    max_cluster_open[c] = cnt

            # ── Compute equity at this bar ──
            total_unrealized = sum(
                self._unrealized_pnl(pos, bar) for pos in open_positions
            )
            equity = cash + sum(pos.capital for pos in open_positions) + total_unrealized
            equity_curve[bar] = equity

            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

        # ── FORCE CLOSE all remaining positions at last bar ──
        last_bar = n_bars - 1
        for pos in list(open_positions):
            current_price = self._close[pos.symbol][last_bar]
            capital_returned, trade = self._close_position(
                pos, last_bar, REASON_FORCE_CLOSE, current_price
            )
            cash += capital_returned
            all_trades.append(trade)
            per_pair_trades[pos.symbol].append(trade)

        open_positions.clear()
        open_symbols.clear()

        # Final equity (all positions closed)
        equity = cash
        equity_curve[last_bar] = equity

        return PortfolioResult(
            equity=equity,
            equity_curve=equity_curve,
            all_trades=all_trades,
            per_pair_trades=per_pair_trades,
            max_positions_open=max_positions_open,
            max_cluster_open=max_cluster_open,
            peak_equity=peak_equity,
            max_drawdown=max_drawdown,
        )
