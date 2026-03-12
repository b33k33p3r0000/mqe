"""Tests for PBO (Probability of Backtest Overfitting)."""
from __future__ import annotations

import numpy as np
import pytest


class TestCSCVCombinations:
    def test_correct_combination_count(self):
        from mqe.core.pbo import generate_cscv_combinations
        combos = generate_cscv_combinations(n_subsets=8)
        # C(8,4) = 70
        assert len(combos) == 70

    def test_each_combo_has_train_and_test(self):
        from mqe.core.pbo import generate_cscv_combinations
        combos = generate_cscv_combinations(n_subsets=8)
        for train_idx, test_idx in combos:
            assert len(train_idx) == 4
            assert len(test_idx) == 4
            assert set(train_idx) & set(test_idx) == set()  # disjoint


class TestRandomParamGeneration:
    def test_correct_count(self):
        from mqe.core.pbo import generate_random_params
        params = generate_random_params("BTC/USDT", n_sets=50, seed=42)
        assert len(params) == 50

    def test_params_within_tier_bounds(self):
        from mqe.core.pbo import generate_random_params
        from mqe.config import TIER_SEARCH_SPACE, PAIR_PROFILES
        params = generate_random_params("BTC/USDT", n_sets=10, seed=42)
        tier = PAIR_PROFILES["BTC/USDT"]["tier"]
        space = TIER_SEARCH_SPACE[tier]
        for p in params:
            for key, (lo, hi) in space.items():
                if key in p and key not in ("trend_tf",):
                    assert lo <= p[key] <= hi + 1, f"{key}={p[key]} not in [{lo}, {hi}]"


class TestPBOScore:
    def test_random_strategy_has_moderate_pbo(self):
        """Random params on random data should produce PBO around 0.5."""
        from mqe.core.pbo import compute_pbo_score
        rng = np.random.default_rng(42)
        n_param_sets = 101
        ranks = rng.integers(1, n_param_sets + 1, size=70)
        median_rank = n_param_sets // 2
        pbo = compute_pbo_score(ranks, median_rank)
        assert 0.2 < pbo < 0.8

    def test_perfect_strategy_has_low_pbo(self):
        """If best-in-train always ranks #1 OOS, PBO should be 0."""
        from mqe.core.pbo import compute_pbo_score
        ranks = np.ones(70, dtype=int)  # always rank 1 (best)
        pbo = compute_pbo_score(ranks, median_rank=50)
        assert pbo == 0.0


class TestPBOOverride:
    def test_high_pbo_excludes(self):
        from mqe.core.pbo import apply_pbo_override
        assert apply_pbo_override("A", 0.55) == "X"
        assert apply_pbo_override("B", 0.60) == "X"

    def test_moderate_pbo_demotes(self):
        from mqe.core.pbo import apply_pbo_override
        assert apply_pbo_override("A", 0.35) == "B"
        assert apply_pbo_override("B", 0.40) == "C"
        assert apply_pbo_override("C", 0.45) == "X"

    def test_low_pbo_no_change(self):
        from mqe.core.pbo import apply_pbo_override
        assert apply_pbo_override("A", 0.25) == "A"
        assert apply_pbo_override("B", 0.10) == "B"
        assert apply_pbo_override("C", 0.29) == "C"
