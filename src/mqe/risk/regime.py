"""BTC Regime Filter — uses BTC 4H MACD state as global market filter.

Uses BTC's Stage 1 optimized MACD params (not hardcoded defaults)
so the regime filter benefits from per-pair optimization.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from mqe.core.backtest import precompute_timeframe_indices
from mqe.core.indicators import macd


def compute_btc_regime(
    btc_data: Dict[str, pd.DataFrame],
    regime_tf: str = "4h",
    btc_stage1_params: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """
    Compute BTC regime aligned to 1H bars.

    Args:
        btc_data: Dict with timeframe keys ("1h", "4h", etc.) mapping to
            OHLCV DataFrames.
        regime_tf: Higher timeframe to use for regime detection.
        btc_stage1_params: BTC's optimized Stage 1 params. Uses MACD params
            from optimization. Falls back to defaults if None.

    Returns:
        1D array (n_1h_bars,): 1=bullish, -1=bearish, 0 where NaN.
    """
    base = btc_data["1h"]
    htf = btc_data[regime_tf]

    p = btc_stage1_params or {}
    macd_line, signal_line, _ = macd(
        htf["close"],
        float(p.get("macd_fast", 10.5)),
        int(p.get("macd_slow", 27)),
        int(p.get("macd_signal", 9)),
    )
    bullish = (macd_line > signal_line).values
    has_nan = np.isnan(macd_line.values) | np.isnan(signal_line.values)

    base_ts = base.index.astype(np.int64) // 10**6
    htf_ts = htf.index.astype(np.int64) // 10**6
    tf_indices = precompute_timeframe_indices(base_ts, htf_ts)

    regime = np.zeros(len(base), dtype=np.float64)
    for i in range(len(base)):
        htf_idx = tf_indices[i]
        if has_nan[htf_idx]:
            regime[i] = np.nan
        elif bullish[htf_idx]:
            regime[i] = 1.0
        else:
            regime[i] = -1.0

    return regime
