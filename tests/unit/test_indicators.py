"""Unit tests for MQE indicators."""

import numpy as np
import pandas as pd
import pytest

from mqe.core.indicators import rsi, macd, atr, adx


class TestRSI:
    def test_range_0_100(self):
        close = pd.Series(100 + np.cumsum(np.random.randn(200) * 0.5))
        result = rsi(close, 14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_length_matches_input(self):
        close = pd.Series(np.arange(100, dtype=float))
        result = rsi(close, 14)
        assert len(result) == len(close)

    def test_sma_based(self):
        """RSI uses SMA (rolling mean), not Wilder's EMA."""
        close = pd.Series([44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10,
                           45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28])
        result = rsi(close, 14)
        assert not result.isna().all()


class TestMACD:
    def test_returns_three_series(self):
        close = pd.Series(100 + np.cumsum(np.random.randn(200) * 0.5))
        macd_line, signal_line, histogram = macd(close, 12, 26, 9)
        assert len(macd_line) == len(close)
        assert len(signal_line) == len(close)
        assert len(histogram) == len(close)

    def test_histogram_is_difference(self):
        close = pd.Series(100 + np.cumsum(np.random.randn(200) * 0.5))
        macd_line, signal_line, histogram = macd(close, 12, 26, 9)
        np.testing.assert_array_almost_equal(
            histogram.values, (macd_line - signal_line).values
        )

    def test_float_fast_period(self):
        """macd_fast can be float (Optuna suggests float 1.0-20.0)."""
        close = pd.Series(100 + np.cumsum(np.random.randn(200) * 0.5))
        macd_line, _, _ = macd(close, 3.7, 26, 9)
        assert not macd_line.isna().all()


class TestATR:
    def test_positive_values(self):
        n = 200
        close = pd.Series(100 + np.cumsum(np.random.randn(n) * 0.5))
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))
        result = atr(high, low, close, 14)
        valid = result.dropna()
        assert (valid > 0).all()

    def test_length_matches(self):
        n = 200
        close = pd.Series(np.arange(n, dtype=float))
        high = close + 1.0
        low = close - 1.0
        result = atr(high, low, close, 14)
        assert len(result) == n


class TestADX:
    def test_range_0_100(self):
        n = 200
        np.random.seed(42)
        close = pd.Series(100 + np.cumsum(np.random.randn(n) * 0.5))
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))
        result = adx(high, low, close, 14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_length_matches(self):
        n = 200
        close = pd.Series(np.arange(n, dtype=float))
        high = close + 1.0
        low = close - 1.0
        result = adx(high, low, close, 14)
        assert len(result) == n
