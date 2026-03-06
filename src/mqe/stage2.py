"""
MQE Stage 2 — Portfolio-level NSGA-II multi-objective optimization.

Optimizes global portfolio params using PortfolioSimulator.
Runs AFTER Stage 1 per-pair optimization is complete.

3 objectives (all maximized by negating minimization targets):
  1. Portfolio Calmar ratio (maximize)
  2. Worst-pair Calmar ratio (maximize) — robustness guard
  3. Negative overfit penalty (maximize = minimize overfit)

Global params optimized:
  - max_concurrent: max simultaneous open positions
  - cluster_max: max positions per cluster (default for all)
  - portfolio_heat: DD threshold for emergency close
  - corr_gate_threshold: correlation gate threshold
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import optuna
import pandas as pd

from mqe.config import (
    BASE_TF,
    CLUSTER_DEFINITIONS,
    DEFAULT_TRIALS_STAGE2,
    MIN_DRAWDOWN_FLOOR,
    STARTING_EQUITY,
)
from mqe.risk.correlation import compute_pairwise_correlation
from mqe.core.portfolio import PortfolioSimulator

logger = logging.getLogger("mqe.stage2")


# ─── OBJECTIVE BUILDER ─────────────────────────────────────────────────────


def build_portfolio_objective(
    pair_data: dict[str, dict[str, pd.DataFrame]],
    pair_signals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    pair_params: dict[str, dict[str, Any]],
    tier_multipliers: dict[str, float] | None = None,
) -> Callable:
    """Build multi-objective function for Stage 2.

    Returns callable(trial) -> (portfolio_calmar, worst_pair_calmar, neg_overfit_penalty)

    Args:
        pair_data: Dict of {symbol: {timeframe: DataFrame}} per pair.
        pair_signals: Dict of {symbol: (buy, sell, atr, signal_strength)} per pair.
        pair_params: Dict of {symbol: {param_name: value}} per pair (from Stage 1).
    """
    n_pairs = len(pair_data)

    # Compute correlation matrix once (outside objective loop)
    returns_dict = {}
    for symbol in pair_data:
        if BASE_TF in pair_data[symbol]:
            close = pair_data[symbol][BASE_TF]["close"]
            returns_dict[symbol] = close.pct_change().dropna()
    corr_matrix = compute_pairwise_correlation(returns_dict) if returns_dict else {}

    def objective(trial: optuna.trial.Trial) -> tuple[float, float, float]:
        # ── Portfolio-level params ──
        max_concurrent = trial.suggest_int(
            "max_concurrent", min(3, n_pairs), min(n_pairs, 10)
        )
        cluster_max = trial.suggest_int("cluster_max", 1, 3)
        portfolio_heat = trial.suggest_float("portfolio_heat", 0.03, 0.10)
        corr_gate_threshold = trial.suggest_float("corr_gate_threshold", 0.60, 0.90)

        # Build cluster_max dict from the single optimized value
        cluster_max_dict = {
            cluster: cluster_max for cluster in CLUSTER_DEFINITIONS
        }

        # Run portfolio simulation
        sim = PortfolioSimulator(
            pair_data=pair_data,
            pair_signals=pair_signals,
            pair_params=pair_params,
            max_concurrent=max_concurrent,
            cluster_max=cluster_max_dict,
            portfolio_heat=portfolio_heat,
            starting_equity=STARTING_EQUITY,
            corr_matrix=corr_matrix,
            corr_gate_threshold=corr_gate_threshold,
            tier_multipliers=tier_multipliers,
        )
        result = sim.run()

        # ── Objective 1: Portfolio Calmar ──
        n_bars = len(result.equity_curve)
        years = n_bars / (24.0 * 365.25) if n_bars > 0 else 1.0

        total_return = (result.equity / STARTING_EQUITY) - 1.0
        annual_return = total_return / years if years > 0 else 0.0

        dd = max(result.max_drawdown, MIN_DRAWDOWN_FLOOR)
        portfolio_calmar = annual_return / dd if dd > 0 else 0.0

        # ── Objective 2: Worst-pair Calmar (robustness guard) ──
        worst_calmar = float("inf")
        has_pair_with_trades = False

        for sym, trades in result.per_pair_trades.items():
            if len(trades) < 2:
                continue
            has_pair_with_trades = True

            # Compute per-pair return and drawdown from trades
            pair_equity = STARTING_EQUITY / n_pairs  # proportional allocation
            pair_pnl = sum(t.get("pnl_abs", 0.0) for t in trades)
            pair_return = pair_pnl / pair_equity if pair_equity > 0 else 0.0
            pair_annual_return = pair_return / years if years > 0 else 0.0

            # Per-pair drawdown from equity curve of that pair's trades
            equity_vals = [pair_equity]
            for t in trades:
                equity_vals.append(equity_vals[-1] + t.get("pnl_abs", 0.0))
            equity_arr = np.array(equity_vals)
            peak = np.maximum.accumulate(equity_arr)
            dd_arr = (peak - equity_arr) / np.where(peak > 0, peak, 1.0)
            pair_max_dd = float(np.max(dd_arr))
            pair_max_dd = max(pair_max_dd, MIN_DRAWDOWN_FLOOR)

            pair_calmar = pair_annual_return / pair_max_dd if pair_max_dd > 0 else 0.0
            worst_calmar = min(worst_calmar, pair_calmar)

        if not has_pair_with_trades:
            worst_calmar = 0.0

        # ── Objective 3: Overfit penalty (minimize -> negate) ──
        overfit_penalty = 0.0

        # Penalize extreme parameter values that suggest overfitting
        if max_concurrent <= 1:
            overfit_penalty += 0.5  # too restrictive — may overfit to single best pair
        if portfolio_heat < 0.035:
            overfit_penalty += 0.3  # too tight heat — may overfit to low-vol regime
        if corr_gate_threshold < 0.65:
            overfit_penalty += 0.2  # too loose gate — no real filtering

        # Penalize if no trades produced (degenerate config)
        if len(result.all_trades) == 0:
            overfit_penalty += 1.0

        return portfolio_calmar, worst_calmar, -overfit_penalty

    return objective


# ─── PROGRESS CALLBACK ─────────────────────────────────────────────────────


class Stage2ProgressCallback:
    """Optuna callback that writes Stage 2 progress JSON every N trials.

    Writes to: {output_dir}/stage2_progress.json
    Atomic write via tmp file + os.replace to prevent partial reads.
    """

    def __init__(
        self,
        output_dir: Path,
        n_trials_total: int,
        interval: int = 50,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.n_trials_total = n_trials_total
        self.interval = interval
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def __call__(
        self,
        study: optuna.study.Study,
        trial: optuna.trial.FrozenTrial,
    ) -> None:
        if (trial.number + 1) % self.interval != 0:
            return

        # Pareto front stats
        best_trials = study.best_trials
        pareto_size = len(best_trials)

        best_portfolio_calmar = 0.0
        best_worst_pair_calmar = 0.0
        if best_trials:
            top = max(best_trials, key=lambda t: t.values[0])
            best_portfolio_calmar = top.values[0]
            best_worst_pair_calmar = top.values[1]

        progress = {
            "trials_completed": trial.number + 1,
            "trials_total": self.n_trials_total,
            "best_portfolio_calmar": round(best_portfolio_calmar, 6),
            "best_worst_pair_calmar": round(best_worst_pair_calmar, 6),
            "pareto_front_size": pareto_size,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        progress_path = self.output_dir / "stage2_progress.json"
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.output_dir), suffix=".tmp",
            )
            with os.fdopen(fd, "w") as f:
                json.dump(progress, f, indent=2)
            os.replace(tmp_path, str(progress_path))
        except OSError:
            logger.debug("Failed to write Stage 2 progress")


# ─── RUN STAGE 2 ───────────────────────────────────────────────────────────


def run_stage2(
    pair_data: dict[str, dict[str, pd.DataFrame]],
    pair_signals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    pair_params: dict[str, dict[str, Any]],
    n_trials: int = DEFAULT_TRIALS_STAGE2,
    seed: int = 42,
    output_dir: Path | None = None,
    tier_multipliers: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run Stage 2 portfolio optimization with NSGA-II.

    Args:
        pair_data: Dict of {symbol: {timeframe: DataFrame}} per pair.
        pair_signals: Dict of {symbol: (buy, sell, atr, signal_strength)} per pair.
        pair_params: Dict of {symbol: {param_name: value}} per pair (from Stage 1).
        n_trials: Number of NSGA-II trials.
        seed: Random seed for reproducibility.
        output_dir: Directory for progress files (None = no file output).
        tier_multipliers: Tier-based position sizing multipliers per symbol.

    Returns:
        Dict with portfolio_params, objectives, n_trials, pareto_front_size.
    """
    logger.info(
        "Stage 2: %d pairs, %d trials, NSGA-II",
        len(pair_data), n_trials,
    )

    objective = build_portfolio_objective(
        pair_data, pair_signals, pair_params,
        tier_multipliers=tier_multipliers,
    )

    sampler = optuna.samplers.NSGAIISampler(
        population_size=min(50, n_trials),
        seed=seed,
    )

    study = optuna.create_study(
        directions=["maximize", "maximize", "maximize"],
        sampler=sampler,
    )

    callbacks: list[Any] = []
    if output_dir is not None:
        callbacks.append(
            Stage2ProgressCallback(output_dir, n_trials, interval=50)
        )

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(
        objective, n_trials=n_trials, show_progress_bar=False,
        callbacks=callbacks,
    )

    # Select best from Pareto front
    best_trials = study.best_trials
    if not best_trials:
        logger.warning("Stage 2: No Pareto-optimal trials found")
        return {
            "portfolio_params": {},
            "objectives": {
                "portfolio_calmar": 0.0,
                "worst_pair_calmar": 0.0,
                "neg_overfit_penalty": 0.0,
            },
            "n_trials": n_trials,
            "pareto_front_size": 0,
        }

    # Pick trial with best portfolio Calmar (objective 0) from Pareto front
    best = max(best_trials, key=lambda t: t.values[0])

    logger.info(
        "Stage 2: Done. Pareto front=%d, best portfolio_calmar=%.4f",
        len(best_trials), best.values[0],
    )

    return {
        "portfolio_params": dict(best.params),
        "objectives": {
            "portfolio_calmar": best.values[0],
            "worst_pair_calmar": best.values[1],
            "neg_overfit_penalty": best.values[2],
        },
        "n_trials": n_trials,
        "pareto_front_size": len(best_trials),
    }
