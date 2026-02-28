"""
Technical Indicators
====================
RSI, MACD, ATR, ADX — core indicators for MQE.
RSI: SMA-based (verified identical to EE on VPS).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """SMA-based RSI (not Wilder's EMA)."""
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = pd.Series(gain, index=series.index).rolling(length, min_periods=length).mean()
    avg_loss = pd.Series(loss, index=series.index).rolling(length, min_periods=length).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series,
    fast_period: float = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD with EWM (adjust=False). fast_period can be float."""
    ema_fast = series.ewm(span=fast_period, adjust=False).mean()
    ema_slow = series.ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average Directional Index (ADX)."""
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = np.where(
        (high - prev_high) > (prev_low - low),
        np.maximum(high - prev_high, 0),
        0.0,
    )
    minus_dm = np.where(
        (prev_low - low) > (high - prev_high),
        np.maximum(prev_low - low, 0),
        0.0,
    )

    atr_vals = atr(high, low, close, period)

    plus_dm_smooth = pd.Series(plus_dm, index=high.index).rolling(period, min_periods=period).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=high.index).rolling(period, min_periods=period).mean()

    plus_di = 100 * plus_dm_smooth / atr_vals.replace(0, np.nan)
    minus_di = 100 * minus_dm_smooth / atr_vals.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(period, min_periods=period).mean()
