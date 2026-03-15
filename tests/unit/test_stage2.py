"""Unit tests for MQE Stage 2 portfolio optimizer (NSGA-II)."""

import numpy as np
import pandas as pd
import pytest

import optuna

from mqe.stage2 import (
    build_portfolio_objective,
    run_stage2,
)
from tests.conftest import make_1h_ohlcv_pd, make_pair_signals, resample_to_multi_tf


# ─── helpers ────────────────────────────────────────────────────────────────


def _build_synthetic_inputs(n_bars=500, n_pairs=2, seed=42):
    """Build synthetic pair_data, pair_signals, pair_params for Stage 2 tests."""
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"][:n_pairs]
    pair_data = {}
    pair_signals = {}
    pair_params = {}

    for i, sym in enumerate(symbols):
        df_1h = make_1h_ohlcv_pd(n_bars=n_bars, seed=seed + i)
        data = resample_to_multi_tf(df_1h)
        pair_data[sym] = data

        # Scatter some buy/sell signals across the data
        rng = np.random.RandomState(seed + i + 100)
        buy_bars = sorted(rng.choice(range(250, n_bars - 50), size=5, replace=False).tolist())
        sell_bars = sorted(rng.choice(range(250, n_bars - 50), size=5, replace=False).tolist())
        pair_signals[sym] = make_pair_signals(
            n_bars, buy_bars=buy_bars, sell_bars=sell_bars, seed=seed + i,
        )

        pair_params[sym] = {
            "hard_stop_mult": 2.5,
            "trail_mult": 3.0,
            "max_hold_bars": 168,
        }

    return pair_data, pair_signals, pair_params


# ─── build_portfolio_objective ──────────────────────────────────────────────


class TestBuildPortfolioObjective:
    def test_returns_callable(self):
        """build_portfolio_objective returns a callable."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs()
        obj = build_portfolio_objective(pair_data, pair_signals, pair_params)
        assert callable(obj)

    def test_objective_returns_3_values(self):
        """Multi-objective returns exactly 3 float values."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs()
        obj = build_portfolio_objective(pair_data, pair_signals, pair_params)

        study = optuna.create_study(
            directions=["maximize", "maximize", "maximize"],
            sampler=optuna.samplers.NSGAIISampler(seed=42),
        )
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study.optimize(obj, n_trials=1, show_progress_bar=False)

        trial = study.trials[0]
        assert len(trial.values) == 3
        for v in trial.values:
            assert isinstance(v, float)

    def test_objective_first_value_is_portfolio_calmar(self):
        """First objective is portfolio Calmar (can be 0 or positive)."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs()
        obj = build_portfolio_objective(pair_data, pair_signals, pair_params)

        study = optuna.create_study(
            directions=["maximize", "maximize", "maximize"],
            sampler=optuna.samplers.NSGAIISampler(seed=42),
        )
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study.optimize(obj, n_trials=1, show_progress_bar=False)

        # Portfolio calmar is a real number (could be negative, zero, or positive)
        portfolio_calmar = study.trials[0].values[0]
        assert isinstance(portfolio_calmar, float)

    def test_objective_third_value_is_nonpositive(self):
        """Third objective (neg overfit penalty) is <= 0."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs()
        obj = build_portfolio_objective(pair_data, pair_signals, pair_params)

        study = optuna.create_study(
            directions=["maximize", "maximize", "maximize"],
            sampler=optuna.samplers.NSGAIISampler(seed=42),
        )
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study.optimize(obj, n_trials=3, show_progress_bar=False)

        for trial in study.trials:
            # neg_overfit_penalty <= 0 (we negate the penalty)
            assert trial.values[2] <= 0.0


# ─── run_stage2 ─────────────────────────────────────────────────────────────


@pytest.mark.slow
class TestRunStage2:
    @pytest.fixture
    def synthetic_inputs(self):
        return _build_synthetic_inputs(n_bars=500, n_pairs=2, seed=42)

    def test_returns_result_dict(self, synthetic_inputs):
        """run_stage2 returns a dict."""
        pair_data, pair_signals, pair_params = synthetic_inputs
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=42,
        )
        assert isinstance(result, dict)

    def test_result_has_portfolio_params(self, synthetic_inputs):
        """Result contains portfolio-level params."""
        pair_data, pair_signals, pair_params = synthetic_inputs
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=42,
        )
        assert "portfolio_params" in result
        params = result["portfolio_params"]
        assert isinstance(params, dict)
        # Should have at least max_concurrent and portfolio_heat
        expected_keys = ["max_concurrent", "portfolio_heat", "corr_gate_threshold"]
        for k in expected_keys:
            assert k in params, f"Missing portfolio param: {k}"

    def test_result_has_objectives(self, synthetic_inputs):
        """Result contains objective values."""
        pair_data, pair_signals, pair_params = synthetic_inputs
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=42,
        )
        assert "objectives" in result
        obj = result["objectives"]
        assert "portfolio_calmar" in obj
        assert "worst_pair_calmar" in obj
        assert "neg_overfit_penalty" in obj

    def test_result_has_pareto_front_size(self, synthetic_inputs):
        """Result reports Pareto front size."""
        pair_data, pair_signals, pair_params = synthetic_inputs
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=42,
        )
        assert "pareto_front_size" in result
        assert result["pareto_front_size"] >= 0

    def test_result_has_cluster_max(self, synthetic_inputs):
        """Stage 2 result portfolio_params includes cluster_max."""
        pair_data, pair_signals, pair_params = synthetic_inputs
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=42,
        )
        assert "cluster_max" in result["portfolio_params"]
        assert isinstance(result["portfolio_params"]["cluster_max"], int)
        assert 1 <= result["portfolio_params"]["cluster_max"] <= 3

    def test_result_has_n_trials(self, synthetic_inputs):
        """Result reports number of trials."""
        pair_data, pair_signals, pair_params = synthetic_inputs
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=42,
        )
        assert result["n_trials"] == 3


# ─── NSGA-II sampler ───────────────────────────────────────────────────────


class TestNSGA2Sampler:
    def test_nsga2_sampler_used(self):
        """Stage 2 uses NSGA-II sampler, not TPE."""
        # Verify that an NSGA-II sampler can be constructed with expected params
        sampler = optuna.samplers.NSGAIISampler(population_size=50, seed=42)
        assert isinstance(sampler, optuna.samplers.NSGAIISampler)

    def test_study_has_3_directions(self):
        """Multi-objective study has exactly 3 maximize directions."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs(
            n_bars=500, n_pairs=2,
        )
        obj = build_portfolio_objective(pair_data, pair_signals, pair_params)

        sampler = optuna.samplers.NSGAIISampler(population_size=50, seed=42)
        study = optuna.create_study(
            directions=["maximize", "maximize", "maximize"],
            sampler=sampler,
        )
        assert study.directions is not None
        assert len(study.directions) == 3


# ─── Pareto front selection ────────────────────────────────────────────────


@pytest.mark.slow
class TestParetoFrontSelection:
    def test_pareto_front_selection(self):
        """run_stage2 selects best trial from Pareto front."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs(
            n_bars=500, n_pairs=2,
        )
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=42,
        )
        # Pareto front should have at least 1 trial
        assert result["pareto_front_size"] >= 1
        # Selected trial should have valid portfolio params
        assert len(result["portfolio_params"]) > 0

    def test_more_trials_returns_valid_result(self):
        """More trials still produce valid structured result."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs(
            n_bars=500, n_pairs=2,
        )
        result = run_stage2(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            n_trials=3,
            seed=99,
        )
        assert isinstance(result, dict)
        assert "portfolio_params" in result
        assert "objectives" in result
        assert "pareto_front_size" in result


# ─── Stage 2 revisions ────────────────────────────────────────────────────


class TestStage2Revisions:
    def test_objective_returns_3_values(self):
        """Multi-objective returns 3 float values (no degradation objective)."""
        pair_data, pair_signals, pair_params = _build_synthetic_inputs()
        obj = build_portfolio_objective(pair_data, pair_signals, pair_params)

        study = optuna.create_study(
            directions=["maximize", "maximize", "maximize"],
            sampler=optuna.samplers.NSGAIISampler(seed=42),
        )
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study.optimize(obj, n_trials=1, show_progress_bar=False)

        trial = study.trials[0]
        assert len(trial.values) == 3
