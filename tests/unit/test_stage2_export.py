"""Unit tests for Stage 2 export functions: extract_pareto_front, extract_s2_history."""

import json
import tempfile
from pathlib import Path

import numpy as np
import optuna
import pytest

from mqe.stage2 import extract_pareto_front, extract_s2_history


# ─── helpers ─────────────────────────────────────────────────────────────────


def _make_nsga2_study(n_trials: int = 20, seed: int = 42) -> optuna.Study:
    """Create a small NSGA-II study with 3 objectives for testing."""
    study = optuna.create_study(
        directions=["maximize", "maximize", "maximize"],
        sampler=optuna.samplers.NSGAIISampler(seed=seed),
    )
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.trial.Trial):
        x = trial.suggest_float("x", 0.0, 1.0)
        y = trial.suggest_float("y", 0.0, 1.0)
        return x, y, -(x - 0.5) ** 2

    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study


# ─── extract_pareto_front ────────────────────────────────────────────────────


class TestExtractParetoFront:
    @pytest.fixture
    def study(self):
        return _make_nsga2_study(n_trials=20)

    def test_returns_dict(self, study):
        """extract_pareto_front returns a dict."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        assert isinstance(result, dict)

    def test_has_selected_trial_key(self, study):
        """Result contains selected_trial key matching given trial number."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        assert "selected_trial" in result
        assert result["selected_trial"] == best.number

    def test_has_trials_list(self, study):
        """Result contains trials list."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        assert "trials" in result
        assert isinstance(result["trials"], list)
        assert len(result["trials"]) >= 1

    def test_each_trial_has_required_keys(self, study):
        """Each trial entry has number, params, objectives keys."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        for t in result["trials"]:
            assert "number" in t
            assert "params" in t
            assert "objectives" in t

    def test_objectives_have_3_values(self, study):
        """Each trial objectives dict has 3 keys."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        for t in result["trials"]:
            obj = t["objectives"]
            assert "portfolio_calmar" in obj
            assert "worst_pair_calmar" in obj
            assert "neg_overfit_penalty" in obj

    def test_pareto_size_matches_study_best_trials(self, study):
        """Number of trials in result matches study.best_trials count."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        assert len(result["trials"]) == len(study.best_trials)

    def test_trial_numbers_are_ints(self, study):
        """Trial number field is an integer."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        for t in result["trials"]:
            assert isinstance(t["number"], int)

    def test_objectives_are_floats(self, study):
        """Objective values are floats (rounded to 4 decimals)."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        for t in result["trials"]:
            for v in t["objectives"].values():
                assert isinstance(v, float)

    def test_result_is_json_serializable(self, study):
        """Result can be serialized to JSON without error."""
        best = max(study.best_trials, key=lambda t: t.values[0])
        result = extract_pareto_front(study, best.number)
        serialized = json.dumps(result)
        roundtripped = json.loads(serialized)
        assert roundtripped["selected_trial"] == result["selected_trial"]


# ─── extract_s2_history ──────────────────────────────────────────────────────


class TestExtractS2History:
    @pytest.fixture
    def study(self):
        return _make_nsga2_study(n_trials=30)

    def test_returns_dict(self, study):
        """extract_s2_history returns a dict."""
        result = extract_s2_history(study)
        assert isinstance(result, dict)

    def test_has_required_keys(self, study):
        """Result contains trial_numbers, portfolio_calmar_values, best_calmar_so_far."""
        result = extract_s2_history(study)
        assert "trial_numbers" in result
        assert "portfolio_calmar_values" in result
        assert "best_calmar_so_far" in result

    def test_lengths_match(self, study):
        """All three lists have equal lengths."""
        result = extract_s2_history(study)
        n = len(result["trial_numbers"])
        assert len(result["portfolio_calmar_values"]) == n
        assert len(result["best_calmar_so_far"]) == n

    def test_best_calmar_is_monotonically_nondecreasing(self, study):
        """best_calmar_so_far is monotonically non-decreasing."""
        result = extract_s2_history(study)
        bsf = result["best_calmar_so_far"]
        for i in range(1, len(bsf)):
            assert bsf[i] >= bsf[i - 1], (
                f"best_calmar_so_far decreased at index {i}: {bsf[i-1]} -> {bsf[i]}"
            )

    def test_trial_numbers_are_ints(self, study):
        """trial_numbers are integers."""
        result = extract_s2_history(study)
        for n in result["trial_numbers"]:
            assert isinstance(n, int)

    def test_calmar_values_are_floats(self, study):
        """portfolio_calmar_values and best_calmar_so_far are floats."""
        result = extract_s2_history(study)
        for v in result["portfolio_calmar_values"]:
            assert isinstance(v, float)
        for v in result["best_calmar_so_far"]:
            assert isinstance(v, float)

    def test_max_points_downsampling(self, study):
        """When max_points < n_trials, result is downsampled to at most max_points+1."""
        result = extract_s2_history(study, max_points=10)
        # With 30 trials and max_points=10, result should be <= 11 (indices + possible last)
        assert len(result["trial_numbers"]) <= 11

    def test_no_downsampling_when_within_limit(self, study):
        """When max_points >= n_trials, all trials are included."""
        n_trials = len(study.trials)
        result = extract_s2_history(study, max_points=n_trials + 100)
        assert len(result["trial_numbers"]) == n_trials

    def test_result_is_json_serializable(self, study):
        """Result serializes to JSON without error."""
        result = extract_s2_history(study)
        serialized = json.dumps(result)
        roundtripped = json.loads(serialized)
        assert len(roundtripped["trial_numbers"]) == len(result["trial_numbers"])
