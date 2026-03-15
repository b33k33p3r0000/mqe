"""Shared test fixtures and factory functions for MQE tests."""

from typing import Optional, List, Tuple

import numpy as np
import pandas as pd


def make_pair_signals(
    n_bars: int,
    buy_bars: Optional[List[int]] = None,
    sell_bars: Optional[List[int]] = None,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Create synthetic signal arrays (buy, sell, atr, signal_strength) for testing.

    Returns 4-tuple of numpy arrays: (buy_bool, sell_bool, atr_float64, strength_float64).
    """
    rng = np.random.RandomState(seed)
    buy = np.zeros(n_bars, dtype=np.bool_)
    sell = np.zeros(n_bars, dtype=np.bool_)
    if buy_bars:
        for b in buy_bars:
            if b < n_bars:
                buy[b] = True
    if sell_bars:
        for s in sell_bars:
            if s < n_bars:
                sell[s] = True
    atr_arr = np.full(n_bars, 2.0)
    sig_str = rng.rand(n_bars).astype(np.float64)
    return buy, sell, atr_arr, sig_str


def make_1h_ohlcv_pd(n_bars: int = 500, seed: int = 42, start: str = "2025-01-01") -> pd.DataFrame:
    """Create random-walk 1H OHLCV DataFrame (Pandas — for Numba compat)."""
    np.random.seed(seed)
    dates = pd.date_range(start, periods=n_bars, freq="1h")
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    high = close + np.abs(np.random.randn(n_bars))
    low = close - np.abs(np.random.randn(n_bars))
    open_ = close + np.random.randn(n_bars) * 0.2
    volume = np.random.randint(100, 10000, n_bars).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def resample_to_multi_tf(df_1h: pd.DataFrame) -> dict:
    """Resample 1H Pandas DataFrame to dict with 1h/4h/8h/1d keys."""
    data = {"1h": df_1h}
    for tf, rule in [("4h", "4h"), ("8h", "8h"), ("1d", "1D")]:
        resampled = df_1h.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        ).dropna()
        data[tf] = resampled
    return data
