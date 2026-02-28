"""
MQE Multi-Pair Strategy -- 6-Layer Entry Funnel
================================================

Layers:
  1. MACD crossover (per-pair)
  2. RSI lookback window (per-pair)
  3. HTF trend filter (per-pair)
  4. BTC regime filter (global -- applied externally for non-BTC pairs)
  5. ADX pre-filter (per-pair)
  6. Correlation gate (portfolio-level -- handled by portfolio.py)

14 Optuna parameters per pair.
Returns (buy_signal, sell_signal, atr_values, signal_strength) -- ATR needed for exit system,
signal_strength needed for correlation gate ranking in portfolio.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import optuna
import pandas as pd

from mqe.config import ATR_PERIOD, BASE_TF
from mqe.core.backtest import precompute_timeframe_indices
from mqe.core.indicators import adx, atr, macd, rsi


class BaseStrategy(ABC):
    name: str = "base"
    version: str = "1.0.0"

    @abstractmethod
    def get_optuna_params(
        self,
        trial: optuna.trial.Trial,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def precompute_signals(
        self,
        data: dict[str, Any],
        params: dict[str, Any],
        precomputed_cache: dict[str, Any] | None = None,
        symbol: str | None = None,
        btc_regime_data: dict[str, Any] | None = None,
        btc_stage1_params: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Returns (buy_signal, sell_signal, atr_values, signal_strength)."""
        pass

    def get_default_params(self) -> dict[str, Any]:
        return {}


class MultiPairStrategy(BaseStrategy):
    """
    MQE 6-Layer Funnel: MACD crossover + RSI lookback + HTF trend
    + BTC regime + ADX filter + correlation gate.
    """

    name = "multi_pair_funnel"
    version = "1.0.0"

    def get_optuna_params(
        self,
        trial: optuna.trial.Trial,
        symbol: str | None = None,
        allow_flip_override: Optional[int] = None,
    ) -> dict[str, Any]:
        """14 Optuna parameters per pair."""
        params: dict[str, Any] = {}

        # -- Layers 1-3 (from QRE) --
        params["macd_fast"] = trial.suggest_float("macd_fast", 1.0, 20.0)
        params["macd_slow"] = trial.suggest_int("macd_slow", 10, 45)
        if params["macd_slow"] - params["macd_fast"] < 5:
            raise optuna.TrialPruned("macd_slow - macd_fast < 5")

        params["macd_signal"] = trial.suggest_int("macd_signal", 3, 15)
        params["rsi_period"] = trial.suggest_int("rsi_period", 3, 30)
        params["rsi_lower"] = trial.suggest_int("rsi_lower", 20, 40)
        params["rsi_upper"] = trial.suggest_int("rsi_upper", 60, 80)
        params["rsi_lookback"] = trial.suggest_int("rsi_lookback", 1, 4)
        params["trend_tf"] = trial.suggest_categorical(
            "trend_tf", ["4h", "8h", "1d"]
        )
        params["trend_strict"] = trial.suggest_int("trend_strict", 1, 1)

        flip_val = allow_flip_override if allow_flip_override is not None else 0
        params["allow_flip"] = trial.suggest_int("allow_flip", flip_val, flip_val)

        # -- Layer 5: ADX (NEW) --
        params["adx_threshold"] = trial.suggest_float("adx_threshold", 15.0, 30.0)

        # -- Exit params (NEW) --
        params["trail_mult"] = trial.suggest_float("trail_mult", 2.0, 4.0)
        params["hard_stop_mult"] = trial.suggest_float("hard_stop_mult", 1.5, 3.0)
        params["max_hold_bars"] = trial.suggest_int("max_hold_bars", 48, 168)

        return params

    def precompute_signals(
        self,
        data: dict[str, Any],
        params: dict[str, Any],
        precomputed_cache: dict[str, Any] | None = None,
        symbol: str | None = None,
        btc_regime_data: dict[str, Any] | None = None,
        btc_stage1_params: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute buy/sell signals + ATR array + signal strength.

        Args:
            btc_stage1_params: BTC's optimized Stage 1 params -- used for BTC regime
                filter (MACD params). If None, uses pair's own params as fallback.

        Returns: (buy_signal, sell_signal, atr_values, signal_strength)
        """
        base = data[BASE_TF]
        n_bars = len(base)

        # -- Params --
        macd_fast = float(params.get("macd_fast", 10.5))
        macd_slow = int(params.get("macd_slow", 27))
        macd_signal_period = int(params.get("macd_signal", 9))
        rsi_period = int(params.get("rsi_period", 14))
        rsi_lower = int(params.get("rsi_lower", 30))
        rsi_upper = int(params.get("rsi_upper", 70))
        rsi_lookback = int(params.get("rsi_lookback", 3))
        trend_tf = params.get("trend_tf", "8h")
        trend_strict = int(params.get("trend_strict", 1))
        adx_threshold = float(params.get("adx_threshold", 20.0))

        # -- Layer 1: MACD crossover --
        macd_line, signal_line, histogram = macd(
            base["close"], macd_fast, macd_slow, macd_signal_period
        )
        macd_vals = macd_line.values.astype(np.float64)
        signal_vals = signal_line.values.astype(np.float64)

        macd_prev = np.roll(macd_vals, 1)
        signal_prev = np.roll(signal_vals, 1)
        macd_prev[0] = np.nan
        signal_prev[0] = np.nan

        macd_bullish_cross = (macd_prev <= signal_prev) & (macd_vals > signal_vals)
        macd_bearish_cross = (macd_prev >= signal_prev) & (macd_vals < signal_vals)

        # -- Layer 2: RSI lookback --
        if (
            precomputed_cache
            and "rsi" in precomputed_cache
            and rsi_period in precomputed_cache["rsi"]
        ):
            rsi_vals = precomputed_cache["rsi"][rsi_period]
        else:
            rsi_vals = rsi(base["close"], rsi_period).values.astype(np.float64)

        rsi_oversold = rsi_vals < rsi_lower
        rsi_overbought = rsi_vals > rsi_upper

        if rsi_lookback > 0:
            rsi_oversold = (
                pd.Series(rsi_oversold)
                .rolling(rsi_lookback + 1, min_periods=1)
                .max()
                .astype(bool)
                .values
            )
            rsi_overbought = (
                pd.Series(rsi_overbought)
                .rolling(rsi_lookback + 1, min_periods=1)
                .max()
                .astype(bool)
                .values
            )

        has_nan = np.isnan(macd_vals) | np.isnan(signal_vals) | np.isnan(rsi_vals)

        # -- Layer 3: HTF trend filter --
        if trend_strict and trend_tf in data:
            htf = data[trend_tf]
            htf_macd, htf_signal, _ = macd(
                htf["close"], macd_fast, macd_slow, macd_signal_period
            )
            htf_bullish = (htf_macd > htf_signal).values

            base_ts = base.index.astype(np.int64) // 10**6
            htf_ts = htf.index.astype(np.int64) // 10**6
            tf_indices = precompute_timeframe_indices(base_ts, htf_ts)

            htf_has_nan = np.isnan(htf_macd.values) | np.isnan(htf_signal.values)
            htf_valid = ~htf_has_nan
            htf_bullish_raw = htf_bullish
            htf_bearish_raw = ~htf_bullish_raw

            htf_bullish_aligned = (htf_bullish_raw & htf_valid)[tf_indices]
            htf_bearish_aligned = (htf_bearish_raw & htf_valid)[tf_indices]
        else:
            htf_bullish_aligned = np.ones(n_bars, dtype=bool)
            htf_bearish_aligned = np.ones(n_bars, dtype=bool)

        # -- Layer 4: BTC regime filter --
        # Applied only to non-BTC pairs. Uses BTC's Stage 1 optimized MACD params
        # (not hardcoded defaults) so the regime filter benefits from optimization.
        is_btc = symbol is not None and symbol.startswith("BTC")
        if not is_btc and btc_regime_data is not None and "4h" in btc_regime_data:
            btc_4h = btc_regime_data["4h"]
            # Use BTC Stage 1 params if available, else fall back to this pair's params
            btc_p = btc_stage1_params or params
            btc_macd_l, btc_signal_l, _ = macd(
                btc_4h["close"],
                float(btc_p.get("macd_fast", macd_fast)),
                int(btc_p.get("macd_slow", macd_slow)),
                int(btc_p.get("macd_signal", macd_signal_period)),
            )
            btc_bullish = (btc_macd_l > btc_signal_l).values
            btc_bearish = ~btc_bullish
            btc_has_nan = np.isnan(btc_macd_l.values) | np.isnan(btc_signal_l.values)
            btc_valid = ~btc_has_nan

            base_ts = base.index.astype(np.int64) // 10**6
            btc_4h_ts = btc_4h.index.astype(np.int64) // 10**6
            btc_tf_indices = precompute_timeframe_indices(base_ts, btc_4h_ts)

            btc_bull_aligned = (btc_bullish & btc_valid)[btc_tf_indices]
            btc_bear_aligned = (btc_bearish & btc_valid)[btc_tf_indices]

            # Only longs when BTC bullish, only shorts when BTC bearish
            regime_allows_long = btc_bull_aligned
            regime_allows_short = btc_bear_aligned
        else:
            regime_allows_long = np.ones(n_bars, dtype=bool)
            regime_allows_short = np.ones(n_bars, dtype=bool)

        # -- Layer 5: ADX pre-filter --
        adx_vals = adx(base["high"], base["low"], base["close"], ATR_PERIOD)
        adx_arr = adx_vals.values.astype(np.float64)
        adx_pass = adx_arr >= adx_threshold
        adx_pass[np.isnan(adx_arr)] = False

        # -- Compute ATR for exit system --
        atr_vals = atr(base["high"], base["low"], base["close"], ATR_PERIOD)
        atr_arr = atr_vals.values.astype(np.float64)

        # -- Compute signal strength (for correlation gate ranking) --
        # Composite: MACD histogram strength + RSI distance from 50
        # Used by portfolio.py to rank competing entry signals
        hist_vals = (macd_line - signal_line).values.astype(np.float64)
        safe_atr = np.where(atr_arr > 0, atr_arr, 1e-8)
        macd_strength = np.abs(hist_vals) / safe_atr
        rsi_strength = np.abs(rsi_vals - 50.0) / 50.0
        signal_strength = macd_strength + rsi_strength

        # -- Combined signals (layers 1-5) --
        # Layer 6 (correlation gate) is handled by portfolio.py
        buy_signal = (
            macd_bullish_cross
            & rsi_oversold
            & htf_bullish_aligned
            & regime_allows_long
            & adx_pass
            & ~has_nan
        )
        sell_signal = (
            macd_bearish_cross
            & rsi_overbought
            & htf_bearish_aligned
            & regime_allows_short
            & adx_pass
            & ~has_nan
        )

        return (
            buy_signal.astype(np.bool_),
            sell_signal.astype(np.bool_),
            atr_arr,
            signal_strength,
        )

    def get_default_params(self) -> dict[str, Any]:
        return {
            "macd_fast": 10.5,
            "macd_slow": 27,
            "macd_signal": 9,
            "rsi_period": 14,
            "rsi_lower": 30,
            "rsi_upper": 70,
            "rsi_lookback": 3,
            "trend_tf": "8h",
            "trend_strict": 1,
            "allow_flip": 0,
            "adx_threshold": 20.0,
            "trail_mult": 3.0,
            "hard_stop_mult": 2.5,
            "max_hold_bars": 168,
        }
