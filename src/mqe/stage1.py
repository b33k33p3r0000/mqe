"""
MQE Stage 1 — Per-pair Optuna TPE Optimizer
=============================================
Anchored Walk-Forward optimization per pair using Optuna TPE.

Adapted from QRE's optimize.py for MQE's MultiPairStrategy (14 params).
Key differences from QRE:
  - 14 Optuna params (vs 10): adds adx_threshold, trail_mult, hard_stop_mult, max_hold_bars
  - Passes ATR array to simulate_trades_fast
  - Passes exit params (hard_stop_mult, trail_mult, max_hold_bars) to backtest
  - No catastrophic_stop_pct — replaced by ATR-based hard stop
  - Returns 4-tuple from strategy: (buy, sell, atr, signal_strength)

Usage:
    result = run_stage1_pair("BTC/USDT", data, n_trials=10000)
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import optuna
import pandas as pd

from mqe.config import (
    ANCHORED_WF_MIN_DATA_HOURS,
    ANCHORED_WF_SHORT_THRESHOLD_HOURS,
    ANCHORED_WF_SPLITS,
    ANCHORED_WF_SPLITS_SHORT,
    BASE_TF,
    DEFAULT_TRIALS_STAGE1,
    ENABLE_PRUNING,
    MIN_DRAWDOWN_FLOOR,
    MIN_STARTUP_TRIALS,
    MIN_TRADES_TEST_HARD,
    MIN_TRADES_YEAR_HARD,
    MIN_WARMUP_BARS,
    PURGE_GAP_BARS,
    SHARPE_DECAY_RATE,
    SHARPE_SUSPECT_THRESHOLD,
    STARTING_EQUITY,
    STARTUP_TRIALS_RATIO,
    TARGET_TRADES_YEAR,
    TPE_CONSIDER_ENDPOINTS,
    TPE_N_EI_CANDIDATES,
)
from mqe.core.backtest import simulate_trades_fast
from mqe.core.indicators import rsi as compute_rsi
from mqe.core.metrics import calculate_metrics
from mqe.core.strategy import MultiPairStrategy

logger = logging.getLogger("mqe.stage1")


# ─── AWF SPLITS ─────────────────────────────────────────────────────────────


def compute_awf_splits(
    total_hours: int,
    n_splits: Optional[int] = None,
    test_size: float = 0.20,
) -> Optional[List[Dict[str, float]]]:
    """Compute Anchored Walk-Forward splits based on data length.

    Returns None if data is too short.
    """
    if total_hours < ANCHORED_WF_MIN_DATA_HOURS:
        return None

    purge_frac = PURGE_GAP_BARS / total_hours  # gap as fraction of total data

    if n_splits is not None and n_splits >= 2:
        splits: List[Dict[str, float]] = []
        train_start = 0.50
        available = 1.0 - train_start - test_size - purge_frac
        train_step = available / n_splits
        for i in range(n_splits):
            train_end = train_start + (i + 1) * train_step
            test_start = train_end + purge_frac
            test_end = min(test_start + test_size, 1.0)
            splits.append({
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
            })
        return splits

    # Static splits -- add purge gap
    base_splits = (
        ANCHORED_WF_SPLITS_SHORT
        if total_hours < ANCHORED_WF_SHORT_THRESHOLD_HOURS
        else ANCHORED_WF_SPLITS
    )
    return [
        {
            "train_end": s["train_end"],
            "test_start": s["train_end"] + purge_frac,
            "test_end": s["test_end"],
        }
        for s in base_splits
    ]


# ─── OPTUNA SAMPLER & PRUNER ────────────────────────────────────────────────


def create_sampler(seed: int, n_trials: int) -> optuna.samplers.BaseSampler:
    """Create TPE sampler for Optuna study."""
    n_startup = max(MIN_STARTUP_TRIALS, int(n_trials * STARTUP_TRIALS_RATIO))
    return optuna.samplers.TPESampler(
        seed=seed,
        n_startup_trials=n_startup,
        n_ei_candidates=TPE_N_EI_CANDIDATES,
        consider_endpoints=TPE_CONSIDER_ENDPOINTS,
    )


def create_pruner(n_trials: int) -> optuna.pruners.BasePruner:
    """Create SuccessiveHalving pruner."""
    if not ENABLE_PRUNING:
        return optuna.pruners.NopPruner()
    return optuna.pruners.SuccessiveHalvingPruner(
        min_resource=1,
        reduction_factor=3,
        min_early_stopping_rate=0,
    )


# ─── OBJECTIVE FUNCTION ─────────────────────────────────────────────────────


def compute_objective_score(
    raw_calmar: float,
    sharpe: float,
    trades_per_year: float,
) -> float:
    """Compute Log Calmar objective score with trade ramp and Sharpe decay.

    This is the core scoring function used by the Optuna objective.
    Identical to QRE's proven objective.

    Args:
        raw_calmar: Raw Calmar ratio (annual_return / max_dd), floored and clamped >= 0.
        sharpe: Equity-based Sharpe ratio (clamped >= 0).
        trades_per_year: Number of trades per year.

    Returns:
        Objective score (higher is better).
    """
    # Log dampening -- compress extreme Calmar values
    log_calmar = math.log(1.0 + raw_calmar)

    # Trade count ramp -- penalize low frequency
    trade_mult = min(1.0, max(0.0, trades_per_year / TARGET_TRADES_YEAR))

    # Smooth Sharpe decay -- penalize suspiciously high Sharpe
    if sharpe > SHARPE_SUSPECT_THRESHOLD:
        penalty = 1.0 / (1.0 + SHARPE_DECAY_RATE * (sharpe - SHARPE_SUSPECT_THRESHOLD))
        log_calmar *= penalty

    return log_calmar * trade_mult


# ─── BUILD OBJECTIVE ────────────────────────────────────────────────────────


def build_objective(
    symbol: str,
    data: Dict[str, pd.DataFrame],
    splits: List[Dict[str, float]],
    allow_flip_setting: int = 0,
) -> Callable:
    """Build Optuna objective function for AWF optimization.

    Returns log(1+Calmar) with trade count ramp and smooth Sharpe decay penalty.
    Hard constraints: MIN_TRADES_YEAR_HARD on train, MIN_TRADES_TEST_HARD on test.

    Key MQE differences from QRE:
    - Uses MultiPairStrategy (14 params, not 10)
    - Extracts exit params from trial and passes to simulate_trades_fast
    - Passes ATR array to backtest
    - No catastrophic_stop_pct
    """
    strategy = MultiPairStrategy()
    base_df = data[BASE_TF]
    total_bars = len(base_df)

    # Pre-compute RSI for all possible Optuna periods (3-30)
    precomputed_cache: Dict[str, Any] = {"rsi": {}}
    for period in range(3, 31):
        precomputed_cache["rsi"][period] = compute_rsi(
            base_df["close"], period
        ).values.astype(np.float64)

    def objective(trial: optuna.trial.Trial) -> float:
        params = strategy.get_optuna_params(
            trial, symbol, allow_flip_override=allow_flip_setting,
        )

        # Compute signals (4-tuple: buy, sell, atr, signal_strength)
        buy_signal, sell_signal, atr_values, _ = strategy.precompute_signals(
            data, params, precomputed_cache=precomputed_cache, symbol=symbol,
        )

        allow_flip = bool(params.get("allow_flip", 0))

        # Extract exit params from trial
        hard_stop_mult = float(params.get("hard_stop_mult", 2.5))
        trail_mult = float(params.get("trail_mult", 3.0))
        max_hold_bars = int(params.get("max_hold_bars", 168))

        split_scores: List[float] = []
        _sharpes: List[float] = []
        _drawdowns: List[float] = []
        _pnls: List[float] = []
        _trade_counts: List[int] = []
        _tpy: List[float] = []

        for split in splits:
            train_end = int(total_bars * split["train_end"])
            test_start = int(total_bars * split.get("test_start", split["train_end"]))
            test_end = int(total_bars * split["test_end"])

            # TRAIN -- only for hard constraint check
            train_result = simulate_trades_fast(
                symbol, data, buy_signal, sell_signal,
                atr_values=atr_values,
                start_idx=MIN_WARMUP_BARS, end_idx=train_end,
                allow_flip=allow_flip,
                hard_stop_mult=hard_stop_mult,
                trail_mult=trail_mult,
                max_hold_bars=max_hold_bars,
            )
            if not train_result.trades:
                split_scores.append(0.0)
                continue

            train_metrics = calculate_metrics(
                train_result.trades, train_result.backtest_days,
                start_equity=STARTING_EQUITY,
            )

            # Hard constraint: minimum trades per year (on train)
            if train_metrics.trades_per_year < MIN_TRADES_YEAR_HARD:
                split_scores.append(0.0)
                continue

            # TEST -- this is what we optimize (start after purge gap)
            test_result = simulate_trades_fast(
                symbol, data, buy_signal, sell_signal,
                atr_values=atr_values,
                start_idx=test_start, end_idx=test_end,
                allow_flip=allow_flip,
                hard_stop_mult=hard_stop_mult,
                trail_mult=trail_mult,
                max_hold_bars=max_hold_bars,
            )

            # Hard constraint: minimum test trades
            if not test_result.trades or len(test_result.trades) < MIN_TRADES_TEST_HARD:
                split_scores.append(0.0)
                continue

            test_metrics = calculate_metrics(
                test_result.trades, test_result.backtest_days,
                start_equity=STARTING_EQUITY,
            )

            # Score = Log Calmar with trade ramp and Sharpe decay
            annual_return = test_metrics.total_pnl_pct / (test_result.backtest_days / 365.25)
            max_dd = abs(test_metrics.max_drawdown / 100.0)  # convert % to fraction
            raw_calmar = annual_return / max(max_dd, MIN_DRAWDOWN_FLOOR)
            raw_calmar = max(0.0, raw_calmar)

            trades_per_year = len(test_result.trades) / (test_result.backtest_days / 365.25)
            sharpe = max(0.0, test_metrics.sharpe_ratio_equity_based)

            score = compute_objective_score(raw_calmar, sharpe, trades_per_year)

            _sharpes.append(test_metrics.sharpe_ratio_equity_based)
            _drawdowns.append(test_metrics.max_drawdown)
            _pnls.append(test_metrics.total_pnl_pct)
            _trade_counts.append(len(test_result.trades))
            _tpy.append(trades_per_year)

            split_scores.append(score)

        if not split_scores or all(s == 0 for s in split_scores):
            return 0.0

        # Store extended metrics for live monitor
        if _sharpes:
            trial.set_user_attr("sharpe_equity", round(float(np.mean(_sharpes)), 4))
            trial.set_user_attr("max_drawdown", round(float(np.mean(_drawdowns)), 2))
            trial.set_user_attr("total_pnl_pct", round(float(np.mean(_pnls)), 2))
            trial.set_user_attr("trades", int(np.mean(_trade_counts)))
            trial.set_user_attr("trades_per_year", round(float(np.mean(_tpy)), 2))

        return float(np.mean(split_scores))

    return objective


# ─── RUN STAGE 1 PER PAIR ───────────────────────────────────────────────────


def run_stage1_pair(
    symbol: str,
    data: Dict[str, pd.DataFrame],
    n_trials: int = DEFAULT_TRIALS_STAGE1,
    n_splits: Optional[int] = None,
    seed: int = 42,
    timeout: int = 0,
    test_size: float = 0.20,
    allow_flip: int = 0,
) -> Dict[str, Any]:
    """Run Stage 1 optimization for a single pair.

    This is the per-pair optimizer. Each pair is optimized independently
    with Optuna TPE using AWF splits (same methodology as QRE).

    Args:
        symbol: Trading pair (e.g. "BTC/USDT").
        data: Dict with at least "1h" key; also "4h"/"8h"/"1d" for trend filter.
        n_trials: Number of Optuna trials.
        n_splits: Custom number of AWF splits (None = auto from data length).
        seed: Random seed.
        timeout: Optuna timeout in seconds (0 = no timeout).
        test_size: Test window fraction (default 0.20).
        allow_flip: Fixed allow_flip value (0=selective, 1=always-in).

    Returns:
        Dict with best_params (all 14 strategy params) + optimization metadata.
    """
    base_df = data[BASE_TF]
    total_bars = len(base_df)

    # Compute AWF splits
    splits = compute_awf_splits(total_bars, n_splits, test_size=test_size)
    if splits is None:
        raise ValueError(
            f"Data too short for AWF: {total_bars} bars < {ANCHORED_WF_MIN_DATA_HOURS}"
        )

    logger.info(
        "Stage 1 [%s]: AWF %d splits, %d bars, %d trials",
        symbol, len(splits), total_bars, n_trials,
    )
    for i, s in enumerate(splits):
        te = int(total_bars * s["train_end"])
        ts = int(total_bars * s.get("test_start", s["train_end"]))
        tse = int(total_bars * s["test_end"])
        logger.info("  Split %d: Train 0-%d, Purge %d-%d, Test %d-%d", i + 1, te, te, ts, ts, tse)

    # Create Optuna study
    sampler = create_sampler(seed, n_trials)
    pruner = create_pruner(n_trials)

    study_name = f"mqe_s1_{symbol.replace('/', '_')}_{seed}"
    study = optuna.create_study(
        study_name=study_name,
        direction="maximize",
        sampler=sampler,
        pruner=pruner,
    )
    study.set_user_attr("symbol", symbol)
    study.set_user_attr("n_trials_requested", n_trials)
    study.set_user_attr("stage", 1)

    # Build objective and run
    objective = build_objective(symbol, data, splits, allow_flip_setting=allow_flip)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout if timeout > 0 else None,
        n_jobs=1,
        show_progress_bar=False,
    )

    # Collect results
    completed_trials = len([
        t for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE
    ])
    if completed_trials == 0:
        raise RuntimeError(
            f"No completed trials for {symbol}. Check data quality and constraints."
        )

    best_params = dict(study.best_trial.params)
    best_value = study.best_value

    if best_value == 0.0:
        logger.warning(
            "All trials scored 0.0 for %s -- degenerate result", symbol,
        )

    # Build result dict
    result: Dict[str, Any] = {}
    result.update(best_params)
    result.update({
        "symbol": symbol,
        "objective_value": best_value,
        "objective_type": "log_calmar",
        "n_trials_completed": completed_trials,
        "n_trials_requested": n_trials,
        "n_splits": len(splits),
        "seed": seed,
        "strategy": "multi_pair_funnel",
        "strategy_version": MultiPairStrategy.version,
    })

    # Add trial user attrs if available
    best_trial = study.best_trial
    for key in ["sharpe_equity", "max_drawdown", "total_pnl_pct", "trades", "trades_per_year"]:
        if key in best_trial.user_attrs:
            result[key] = best_trial.user_attrs[key]

    logger.info(
        "Stage 1 [%s]: Done. Objective=%.4f, %d/%d trials completed",
        symbol, best_value, completed_trials, n_trials,
    )

    return result
