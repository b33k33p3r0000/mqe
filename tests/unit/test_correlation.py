"""Unit tests for rolling correlation and cluster logic."""

import numpy as np
import pandas as pd
import pytest

from mqe.risk.correlation import (
    compute_pairwise_correlation,
    compute_rolling_correlation_matrix,
    get_correlated_pairs,
)


def _make_returns(n: int = 1000, seed: int = 42) -> dict:
    """Create synthetic hourly log return series for 3 symbols."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    # BTC: independent random walk
    btc = pd.Series(rng.randn(n) * 0.005, index=dates, name="BTC/USDT")
    # ETH: highly correlated with BTC (0.9× BTC + noise)
    eth = pd.Series(0.9 * btc.values + rng.randn(n) * 0.002, index=dates, name="ETH/USDT")
    # SOL: moderately correlated with BTC (0.4× BTC + noise)
    sol = pd.Series(0.4 * btc.values + rng.randn(n) * 0.005, index=dates, name="SOL/USDT")
    return {"BTC/USDT": btc, "ETH/USDT": eth, "SOL/USDT": sol}


class TestComputeRollingCorrelationMatrix:
    def test_correlation_matrix_shape(self):
        """Matrix should be n_symbols × n_symbols."""
        returns = _make_returns()
        corr = compute_rolling_correlation_matrix(returns, window=200)
        assert corr.shape == (3, 3)

    def test_self_correlation_is_one(self):
        """Diagonal entries should be approximately 1.0."""
        returns = _make_returns()
        corr = compute_rolling_correlation_matrix(returns, window=200)
        for sym in returns:
            assert abs(corr.loc[sym, sym] - 1.0) < 1e-10

    def test_symmetric(self):
        """corr(A,B) should equal corr(B,A)."""
        returns = _make_returns()
        corr = compute_rolling_correlation_matrix(returns, window=200)
        assert abs(corr.loc["BTC/USDT", "ETH/USDT"] - corr.loc["ETH/USDT", "BTC/USDT"]) < 1e-10

    def test_values_in_range(self):
        """All correlation values should be in [-1, 1]."""
        returns = _make_returns()
        corr = compute_rolling_correlation_matrix(returns, window=200)
        assert (corr.values >= -1.0 - 1e-10).all()
        assert (corr.values <= 1.0 + 1e-10).all()

    def test_columns_match_input_symbols(self):
        """Columns and index should match input symbol names."""
        returns = _make_returns()
        corr = compute_rolling_correlation_matrix(returns, window=200)
        assert list(corr.columns) == list(returns.keys())
        assert list(corr.index) == list(returns.keys())


class TestComputePairwiseCorrelation:
    def test_excludes_self(self):
        """Pairwise dict should not contain self-correlations."""
        returns = _make_returns()
        result = compute_pairwise_correlation(returns, window=200)
        for sym in returns:
            assert sym not in result[sym]

    def test_highly_correlated_detected(self):
        """ETH should be highly correlated with BTC."""
        returns = _make_returns()
        result = compute_pairwise_correlation(returns, window=200)
        btc_eth = result["BTC/USDT"]["ETH/USDT"]
        assert btc_eth > 0.8, f"Expected high correlation, got {btc_eth}"

    def test_symmetric_values(self):
        """corr(A,B) == corr(B,A) in pairwise dict."""
        returns = _make_returns()
        result = compute_pairwise_correlation(returns, window=200)
        assert abs(
            result["BTC/USDT"]["ETH/USDT"] - result["ETH/USDT"]["BTC/USDT"]
        ) < 1e-10


class TestGetCorrelatedPairs:
    def test_empty_when_no_open(self):
        """Returns 0 when no open pairs."""
        corr_dict = {
            "BTC/USDT": {"ETH/USDT": 0.9, "SOL/USDT": 0.4},
            "ETH/USDT": {"BTC/USDT": 0.9, "SOL/USDT": 0.5},
            "SOL/USDT": {"BTC/USDT": 0.4, "ETH/USDT": 0.5},
        }
        result = get_correlated_pairs("BTC/USDT", [], corr_dict)
        assert result == 0

    def test_counts_above_threshold(self):
        """Counts pairs with correlation > threshold."""
        corr_dict = {
            "BTC/USDT": {"ETH/USDT": 0.9, "SOL/USDT": 0.4},
            "ETH/USDT": {"BTC/USDT": 0.9, "SOL/USDT": 0.5},
            "SOL/USDT": {"BTC/USDT": 0.4, "ETH/USDT": 0.5},
        }
        # ETH is above 0.75 threshold, SOL is below
        result = get_correlated_pairs(
            "BTC/USDT", ["ETH/USDT", "SOL/USDT"], corr_dict, threshold=0.75
        )
        assert result == 1

    def test_counts_all_above_threshold(self):
        """All open pairs above threshold should be counted."""
        corr_dict = {
            "BTC/USDT": {"ETH/USDT": 0.9, "SOL/USDT": 0.85},
        }
        result = get_correlated_pairs(
            "BTC/USDT", ["ETH/USDT", "SOL/USDT"], corr_dict, threshold=0.75
        )
        assert result == 2

    def test_unknown_symbol_returns_zero(self):
        """Unknown symbol returns 0."""
        corr_dict = {
            "BTC/USDT": {"ETH/USDT": 0.9},
        }
        result = get_correlated_pairs("DOGE/USDT", ["ETH/USDT"], corr_dict)
        assert result == 0

    def test_negative_correlation_counted(self):
        """Strong negative correlation also counted (abs > threshold)."""
        corr_dict = {
            "BTC/USDT": {"ETH/USDT": -0.85},
        }
        result = get_correlated_pairs(
            "BTC/USDT", ["ETH/USDT"], corr_dict, threshold=0.75
        )
        assert result == 1
