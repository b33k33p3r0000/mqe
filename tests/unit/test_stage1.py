"""Unit tests for MQE Stage 1 per-pair optimizer."""

import math

import numpy as np
import pandas as pd
import pytest

from mqe.stage1 import (
    compute_objective_score,
    compute_awf_splits,
    build_objective,
    create_sampler,
    run_stage1_pair,
)
from tests.conftest import make_1h_ohlcv_pd, resample_to_multi_tf


# ─── compute_objective_score ────────────────────────────────────────────────


class TestComputeObjectiveScore:
    def test_positive_for_good_calmar(self):
        """Good raw Calmar + decent trades/year => positive score."""
        score = compute_objective_score(
            raw_calmar=5.0, sharpe=1.5, trades_per_year=100,
        )
        assert score > 0.0
        # log(1 + 5) * min(1, 100/100) = log(6) ~ 1.79
        expected = math.log(1.0 + 5.0) * 1.0
        assert abs(score - expected) < 0.01

    def test_zero_for_negative_calmar(self):
        """raw_calmar=0 => log(1+0)=0 => score=0."""
        score = compute_objective_score(
            raw_calmar=0.0, sharpe=1.0, trades_per_year=100,
        )
        assert score == 0.0

    def test_zero_for_zero_trades(self):
        """No trades => trade_mult=0 => score=0."""
        score = compute_objective_score(
            raw_calmar=5.0, sharpe=1.0, trades_per_year=0,
        )
        assert score == 0.0

    def test_trade_ramp_partial(self):
        """50 trades/year vs 100 target => trade_mult=0.5."""
        score_full = compute_objective_score(
            raw_calmar=3.0, sharpe=1.0, trades_per_year=100,
        )
        score_half = compute_objective_score(
            raw_calmar=3.0, sharpe=1.0, trades_per_year=50,
        )
        assert abs(score_half - score_full * 0.5) < 0.01

    def test_sharpe_decay_penalty(self):
        """Sharpe > 3.0 triggers penalty."""
        score_normal = compute_objective_score(
            raw_calmar=3.0, sharpe=2.0, trades_per_year=100,
        )
        score_suspect = compute_objective_score(
            raw_calmar=3.0, sharpe=5.0, trades_per_year=100,
        )
        assert score_suspect < score_normal

    def test_sharpe_at_threshold_no_penalty(self):
        """Sharpe exactly at 3.0 => no penalty."""
        score_a = compute_objective_score(
            raw_calmar=3.0, sharpe=2.9, trades_per_year=100,
        )
        score_b = compute_objective_score(
            raw_calmar=3.0, sharpe=3.0, trades_per_year=100,
        )
        assert abs(score_a - score_b) < 0.01

    def test_zero_for_bad_metrics_combined(self):
        """All bad: raw_calmar=0, sharpe=0, trades=0 => 0."""
        score = compute_objective_score(
            raw_calmar=0.0, sharpe=0.0, trades_per_year=0.0,
        )
        assert score == 0.0


# ─── compute_awf_splits ────────────────────────────────────────────────────


class TestComputeAwfSplits:
    def test_returns_none_for_short_data(self):
        """Data below minimum => None."""
        result = compute_awf_splits(total_hours=1000)
        assert result is None

    def test_returns_splits_for_long_data(self):
        """Enough data => list of splits."""
        splits = compute_awf_splits(total_hours=20000)
        assert splits is not None
        assert len(splits) >= 2

    def test_splits_have_required_keys(self):
        splits = compute_awf_splits(total_hours=20000)
        assert splits is not None
        for s in splits:
            assert "train_end" in s
            assert "test_start" in s
            assert "test_end" in s

    def test_test_start_after_train_end(self):
        """Purge gap means test_start > train_end."""
        splits = compute_awf_splits(total_hours=20000)
        assert splits is not None
        for s in splits:
            assert s["test_start"] > s["train_end"]

    def test_custom_n_splits(self):
        splits = compute_awf_splits(total_hours=20000, n_splits=4)
        assert splits is not None
        assert len(splits) == 4


# ─── build_objective ────────────────────────────────────────────────────────


class TestBuildObjective:
    def test_returns_callable(self):
        """build_objective returns a function."""
        df_1h = make_1h_ohlcv_pd(n_bars=5000, seed=42)
        data = resample_to_multi_tf(df_1h)
        splits = compute_awf_splits(total_hours=5000)
        assert splits is not None
        obj = build_objective("BTC/USDT", data, splits)
        assert callable(obj)

    def test_callable_returns_float(self):
        """Objective returns a float when called with a trial."""
        import optuna

        df_1h = make_1h_ohlcv_pd(n_bars=5000, seed=42)
        data = resample_to_multi_tf(df_1h)
        splits = compute_awf_splits(total_hours=5000)
        assert splits is not None

        obj = build_objective("BTC/USDT", data, splits)

        study = optuna.create_study(direction="maximize")
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study.optimize(obj, n_trials=1, show_progress_bar=False)
        assert isinstance(study.best_value, float)


# ─── run_stage1_pair ────────────────────────────────────────────────────────


class TestRunStage1Pair:
    @pytest.fixture
    def synthetic_data(self):
        """Create synthetic data dict for Stage 1 test."""
        df_1h = make_1h_ohlcv_pd(n_bars=5000, seed=42)
        return resample_to_multi_tf(df_1h)

    def test_returns_result_dict(self, synthetic_data):
        """run_stage1_pair returns a dict."""
        result = run_stage1_pair(
            symbol="BTC/USDT",
            data=synthetic_data,
            n_trials=20,
            seed=42,
        )
        assert isinstance(result, dict)

    def test_result_has_best_params(self, synthetic_data):
        """Result dict contains all 14 strategy params."""
        result = run_stage1_pair(
            symbol="BTC/USDT",
            data=synthetic_data,
            n_trials=20,
            seed=42,
        )
        expected_params = [
            "macd_fast", "macd_slow", "macd_signal",
            "rsi_period", "rsi_lower", "rsi_upper", "rsi_lookback",
            "trend_tf", "trend_strict", "allow_flip",
            "adx_threshold", "trail_mult", "hard_stop_mult", "max_hold_bars",
        ]
        for p in expected_params:
            assert p in result, f"Missing param: {p}"

    def test_result_has_metrics(self, synthetic_data):
        """Result dict has performance metrics."""
        result = run_stage1_pair(
            symbol="BTC/USDT",
            data=synthetic_data,
            n_trials=20,
            seed=42,
        )
        assert "objective_value" in result
        assert "n_trials_completed" in result

    def test_result_objective_is_non_negative(self, synthetic_data):
        """Objective value >= 0."""
        result = run_stage1_pair(
            symbol="BTC/USDT",
            data=synthetic_data,
            n_trials=20,
            seed=42,
        )
        assert result["objective_value"] >= 0.0


# ─── create_sampler ─────────────────────────────────────────────────────────


class TestCreateSampler:
    def test_returns_tpe_sampler(self):
        import optuna
        sampler = create_sampler(seed=42, n_trials=100)
        assert isinstance(sampler, optuna.samplers.TPESampler)
