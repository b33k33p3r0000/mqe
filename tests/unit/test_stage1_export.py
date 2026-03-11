"""Unit tests for stage1 trial export functions."""

from unittest.mock import MagicMock

import optuna
import pytest

from mqe.stage1 import extract_top_trials, extract_trial_history


# ─── Helpers ────────────────────────────────────────────────────────────────


_DEFAULT_USER_ATTRS = {
    "sharpe_equity": 1.5,
    "max_drawdown": -10.0,
    "total_pnl_pct": 50.0,
    "trades_per_year": 80.0,
}

_SENTINEL = object()


def _make_frozen_trial(
    number: int,
    value: float,
    state: optuna.trial.TrialState = optuna.trial.TrialState.COMPLETE,
    user_attrs: dict = _SENTINEL,
) -> optuna.trial.FrozenTrial:
    """Create a minimal FrozenTrial for testing."""
    t = MagicMock(spec=optuna.trial.FrozenTrial)
    t.number = number
    t.value = value
    t.state = state
    t.params = {"macd_fast": 5.0, "rsi_period": 14}
    t.user_attrs = _DEFAULT_USER_ATTRS if user_attrs is _SENTINEL else user_attrs
    return t


def _make_study(trials: list) -> MagicMock:
    study = MagicMock(spec=optuna.Study)
    study.trials = trials
    return study


# ─── extract_top_trials ─────────────────────────────────────────────────────


class TestExtractTopTrials:
    def test_returns_list(self):
        trials = [_make_frozen_trial(i, float(i)) for i in range(5)]
        study = _make_study(trials)
        result = extract_top_trials(study)
        assert isinstance(result, list)

    def test_sorted_descending(self):
        trials = [_make_frozen_trial(i, float(i)) for i in range(5)]
        study = _make_study(trials)
        result = extract_top_trials(study)
        objectives = [r["objective"] for r in result]
        assert objectives == sorted(objectives, reverse=True)

    def test_has_required_keys(self):
        trials = [_make_frozen_trial(0, 1.5)]
        study = _make_study(trials)
        result = extract_top_trials(study)
        assert len(result) == 1
        item = result[0]
        assert "number" in item
        assert "objective" in item
        assert "params" in item
        assert "metrics" in item
        assert "sharpe_equity" in item["metrics"]
        assert "max_drawdown" in item["metrics"]
        assert "total_pnl_pct" in item["metrics"]
        assert "trades_per_year" in item["metrics"]

    def test_caps_at_max_trials(self):
        trials = [_make_frozen_trial(i, float(i)) for i in range(50)]
        study = _make_study(trials)
        result = extract_top_trials(study, max_trials=10)
        assert len(result) == 10

    def test_skips_pruned_and_failed(self):
        completed = [_make_frozen_trial(0, 2.0, optuna.trial.TrialState.COMPLETE)]
        pruned = [_make_frozen_trial(1, 0.0, optuna.trial.TrialState.PRUNED)]
        failed = [_make_frozen_trial(2, 0.0, optuna.trial.TrialState.FAIL)]
        study = _make_study(completed + pruned + failed)
        result = extract_top_trials(study)
        assert len(result) == 1
        assert result[0]["number"] == 0

    def test_empty_study_returns_empty_list(self):
        study = _make_study([])
        result = extract_top_trials(study)
        assert result == []

    def test_params_floats_rounded(self):
        t = _make_frozen_trial(0, 1.23456789)
        t.params = {"macd_fast": 5.123456789}
        study = _make_study([t])
        result = extract_top_trials(study)
        # float params should be rounded to 6 decimal places
        assert result[0]["params"]["macd_fast"] == round(5.123456789, 6)

    def test_int_params_preserved(self):
        t = _make_frozen_trial(0, 1.0)
        t.params = {"rsi_period": 14}  # int param
        study = _make_study([t])
        result = extract_top_trials(study)
        assert result[0]["params"]["rsi_period"] == 14
        assert isinstance(result[0]["params"]["rsi_period"], int)

    def test_missing_user_attrs_default_zero(self):
        t = _make_frozen_trial(0, 1.0, user_attrs={})  # empty dict — no attrs set
        study = _make_study([t])
        result = extract_top_trials(study)
        metrics = result[0]["metrics"]
        assert metrics["sharpe_equity"] == 0.0
        assert metrics["max_drawdown"] == 0.0
        assert metrics["total_pnl_pct"] == 0.0
        assert metrics["trades_per_year"] == 0.0


# ─── extract_trial_history ──────────────────────────────────────────────────


class TestExtractTrialHistory:
    def _make_history_study(self, values: list[float]) -> MagicMock:
        trials = []
        for i, v in enumerate(values):
            t = _make_frozen_trial(i, v)
            trials.append(t)
        return _make_study(trials)

    def test_has_required_keys(self):
        study = self._make_history_study([1.0, 2.0, 3.0])
        result = extract_trial_history(study)
        assert "trial_numbers" in result
        assert "objective_values" in result
        assert "best_so_far" in result

    def test_lengths_match(self):
        study = self._make_history_study([1.0, 0.5, 2.0, 1.5])
        result = extract_trial_history(study)
        n = len(result["trial_numbers"])
        assert len(result["objective_values"]) == n
        assert len(result["best_so_far"]) == n

    def test_best_so_far_monotonic(self):
        study = self._make_history_study([1.0, 0.5, 2.0, 1.5, 3.0])
        result = extract_trial_history(study)
        bsf = result["best_so_far"]
        for i in range(1, len(bsf)):
            assert bsf[i] >= bsf[i - 1], f"best_so_far not monotonic at index {i}"

    def test_best_so_far_correct_values(self):
        study = self._make_history_study([1.0, 0.5, 2.0])
        result = extract_trial_history(study)
        assert result["best_so_far"] == [1.0, 1.0, 2.0]

    def test_samples_large_datasets(self):
        values = [float(i) for i in range(3000)]
        study = self._make_history_study(values)
        result = extract_trial_history(study, max_points=200)
        assert len(result["trial_numbers"]) <= 210  # allow small overshoot for last-point append

    def test_pruned_trial_gets_zero_value(self):
        completed = _make_frozen_trial(0, 2.0, optuna.trial.TrialState.COMPLETE)
        pruned = _make_frozen_trial(1, None, optuna.trial.TrialState.PRUNED)
        pruned.value = None
        study = _make_study([completed, pruned])
        result = extract_trial_history(study)
        assert result["objective_values"][1] == 0.0

    def test_empty_study(self):
        study = _make_study([])
        result = extract_trial_history(study)
        assert result["trial_numbers"] == []
        assert result["objective_values"] == []
        assert result["best_so_far"] == []

    def test_trial_numbers_sequential(self):
        study = self._make_history_study([1.0, 2.0, 3.0])
        result = extract_trial_history(study)
        assert result["trial_numbers"] == [0, 1, 2]
