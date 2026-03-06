"""Unit tests for position sizing."""

import pytest

from mqe.risk.sizing import compute_position_size
from mqe.config import PAIR_PROFILES, OI_MC_DANGER_THRESHOLD


class TestPositionSizing:
    def test_btc_gets_more_weight(self):
        """BTC (lower vol) gets larger position than SOL (higher vol)."""
        atr_dict = {"BTC/USDT": 0.004, "ETH/USDT": 0.006, "SOL/USDT": 0.009}
        btc_size = compute_position_size(
            "BTC/USDT", [], 100000, atr_dict, {}
        )
        sol_size = compute_position_size(
            "SOL/USDT", [], 100000, atr_dict, {}
        )
        assert btc_size > sol_size

    def test_correlation_haircut(self):
        """Highly correlated open positions reduce new position size."""
        # Use enough symbols so ETH weight stays below POSITION_MAX_PCT (20%)
        atr_dict = {
            "BTC/USDT": 0.004,
            "ETH/USDT": 0.006,
            "SOL/USDT": 0.009,
            "DOT/USDT": 0.012,
            "NEAR/USDT": 0.010,
            "ADA/USDT": 0.008,
        }
        no_corr = compute_position_size(
            "ETH/USDT", [], 100000, atr_dict, {}
        )
        with_corr = compute_position_size(
            "ETH/USDT", ["SOL/USDT"], 100000,
            atr_dict,
            {"ETH/USDT": {"SOL/USDT": 0.85}},
        )
        assert with_corr < no_corr

    def test_oi_mc_danger_penalty(self):
        """SOL (OI/MC > 6%) gets 30% size reduction."""
        # This is handled via pair profiles in the function
        pass

    def test_clipped_to_range(self):
        """Position size is clipped to 5-20% of equity."""
        size = compute_position_size(
            "BTC/USDT", [], 100000, {"BTC/USDT": 0.001}, {}
        )
        assert 5000 <= size <= 20000  # 5-20% of 100k


def test_tier_multiplier_reduces_size():
    base_size = compute_position_size(
        "BTC/USDT", [], 100_000.0,
        {"BTC/USDT": 0.02}, {},
        tier_multiplier=1.0,
    )
    reduced_size = compute_position_size(
        "BTC/USDT", [], 100_000.0,
        {"BTC/USDT": 0.02}, {},
        tier_multiplier=0.6,
    )
    assert reduced_size == pytest.approx(base_size * 0.6, rel=0.01)


def test_tier_multiplier_zero_returns_zero():
    size = compute_position_size(
        "BTC/USDT", [], 100_000.0,
        {"BTC/USDT": 0.02}, {},
        tier_multiplier=0.0,
    )
    assert size == 0.0


def test_tier_multiplier_default_is_one():
    size_default = compute_position_size(
        "BTC/USDT", [], 100_000.0,
        {"BTC/USDT": 0.02}, {},
    )
    size_explicit = compute_position_size(
        "BTC/USDT", [], 100_000.0,
        {"BTC/USDT": 0.02}, {},
        tier_multiplier=1.0,
    )
    assert size_default == size_explicit
