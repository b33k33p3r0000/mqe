"""Tests for GARCH(1,1) conditional volatility computation."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _make_close_series(n: int = 2000, seed: int = 42) -> pd.Series:
    """Generate synthetic close prices with volatility clustering."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.02, n)
    # Inject vol cluster at bar 1000-1200
    returns[1000:1200] *= 3.0
    prices = 100.0 * np.exp(np.cumsum(returns))
    return pd.Series(prices, name="close")


class TestGarchConditionalVol:
    def test_returns_three_arrays(self):
        from mqe.core.garch import garch_conditional_vol
        close = _make_close_series(1500)
        vol_ratio, cond_vol, lt_vol = garch_conditional_vol(close)
        assert isinstance(vol_ratio, np.ndarray)
        assert isinstance(cond_vol, np.ndarray)
        assert isinstance(lt_vol, np.ndarray)
        assert len(vol_ratio) == len(close)
        assert len(cond_vol) == len(close)
        assert len(lt_vol) == len(close)

    def test_warmup_period_is_neutral(self):
        from mqe.core.garch import garch_conditional_vol
        close = _make_close_series(1500)
        vol_ratio, _, _ = garch_conditional_vol(close, window=720)
        # First 720 bars should be 1.0 (neutral fallback)
        assert np.allclose(vol_ratio[:720], 1.0)

    def test_vol_ratio_clipped(self):
        from mqe.core.garch import garch_conditional_vol
        from mqe.config import GARCH_VOL_RATIO_MIN, GARCH_VOL_RATIO_MAX
        close = _make_close_series(2000)
        vol_ratio, _, _ = garch_conditional_vol(close)
        assert vol_ratio.min() >= GARCH_VOL_RATIO_MIN - 1e-9
        assert vol_ratio.max() <= GARCH_VOL_RATIO_MAX + 1e-9

    def test_vol_spike_lowers_ratio(self):
        from mqe.core.garch import garch_conditional_vol
        close = _make_close_series(2000)
        vol_ratio, _, _ = garch_conditional_vol(close)
        # After vol cluster (bars 1000-1200), vol_ratio should drop below 1.0
        post_spike = vol_ratio[1100:1250]
        assert post_spike.mean() < 1.0, "Vol spike should lower vol_ratio"

    def test_fallback_on_short_data(self):
        from mqe.core.garch import garch_conditional_vol
        close = _make_close_series(500)  # shorter than window
        vol_ratio, _, _ = garch_conditional_vol(close, window=720)
        # All neutral when data shorter than window
        assert np.allclose(vol_ratio, 1.0)

    def test_no_nans_in_output(self):
        from mqe.core.garch import garch_conditional_vol
        close = _make_close_series(2000)
        vol_ratio, cond_vol, lt_vol = garch_conditional_vol(close)
        assert not np.any(np.isnan(vol_ratio))
        assert not np.any(np.isnan(cond_vol))
        assert not np.any(np.isnan(lt_vol))
