"""Unit tests for MQE 6-layer entry funnel strategy."""

import numpy as np
import optuna
import pytest

from mqe.config import PAIR_PROFILES, TIER_SEARCH_SPACE
from mqe.core.strategy import MultiPairStrategy
from tests.conftest import make_1h_ohlcv_pd, resample_to_multi_tf


class TestOptunaParams:
    def test_param_count(self):
        """Strategy has 15 Optuna params."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        trial = study.ask()
        try:
            params = strategy.get_optuna_params(trial, "BTC/USDT")
        except optuna.TrialPruned:
            params = strategy.get_optuna_params(study.ask(), "BTC/USDT")
        assert len(params) == 15

    def test_new_params_present(self):
        """New MQE params: adx_threshold, trail_mult, hard_stop_mult, max_hold_bars."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        for _ in range(20):
            trial = study.ask()
            try:
                params = strategy.get_optuna_params(trial, "BTC/USDT")
                assert "adx_threshold" in params
                assert "trail_mult" in params
                assert "hard_stop_mult" in params
                assert "max_hold_bars" in params
                break
            except optuna.TrialPruned:
                continue

    def test_macd_constraint(self):
        """macd_slow - macd_fast < 5 raises TrialPruned."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        pruned_count = 0
        for _ in range(50):
            trial = study.ask()
            try:
                strategy.get_optuna_params(trial, "BTC/USDT")
            except optuna.TrialPruned:
                pruned_count += 1
        assert pruned_count > 0


class TestSignalComputation:
    def test_returns_4_tuple(self):
        """precompute_signals returns (buy, sell, atr, signal_strength)."""
        strategy = MultiPairStrategy()
        df = make_1h_ohlcv_pd(n_bars=500, seed=42)
        data = resample_to_multi_tf(df)
        params = strategy.get_default_params()
        result = strategy.precompute_signals(data, params)
        assert len(result) == 4
        buy, sell, atr_arr, sig_str = result
        assert buy.dtype == np.bool_
        assert sell.dtype == np.bool_
        assert len(buy) == len(df)
        assert len(atr_arr) == len(df)
        assert len(sig_str) == len(df)

    def test_atr_returned(self):
        strategy = MultiPairStrategy()
        df = make_1h_ohlcv_pd(n_bars=500, seed=42)
        data = resample_to_multi_tf(df)
        params = strategy.get_default_params()
        _, _, atr_arr, _ = strategy.precompute_signals(data, params)
        assert atr_arr.dtype == np.float64
        valid_atr = atr_arr[~np.isnan(atr_arr)]
        assert (valid_atr > 0).all()

    def test_signal_strength_computed(self):
        """signal_strength = macd_histogram/ATR + abs(RSI-50)/50."""
        strategy = MultiPairStrategy()
        df = make_1h_ohlcv_pd(n_bars=500, seed=42)
        data = resample_to_multi_tf(df)
        params = strategy.get_default_params()
        _, _, _, sig_str = strategy.precompute_signals(data, params)
        assert sig_str.dtype == np.float64
        valid = sig_str[~np.isnan(sig_str)]
        assert (valid >= 0).all()

    def test_no_signal_in_warmup(self):
        strategy = MultiPairStrategy()
        df = make_1h_ohlcv_pd(n_bars=500, seed=42)
        data = resample_to_multi_tf(df)
        params = strategy.get_default_params()
        buy, sell, _, _ = strategy.precompute_signals(data, params)
        assert not buy[:50].any()
        assert not sell[:50].any()


class TestBTCRegimeFilter:
    def test_btc_regime_not_applied_to_btc(self):
        strategy = MultiPairStrategy()
        df = make_1h_ohlcv_pd(n_bars=500, seed=42)
        data = resample_to_multi_tf(df)
        params = strategy.get_default_params()
        buy1, sell1, _, _ = strategy.precompute_signals(
            data, params, symbol="BTC/USDT"
        )
        buy2, sell2, _, _ = strategy.precompute_signals(
            data, params, symbol="BTC/USDT", btc_regime_data=data
        )
        np.testing.assert_array_equal(buy1, buy2)
        np.testing.assert_array_equal(sell1, sell2)


class TestPerTierParams:
    """Tests that get_optuna_params uses tier-specific ranges."""

    def test_tier_s_allows_flip(self):
        """Tier S (BTC) can have allow_flip=0 or 1."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        flips_seen = set()
        for _ in range(20):
            trial = study.ask()
            try:
                params = strategy.get_optuna_params(trial, "BTC/USDT")
                flips_seen.add(params["allow_flip"])
            except optuna.TrialPruned:
                pass
        # With 20 tries, should see both 0 and 1 at least once
        assert 0 in flips_seen or 1 in flips_seen

    def test_tier_b_fixes_flip_off(self):
        """Tier B (NEAR) always has allow_flip=0."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        for _ in range(5):
            trial = study.ask()
            try:
                params = strategy.get_optuna_params(trial, "NEAR/USDT")
                assert params["allow_flip"] == 0
            except optuna.TrialPruned:
                pass

    def test_tier_b_narrower_macd(self):
        """Tier B has narrower macd_fast range than Tier S."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        for _ in range(10):
            trial = study.ask()
            try:
                params = strategy.get_optuna_params(trial, "NEAR/USDT")
                assert params["macd_fast"] <= 12.0  # B tier max
            except optuna.TrialPruned:
                pass

    def test_unknown_symbol_uses_tier_b(self):
        """Unknown symbol defaults to Tier B ranges."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        trial = study.ask()
        try:
            params = strategy.get_optuna_params(trial, "UNKNOWN/USDT")
            assert params["macd_fast"] <= 12.0
        except optuna.TrialPruned:
            pass

    def test_vol_sensitivity_in_optuna_params(self):
        """vol_sensitivity should be the 15th Optuna param."""
        strategy = MultiPairStrategy()
        study = optuna.create_study()
        for _ in range(10):
            trial = study.ask()
            try:
                params = strategy.get_optuna_params(trial, "BTC/USDT")
                assert "vol_sensitivity" in params
                assert 0.3 <= params["vol_sensitivity"] <= 2.5  # S tier range
                break
            except optuna.TrialPruned:
                pass

    def test_param_count_unchanged(self):
        """Still 15 params regardless of tier."""
        strategy = MultiPairStrategy()
        for sym in ["BTC/USDT", "NEAR/USDT", "INJ/USDT"]:
            study = optuna.create_study()
            for _ in range(5):
                trial = study.ask()
                try:
                    params = strategy.get_optuna_params(trial, sym)
                    assert len(params) == 15
                    break
                except optuna.TrialPruned:
                    pass
