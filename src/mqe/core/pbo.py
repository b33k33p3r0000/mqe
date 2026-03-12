"""
PBO — Probability of Backtest Overfitting
==========================================
CSCV (Combinatorially Symmetric Cross-Validation) implementation.

Splits data into S subsets, generates C(S, S/2) train/test combinations,
tests rank stability of best-in-sample strategy across all combinations.

PBO < 0.30 → probably real edge
PBO > 0.50 → probably trading noise
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from mqe.config import (
    BASE_TF,
    MIN_WARMUP_BARS,
    PAIR_PROFILES,
    PBO_DEMOTE_THRESHOLD,
    PBO_N_PARAM_SETS,
    PBO_N_SUBSETS,
    PBO_TIER_X_THRESHOLD,
    STARTING_EQUITY,
    TIER_SEARCH_SPACE,
)
from mqe.core.backtest import simulate_trades_fast
from mqe.core.metrics import calculate_metrics
from mqe.core.strategy import MultiPairStrategy
from mqe.stage1 import compute_objective_score

logger = logging.getLogger("mqe.pbo")


@dataclass
class PBOResult:
    pbo_score: float
    n_combinations: int
    n_param_sets: int
    rank_distribution: List[int]
    logit_pbo: float


def generate_cscv_combinations(n_subsets: int = 8) -> List[Tuple[tuple, tuple]]:
    """Generate all C(n, n/2) CSCV train/test splits."""
    indices = list(range(n_subsets))
    half = n_subsets // 2
    result = []
    for train in combinations(indices, half):
        test = tuple(i for i in indices if i not in train)
        result.append((train, test))
    return result


def generate_random_params(
    symbol: str,
    n_sets: int = PBO_N_PARAM_SETS,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Generate independent random param sets from TIER_SEARCH_SPACE."""
    tier = PAIR_PROFILES.get(symbol, {}).get("tier", "B")
    space = TIER_SEARCH_SPACE.get(tier, TIER_SEARCH_SPACE["B"])
    rng = np.random.default_rng(seed)
    params_list: List[Dict[str, Any]] = []

    for _ in range(n_sets):
        p: Dict[str, Any] = {}
        for key, (lo, hi) in space.items():
            if key == "trend_tf":
                continue  # categorical, handled separately
            if key in ("allow_flip", "trend_strict"):
                p[key] = lo  # fixed
            elif isinstance(lo, float):
                p[key] = rng.uniform(lo, hi)
            else:
                p[key] = int(rng.integers(lo, hi + 1))
        # trend_tf random choice
        p["trend_tf"] = rng.choice(["4h", "8h", "1d"])
        # Enforce macd_slow > macd_fast + 5
        if p.get("macd_slow", 26) - p.get("macd_fast", 12) < 5:
            p["macd_slow"] = int(p.get("macd_fast", 12)) + 5
        params_list.append(p)

    return params_list


def compute_pbo_score(
    oos_ranks: np.ndarray,
    median_rank: int,
) -> float:
    """Compute PBO from OOS rank distribution.

    PBO = fraction of combinations where best-in-sample ranked at or below median OOS.
    """
    below_median = np.sum(oos_ranks >= median_rank)
    return float(below_median / len(oos_ranks))


def run_pbo_for_pair(
    symbol: str,
    data: Dict[str, pd.DataFrame],
    best_params: Dict[str, Any],
    n_param_sets: int = PBO_N_PARAM_SETS,
    n_subsets: int = PBO_N_SUBSETS,
    garch_vol_ratio: Optional[np.ndarray] = None,
    seed: int = 42,
) -> PBOResult:
    """Run full PBO evaluation for one pair.

    1. Split data into n_subsets
    2. Generate random params + add best_params
    3. For each CSCV combination: backtest all, rank, record best-in-train OOS rank
    4. Compute PBO score
    """
    base_df = data[BASE_TF]
    n_bars = len(base_df)
    subset_size = n_bars // n_subsets

    # Generate param sets: K random + 1 best
    random_params = generate_random_params(symbol, n_param_sets, seed=seed)
    all_params = random_params + [best_params]
    n_total = len(all_params)

    strategy = MultiPairStrategy()
    combos = generate_cscv_combinations(n_subsets)

    oos_ranks: List[int] = []

    for combo_idx, (train_idx, test_idx) in enumerate(combos):
        train_scores: List[float] = []
        test_scores: List[float] = []

        for params in all_params:
            # Precompute signals for this param set
            buy, sell, atr_vals, _ = strategy.precompute_signals(data, params, symbol=symbol)

            # Train: backtest on train subset bars
            train_start = min(train_idx) * subset_size
            train_end = (max(train_idx) + 1) * subset_size
            train_score = _backtest_score(
                symbol, data, buy, sell, atr_vals, params,
                max(train_start, MIN_WARMUP_BARS), min(train_end, n_bars),
                garch_vol_ratio=garch_vol_ratio,
            )
            train_scores.append(train_score)

            # Test: backtest on test subset bars
            test_start = min(test_idx) * subset_size
            test_end = (max(test_idx) + 1) * subset_size
            test_score = _backtest_score(
                symbol, data, buy, sell, atr_vals, params,
                max(test_start, MIN_WARMUP_BARS), min(test_end, n_bars),
                garch_vol_ratio=garch_vol_ratio,
            )
            test_scores.append(test_score)

        # Rank by train score (descending), find best-in-train
        train_ranking = np.argsort(train_scores)[::-1]
        best_in_train_idx = train_ranking[0]

        # Rank by test score (descending), find rank of best-in-train
        test_ranking = np.argsort(test_scores)[::-1]
        oos_rank = int(np.where(test_ranking == best_in_train_idx)[0][0]) + 1
        oos_ranks.append(oos_rank)

        if (combo_idx + 1) % 10 == 0:
            logger.debug("PBO [%s]: %d/%d combos done", symbol, combo_idx + 1, len(combos))

    median_rank = n_total // 2
    pbo = compute_pbo_score(np.array(oos_ranks), median_rank)

    # Logit PBO (clipped to avoid inf)
    pbo_clipped = np.clip(pbo, 1e-6, 1 - 1e-6)
    logit = float(math.log(pbo_clipped / (1 - pbo_clipped)))

    logger.info("PBO [%s]: score=%.3f, logit=%.2f (%d combos)", symbol, pbo, logit, len(combos))

    return PBOResult(
        pbo_score=pbo,
        n_combinations=len(combos),
        n_param_sets=n_total,
        rank_distribution=oos_ranks,
        logit_pbo=logit,
    )


def _backtest_score(
    symbol: str,
    data: Dict[str, pd.DataFrame],
    buy: np.ndarray,
    sell: np.ndarray,
    atr_vals: np.ndarray,
    params: Dict[str, Any],
    start_idx: int,
    end_idx: int,
    garch_vol_ratio: Optional[np.ndarray] = None,
) -> float:
    """Backtest on a bar range and return Log Calmar score."""
    if end_idx <= start_idx:
        return 0.0

    result = simulate_trades_fast(
        symbol, data, buy, sell,
        atr_values=atr_vals,
        start_idx=start_idx,
        end_idx=end_idx,
        allow_flip=bool(params.get("allow_flip", 0)),
        hard_stop_mult=float(params.get("hard_stop_mult", 2.5)),
        trail_mult=float(params.get("trail_mult", 3.0)),
        max_hold_bars=int(params.get("max_hold_bars", 168)),
        vol_ratio=garch_vol_ratio,
        vol_sensitivity=float(params.get("vol_sensitivity", 1.0)),
    )

    if not result.trades or result.backtest_days < 1:
        return 0.0

    metrics = calculate_metrics(result.trades, result.backtest_days, start_equity=STARTING_EQUITY)
    annual_return = metrics.total_pnl_pct / (result.backtest_days / 365.25)
    max_dd = abs(metrics.max_drawdown / 100.0)
    raw_calmar = max(0.0, annual_return / max(max_dd, 0.05))
    sharpe = max(0.0, metrics.sharpe_ratio_equity_based)
    return compute_objective_score(raw_calmar, sharpe, 0.0)


def apply_pbo_override(tier: str, pbo_score: float) -> str:
    """Apply PBO tier override. Operates on evaluation tiers (A/B/C/X)."""
    if pbo_score > PBO_TIER_X_THRESHOLD:
        return "X"
    if pbo_score > PBO_DEMOTE_THRESHOLD:
        demotion = {"A": "B", "B": "C", "C": "X", "X": "X"}
        return demotion.get(tier, "X")
    return tier
