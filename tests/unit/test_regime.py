"""Unit tests for BTC regime filter."""

import numpy as np
import pandas as pd

from mqe.risk.regime import compute_btc_regime
from tests.conftest import make_1h_ohlcv_pd, resample_to_multi_tf


class TestBTCRegime:
    def test_returns_correct_length(self):
        df = make_1h_ohlcv_pd(500, seed=42)
        data = resample_to_multi_tf(df)
        regime = compute_btc_regime(data)
        assert len(regime) == len(df)

    def test_values_are_valid(self):
        """Regime values: 1=bullish, -1=bearish, 0=neutral."""
        df = make_1h_ohlcv_pd(500, seed=42)
        data = resample_to_multi_tf(df)
        regime = compute_btc_regime(data)
        valid = regime[~np.isnan(regime)]
        assert set(valid.astype(int)).issubset({-1, 0, 1})
