"""
MQE Optimization Pipeline
==========================
Orchestrates Stage 1 (per-pair TPE) + Stage 2 (portfolio NSGA-II).

Pipeline flow:
  1. Parse CLI args (symbols, trials, hours, tag)
  2. Fetch data for all symbols (+ BTC for regime)
  3. Run Stage 1 per pair (parallel via ProcessPoolExecutor)
  4. Re-compute signals with best Stage 1 params
  5. Run Stage 2 portfolio optimization
  6. Final evaluation: full backtest + portfolio sim with best params
  7. Analyze + report (console + markdown)
  8. Save results (JSON + CSV)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mqe.analyze import analyze_run
from mqe.config import (
    ANCHORED_WF_SPLITS,
    BASE_TF,
    CLUSTER_DEFINITIONS,
    CORRELATION_GATE_THRESHOLD,
    DEFAULT_TRIALS_STAGE2,
    DISCORD_WEBHOOK_RUNS,
    MIN_WARMUP_BARS,
    STARTING_EQUITY,
    SYMBOLS,
    TIER_MULTIPLIERS,
    TIER_THRESHOLDS,
    TRIALS_LONG,
)
from mqe.core.backtest import simulate_trades_fast
from mqe.core.metrics import MetricsResult, calculate_metrics
from mqe.core.portfolio import PortfolioResult, PortfolioSimulator
from mqe.core.strategy import MultiPairStrategy
from mqe.data.fetch import load_multi_pair_data
from mqe.io import save_json, save_trades_csv
from mqe.notify import notify_complete, notify_start
from mqe.report import print_report, save_markdown_report
from mqe.risk.correlation import compute_pairwise_correlation
from mqe.stage1 import compute_trials, run_stage1_pair
from mqe.stage2 import run_stage2

logger = logging.getLogger("mqe.optimize")

# Strategy param keys -- used to extract best params from Stage 1 flat result dict.
_STRATEGY_PARAM_KEYS = set(MultiPairStrategy().get_default_params().keys())


def fetch_all_data(
    symbols: list[str], hours: int = 8760,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Fetch data for all symbols using ccxt/Binance."""
    import ccxt

    exchange = ccxt.binance({"enableRateLimit": True})
    return load_multi_pair_data(exchange, symbols, hours)


def _extract_strategy_params(stage1_result: dict[str, Any]) -> dict[str, Any]:
    """Extract only strategy params from Stage 1 flat result dict.

    Stage 1 returns a flat dict with both params (macd_fast, rsi_period, etc.)
    and metadata (symbol, objective_value, etc.) mixed together.
    This extracts only the 14 strategy parameters.
    """
    return {k: v for k, v in stage1_result.items() if k in _STRATEGY_PARAM_KEYS}


def _metrics_to_dict(m: MetricsResult) -> dict[str, Any]:
    """Convert MetricsResult dataclass to JSON-safe dict."""
    d = dataclasses.asdict(m)
    # Convert numpy types to Python natives
    for k, v in d.items():
        if isinstance(v, (np.integer,)):
            d[k] = int(v)
        elif isinstance(v, (np.floating,)):
            d[k] = float(v)
        elif isinstance(v, np.ndarray):
            d[k] = v.tolist()
    return d


def assign_tiers(
    per_pair_metrics: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Assign quality tiers based on evaluation Sharpe.

    Args:
        per_pair_metrics: {symbol: {sharpe_ratio_equity_based: float, ...}}

    Returns:
        {symbol: {"tier": "A"/"B"/"C"/"X", "multiplier": float, "sharpe": float}}
    """
    tiers: dict[str, dict[str, Any]] = {}
    for symbol, metrics in per_pair_metrics.items():
        sharpe = metrics.get("sharpe_ratio_equity_based", 0.0)
        if sharpe >= TIER_THRESHOLDS["A"]:
            tier = "A"
        elif sharpe >= TIER_THRESHOLDS["B"]:
            tier = "B"
        elif sharpe >= TIER_THRESHOLDS["C"]:
            tier = "C"
        else:
            tier = "X"
        tiers[symbol] = {
            "tier": tier,
            "multiplier": TIER_MULTIPLIERS[tier],
            "sharpe": sharpe,
        }
    return tiers


def assign_tiers_enhanced(
    wf_metrics: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Assign quality tiers using WF eval metrics (3-signal tiering).

    Signals:
      1. Absolute quality: median OOS Sharpe
      2. Degradation guard: S1/OOS ratio (overfit detection)
      3. Consistency guard: Sharpe std across windows
    """
    from mqe.config import (
        TIER_DEGRADATION_A,
        TIER_DEGRADATION_B,
        TIER_CONSISTENCY_A,
        TIER_WORST_WINDOW_A,
        TIER_WORST_WINDOW_B,
        TIER_WORST_WINDOW_C,
    )
    tiers: dict[str, dict[str, Any]] = {}
    for symbol, wf in wf_metrics.items():
        median_sharpe = wf.get("wf_sharpe_median", 0.0)
        consistency = wf.get("wf_sharpe_std", 0.0)
        degradation = wf.get("degradation_ratio", 0.0)
        worst_sharpe = wf.get("wf_worst_sharpe", 0.0)

        if (
            median_sharpe >= TIER_THRESHOLDS["A"]
            and degradation >= TIER_DEGRADATION_A
            and consistency < TIER_CONSISTENCY_A
            and worst_sharpe >= TIER_WORST_WINDOW_A
        ):
            tier = "A"
        elif (
            median_sharpe >= TIER_THRESHOLDS["B"]
            and degradation >= TIER_DEGRADATION_B
            and worst_sharpe >= TIER_WORST_WINDOW_B
        ):
            tier = "B"
        elif (
            median_sharpe >= TIER_THRESHOLDS["C"]
            and worst_sharpe >= TIER_WORST_WINDOW_C
        ):
            tier = "C"
        else:
            tier = "X"

        tiers[symbol] = {
            "tier": tier,
            "multiplier": TIER_MULTIPLIERS[tier],
            "sharpe": median_sharpe,
            "degradation": degradation,
            "consistency": consistency,
            "worst_sharpe": worst_sharpe,
        }
    return tiers


def run_per_pair_evaluation(
    all_data: dict[str, dict[str, pd.DataFrame]],
    pair_signals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    pair_params: dict[str, dict[str, Any]],
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    """Run per-pair backtests on full data. Used for tier assignment."""
    logger.info("Per-pair evaluation: running full backtests for tier assignment")
    eval_dir = output_dir / "evaluation"
    eval_dir.mkdir(exist_ok=True)
    per_pair_dir = eval_dir / "per_pair_trades"
    per_pair_dir.mkdir(exist_ok=True)

    per_pair_metrics: dict[str, dict[str, Any]] = {}

    for symbol in pair_signals:
        data = all_data[symbol]
        buy, sell, atr, _ = pair_signals[symbol]
        params = pair_params.get(symbol, {})

        result = simulate_trades_fast(
            symbol, data, buy, sell,
            atr_values=atr,
            start_idx=MIN_WARMUP_BARS,
            end_idx=len(data[BASE_TF]),
            allow_flip=bool(params.get("allow_flip", 0)),
            hard_stop_mult=float(params.get("hard_stop_mult", 2.5)),
            trail_mult=float(params.get("trail_mult", 3.0)),
            max_hold_bars=int(params.get("max_hold_bars", 168)),
        )

        metrics = calculate_metrics(
            result.trades, result.backtest_days, start_equity=STARTING_EQUITY,
        )
        per_pair_metrics[symbol] = _metrics_to_dict(metrics)

        safe_name = symbol.replace("/", "_")
        save_trades_csv(per_pair_dir / f"{safe_name}.csv", result.trades)

    save_json(eval_dir / "per_pair_metrics.json", per_pair_metrics)
    return per_pair_metrics


def compute_wf_ceiling(n_bars: int) -> tuple[float, int]:
    """Compute WF eval ceiling and window count based on data length."""
    from mqe.config import (
        ANCHORED_WF_LONG_THRESHOLD_HOURS,
        ANCHORED_WF_SHORT_THRESHOLD_HOURS,
        WF_EVAL_CEILING_LONG,
        WF_EVAL_CEILING_MEDIUM,
        WF_EVAL_CEILING_SHORT,
        WF_EVAL_N_WINDOWS_LONG,
        WF_EVAL_N_WINDOWS_MEDIUM,
        WF_EVAL_N_WINDOWS_SHORT,
    )
    if n_bars >= ANCHORED_WF_LONG_THRESHOLD_HOURS:
        return WF_EVAL_CEILING_LONG, WF_EVAL_N_WINDOWS_LONG
    elif n_bars >= ANCHORED_WF_SHORT_THRESHOLD_HOURS:
        return WF_EVAL_CEILING_MEDIUM, WF_EVAL_N_WINDOWS_MEDIUM
    else:
        return WF_EVAL_CEILING_SHORT, WF_EVAL_N_WINDOWS_SHORT


def run_wf_evaluation(
    all_data: dict[str, dict[str, pd.DataFrame]],
    pair_signals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    pair_params: dict[str, dict[str, Any]],
    s1_sharpes: dict[str, float],
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    """Run walk-forward evaluation on OOS windows for each pair.

    Evaluates S1-optimized params on data AFTER the S1 training ceiling.
    Returns per-pair WF metrics: median Sharpe, std, worst Sharpe, degradation.
    """
    logger.info("WF evaluation: running OOS window backtests for tiering")
    wf_metrics: dict[str, dict[str, Any]] = {}

    for symbol in pair_signals:
        data = all_data[symbol]
        base_df = data[BASE_TF]
        total_bars = len(base_df)
        buy, sell, atr, _ = pair_signals[symbol]
        params = pair_params.get(symbol, {})

        ceiling, n_windows = compute_wf_ceiling(total_bars)
        ceiling_bar = int(total_bars * ceiling)
        remaining = total_bars - ceiling_bar
        window_size = remaining // n_windows if n_windows > 0 else remaining

        window_sharpes: list[float] = []

        for w in range(n_windows):
            w_start = ceiling_bar + w * window_size
            w_end = ceiling_bar + (w + 1) * window_size if w < n_windows - 1 else total_bars

            if w_end - w_start < 100:
                continue

            result = simulate_trades_fast(
                symbol, data, buy, sell,
                atr_values=atr,
                start_idx=w_start,
                end_idx=w_end,
                allow_flip=bool(params.get("allow_flip", 0)),
                hard_stop_mult=float(params.get("hard_stop_mult", 2.5)),
                trail_mult=float(params.get("trail_mult", 3.0)),
                max_hold_bars=int(params.get("max_hold_bars", 168)),
            )

            if not result.trades or len(result.trades) < 3:
                window_sharpes.append(0.0)
                continue

            metrics = calculate_metrics(
                result.trades, result.backtest_days, start_equity=STARTING_EQUITY,
            )
            window_sharpes.append(metrics.sharpe_ratio_equity_based)

        if not window_sharpes:
            window_sharpes = [0.0]

        s1_sharpe = s1_sharpes.get(symbol, 1.0)
        median_sharpe = float(np.median(window_sharpes))
        degradation = median_sharpe / s1_sharpe if s1_sharpe > 0 else 0.0

        wf_metrics[symbol] = {
            "wf_sharpe_median": median_sharpe,
            "wf_sharpe_std": float(np.std(window_sharpes)) if len(window_sharpes) > 1 else 0.0,
            "wf_worst_sharpe": float(min(window_sharpes)),
            "wf_window_sharpes": window_sharpes,
            "degradation_ratio": degradation,
            "s1_sharpe": s1_sharpe,
            "n_windows": len(window_sharpes),
        }
        logger.info(
            "WF eval [%s]: median_sharpe=%.2f, degradation=%.2f, windows=%d",
            symbol, median_sharpe, degradation, len(window_sharpes),
        )

    # Save WF metrics
    eval_dir = output_dir / "evaluation"
    eval_dir.mkdir(exist_ok=True)
    save_json(eval_dir / "wf_eval_metrics.json", wf_metrics)

    return wf_metrics


def run_final_evaluation(
    all_data: dict[str, dict[str, pd.DataFrame]],
    pair_signals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    pair_params: dict[str, dict[str, Any]],
    stage2_result: dict[str, Any],
    output_dir: Path,
    per_pair_metrics: dict[str, dict[str, Any]] | None = None,
    tier_multipliers: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run final evaluation with best params from both stages.

    Runs full per-pair backtests and portfolio sim to produce complete
    trades and metrics for reporting.

    Args:
        per_pair_metrics: Pre-computed per-pair metrics (skips backtest loop).
        tier_multipliers: Tier-based position sizing multipliers per symbol.

    Returns:
        Dict with per_pair_metrics, portfolio_metrics, portfolio_result.
    """
    logger.info("Final evaluation: running full backtests with best params")
    eval_dir = output_dir / "evaluation"
    eval_dir.mkdir(exist_ok=True)

    if per_pair_metrics is None:
        per_pair_metrics = run_per_pair_evaluation(
            all_data, pair_signals, pair_params, output_dir,
        )

    # ── Portfolio sim with best S2 params ──
    s2_params = stage2_result.get("portfolio_params", {})
    cluster_max_val = s2_params.get("cluster_max", 2)

    # Build cluster_max dict from the single optimized value
    cluster_max_dict = {
        cluster: cluster_max_val for cluster in CLUSTER_DEFINITIONS
    }

    # Compute correlation matrix from 1H close prices
    returns_dict = {}
    for symbol in pair_signals:
        close = all_data[symbol][BASE_TF]["close"]
        returns_dict[symbol] = close.pct_change().dropna()
    corr_matrix = compute_pairwise_correlation(returns_dict)

    # Save correlation matrix for HTML report
    symbols_list = list(corr_matrix.keys())
    corr_json = {
        "symbols": symbols_list,
        "matrix": [
            [corr_matrix.get(a, {}).get(b, 1.0 if a == b else 0.0)
             for b in symbols_list]
            for a in symbols_list
        ],
        "corr_gate_threshold": stage2_result.get("portfolio_params", {}).get(
            "corr_gate_threshold", 0.0
        ),
    }
    save_json(eval_dir / "corr_matrix.json", corr_json)

    sim = PortfolioSimulator(
        pair_data=all_data,
        pair_signals=pair_signals,
        pair_params=pair_params,
        max_concurrent=s2_params.get("max_concurrent", 5),
        cluster_max=cluster_max_dict,
        portfolio_heat=s2_params.get("portfolio_heat", 0.05),
        starting_equity=STARTING_EQUITY,
        corr_matrix=corr_matrix,
        corr_gate_threshold=s2_params.get(
            "corr_gate_threshold", CORRELATION_GATE_THRESHOLD
        ),
        tier_multipliers=tier_multipliers,
    )
    portfolio_result = sim.run()

    # Portfolio-level metrics from all trades
    n_bars = len(portfolio_result.equity_curve)
    portfolio_backtest_days = max(1, n_bars // 24)

    portfolio_metrics = calculate_metrics(
        portfolio_result.all_trades, portfolio_backtest_days,
        start_equity=STARTING_EQUITY,
    )
    portfolio_metrics_dict = _metrics_to_dict(portfolio_metrics)
    portfolio_metrics_dict["portfolio_max_drawdown"] = float(portfolio_result.max_drawdown)
    portfolio_metrics_dict["max_positions_open"] = portfolio_result.max_positions_open
    portfolio_metrics_dict["peak_equity"] = float(portfolio_result.peak_equity)

    save_json(eval_dir / "portfolio_metrics.json", portfolio_metrics_dict)
    save_trades_csv(eval_dir / "portfolio_trades.csv", portfolio_result.all_trades)

    total_pair_trades = sum(
        m.get("trades", 0) for m in per_pair_metrics.values()
    )
    logger.info(
        "Final evaluation: %d per-pair trades, %d portfolio trades",
        total_pair_trades, len(portfolio_result.all_trades),
    )

    return {
        "per_pair_metrics": per_pair_metrics,
        "portfolio_metrics": portfolio_metrics_dict,
        "portfolio_result_summary": {
            "equity": float(portfolio_result.equity),
            "max_drawdown": float(portfolio_result.max_drawdown),
            "total_trades": len(portfolio_result.all_trades),
            "max_positions_open": portfolio_result.max_positions_open,
            "peak_equity": float(portfolio_result.peak_equity),
        },
    }


def precompute_all_signals(
    pair_data: dict[str, dict[str, pd.DataFrame]],
    pair_params: dict[str, dict[str, Any]],
    btc_stage1_params: dict[str, Any] | None = None,
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Pre-compute signals for all pairs using Stage 1 best params.

    Args:
        pair_data: Dict of {symbol: {timeframe: DataFrame}} per pair.
        pair_params: Dict of {symbol: {strategy_param: value}} per pair.
        btc_stage1_params: BTC's optimized strategy params for regime filter.

    Returns:
        Dict of {symbol: (buy_signal, sell_signal, atr_values, signal_strength)}.
    """
    strategy = MultiPairStrategy()
    signals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    btc_data = pair_data.get("BTC/USDT")

    for symbol, data in pair_data.items():
        params = pair_params.get(symbol, strategy.get_default_params())
        result = strategy.precompute_signals(
            data,
            params,
            symbol=symbol,
            btc_regime_data=btc_data,
            btc_stage1_params=btc_stage1_params,
        )
        signals[symbol] = result

    return signals


def compute_parallelism(
    n_pairs: int,
    max_workers: int | None = None,
    n_jobs: int | None = None,
) -> tuple[int, int]:
    """Compute optimal (max_workers, n_jobs_per_pair) based on CPU count.

    Strategy:
    - max_workers = number of pair processes running concurrently (queued)
    - n_jobs = number of parallel trial threads within each pair process
    - Total threads = max_workers × n_jobs ≈ cpu_count
    - Each pair gets at least 2 trial threads for meaningful parallelism

    Pairs beyond max_workers wait in ProcessPoolExecutor queue and start
    as soon as a running pair finishes. This means you can always pass
    all pairs and the system handles scheduling automatically.

    Numba @njit releases the GIL, so threading achieves true parallelism
    for the compute-heavy backtest loop (~60% of trial time).
    """
    cpu_count = os.cpu_count() or 4
    usable_cores = max(1, cpu_count - 1)  # leave 1 for OS

    if max_workers is not None and n_jobs is not None:
        return max_workers, n_jobs

    if max_workers is None:
        # Cap concurrent pairs so each gets at least 2 trial threads.
        # Remaining pairs queue and auto-start when a slot opens.
        max_workers = min(n_pairs, max(1, usable_cores // 2))

    if n_jobs is None:
        n_jobs = min(3, max(1, usable_cores // max_workers))

    return max_workers, n_jobs


def run_stage1_all_pairs(
    symbols: list[str],
    all_data: dict[str, dict[str, pd.DataFrame]],
    n_trials: int,
    max_workers: int | None = None,
    output_dir: Path | None = None,
    n_jobs: int | None = None,
    adaptive_trials: bool = True,
) -> dict[str, dict[str, Any]]:
    """Run Stage 1 for all pairs in parallel.

    Args:
        symbols: List of trading pair symbols.
        all_data: Dict of {symbol: {timeframe: DataFrame}}.
        n_trials: Base number of Optuna trials per pair.
        max_workers: Max parallel workers (default: auto from CPU count).
        output_dir: Directory for progress/result files (None = no file output).
        n_jobs: Parallel trial threads per pair (default: auto from CPU count).
        adaptive_trials: Scale trials by data length (default: True).

    Returns:
        Dict of {symbol: stage1_result_dict}.
    """
    max_workers, jobs_per_pair = compute_parallelism(
        len(symbols), max_workers, n_jobs,
    )

    logger.info(
        "Stage 1 parallelism: %d pair workers × %d trial jobs = %d total threads "
        "(CPU cores: %d)",
        max_workers, jobs_per_pair, max_workers * jobs_per_pair,
        os.cpu_count() or 0,
    )

    results: dict[str, dict[str, Any]] = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for symbol in symbols:
            n_bars = len(all_data[symbol][BASE_TF])
            if adaptive_trials:
                pair_trials = compute_trials(n_bars)
            else:
                pair_trials = n_trials
            pair_ceiling, _ = compute_wf_ceiling(n_bars)
            future = executor.submit(
                run_stage1_pair, symbol, all_data[symbol], pair_trials,
                output_dir=output_dir,
                n_jobs=jobs_per_pair,
                ceiling=pair_ceiling,
            )
            futures[future] = symbol
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                results[symbol] = future.result()
                logger.info("Stage 1 complete: %s", symbol)
            except Exception as e:
                logger.error("Stage 1 failed for %s: %s", symbol, e)
                raise

    return results


def run_pipeline(
    symbols: list[str] | None = None,
    stage1_trials: int = TRIALS_LONG,
    stage2_trials: int = DEFAULT_TRIALS_STAGE2,
    hours: int = 26280,
    output_dir: Path | None = None,
    tag: str = "",
    max_workers: int | None = None,
    n_jobs: int | None = None,
) -> dict[str, Any]:
    """Run full MQE optimization pipeline.

    Args:
        symbols: List of trading pairs (default: config.SYMBOLS).
        stage1_trials: Optuna trials per pair for Stage 1.
        stage2_trials: NSGA-II trials for Stage 2.
        hours: How many hours of 1h data to fetch.
        output_dir: Directory to save results (auto-generated if None).
        tag: Optional run tag for identification.
        max_workers: Max parallel workers for Stage 1.
        n_jobs: Parallel trial threads per pair (default: auto from CPU count).

    Returns:
        Dict with stage1_results, stage2_results, and metadata.
    """
    if symbols is None:
        symbols = list(SYMBOLS)
    if output_dir is None:
        output_dir = Path("results") / time.strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "MQE Pipeline: %d symbols, S1=%d trials, S2=%d trials",
        len(symbols), stage1_trials, stage2_trials,
    )

    n_splits = len(ANCHORED_WF_SPLITS)
    notify_start(
        symbols=symbols,
        n_trials_s1=stage1_trials,
        n_trials_s2=stage2_trials,
        n_splits=n_splits,
        run_tag=tag or None,
    )

    # ── 1. Fetch data ──
    all_data = fetch_all_data(symbols, hours)

    # ── 2. Stage 1: per-pair optimization (parallel) ──
    stage1_results = run_stage1_all_pairs(
        symbols, all_data, stage1_trials, max_workers,
        output_dir=output_dir,
        n_jobs=n_jobs,
    )

    # ── 3. Re-compute signals with best Stage 1 params ──
    pair_params = {
        sym: _extract_strategy_params(res)
        for sym, res in stage1_results.items()
    }
    btc_params = pair_params.get("BTC/USDT")
    pair_signals = precompute_all_signals(all_data, pair_params, btc_params)

    # ── 4. Walk-forward evaluation (OOS windows) ──
    s1_sharpes = {
        sym: res.get("sharpe_equity", 0.0)
        for sym, res in stage1_results.items()
    }
    wf_metrics = run_wf_evaluation(
        all_data, pair_signals, pair_params, s1_sharpes, output_dir,
    )

    # ── 5. Enhanced tiering (3-signal: OOS Sharpe + degradation + consistency) ──
    tier_assignments = assign_tiers_enhanced(wf_metrics)
    tier_multipliers = {
        sym: info["multiplier"] for sym, info in tier_assignments.items()
    }
    for sym, info in sorted(
        tier_assignments.items(), key=lambda x: x[1]["sharpe"], reverse=True,
    ):
        logger.info(
            "Tier %s: %s (OOS Sharpe %.2f, degrad %.2f, std %.2f, mult %.2f)",
            info["tier"], sym, info["sharpe"], info["degradation"],
            info["consistency"], info["multiplier"],
        )
    active_count = sum(
        1 for t in tier_assignments.values() if t["tier"] != "X"
    )
    excluded_count = sum(
        1 for t in tier_assignments.values() if t["tier"] == "X"
    )
    logger.info(
        "Tiers: %d active, %d excluded (Tier X)", active_count, excluded_count,
    )

    # ── 6. Per-pair evaluation (full data for reporting) ──
    per_pair_metrics = run_per_pair_evaluation(
        all_data, pair_signals, pair_params, output_dir,
    )

    # ── 6b. Post-eval gate: override tier to X if full-eval Sharpe < 0 ──
    for sym, metrics in per_pair_metrics.items():
        eval_sharpe = metrics.get("sharpe_ratio_equity_based", 0.0)
        if eval_sharpe < 0 and sym in tier_assignments:
            old_tier = tier_assignments[sym]["tier"]
            if old_tier != "X":
                logger.warning(
                    "Post-eval gate: %s demoted %s -> X (eval Sharpe %.2f < 0)",
                    sym, old_tier, eval_sharpe,
                )
                tier_assignments[sym]["tier"] = "X"
                tier_assignments[sym]["multiplier"] = 0.0
                tier_multipliers[sym] = 0.0

    # ── 7. Stage 2: portfolio optimization ──
    stage2_result = run_stage2(
        all_data, pair_signals, pair_params, stage2_trials,
        output_dir=output_dir,
        tier_multipliers=tier_multipliers,
    )
    save_json(output_dir / "stage2_result.json", stage2_result)

    # ── 8. Final evaluation ──
    eval_result = run_final_evaluation(
        all_data, pair_signals, pair_params, stage2_result, output_dir,
        per_pair_metrics=per_pair_metrics,
        tier_multipliers=tier_multipliers,
    )

    # ── 9. Save combined results ──
    combined: dict[str, Any] = {
        "symbols": symbols,
        "stage1_trials": stage1_trials,
        "stage2_trials": stage2_trials,
        "tag": tag,
        "hours": hours,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stage1_results": stage1_results,
        "stage2_results": stage2_result,
        "tier_assignments": tier_assignments,
        "wf_eval_metrics": wf_metrics,
    }
    save_json(output_dir / "pipeline_result.json", combined)

    # ── 10. Analyze + Report ──
    analysis = analyze_run(combined, eval_result)
    print_report(analysis, combined, eval_result)
    save_markdown_report(
        output_dir / "report.md", combined, eval_result, analysis,
    )
    notify_complete(analysis)

    logger.info("Pipeline complete. Results saved to %s", output_dir)
    return combined


def resume_pipeline(
    run_dir: str,
    stage2_trials: int = DEFAULT_TRIALS_STAGE2,
    hours: int | None = None,
    tag: str = "",
    n_jobs: int | None = None,
) -> dict[str, Any]:
    """Resume MQE pipeline from Stage 2 using existing Stage 1 results.

    Loads Stage 1 result JSONs from a previous run directory, fetches fresh
    data, re-computes signals, then runs Stage 2 + evaluation + reporting.

    Args:
        run_dir: Path to existing run directory (e.g. results/20260304_194135).
        stage2_trials: NSGA-II trials for Stage 2.
        hours: Hours of data to fetch (default: from Stage 1 metadata or 26280).
        tag: Optional run tag for identification.
        n_jobs: Parallel trial threads (unused in Stage 2, kept for API parity).

    Returns:
        Dict with stage1_results, stage2_results, and metadata.
    """
    output_dir = Path(run_dir)
    stage1_dir = output_dir / "stage1"

    if not stage1_dir.exists():
        raise FileNotFoundError(f"Stage 1 directory not found: {stage1_dir}")

    # ── 1. Load Stage 1 results ──
    stage1_results: dict[str, dict[str, Any]] = {}
    for path in sorted(stage1_dir.glob("*.json")):
        if "_progress" in path.name:
            continue
        result = json.load(open(path))
        symbol = result["symbol"]
        stage1_results[symbol] = result

    if not stage1_results:
        raise ValueError(f"No Stage 1 result JSONs found in {stage1_dir}")

    symbols = list(stage1_results.keys())
    logger.info(
        "Resume pipeline: loaded %d Stage 1 results from %s",
        len(symbols), stage1_dir,
    )

    # ── 2. Determine hours for data fetch ──
    if hours is None:
        hours = 26280  # default: 3 years
    logger.info("Resume pipeline: fetching %d hours of data for %d symbols", hours, len(symbols))

    # ── 3. Fetch data ──
    all_data = fetch_all_data(symbols, hours)

    # ── 4. Re-compute signals with Stage 1 params ──
    pair_params = {
        sym: _extract_strategy_params(res)
        for sym, res in stage1_results.items()
    }
    btc_params = pair_params.get("BTC/USDT")
    pair_signals = precompute_all_signals(all_data, pair_params, btc_params)

    # ── 5. Walk-forward evaluation (OOS windows) ──
    s1_sharpes = {
        sym: res.get("sharpe_equity", 0.0)
        for sym, res in stage1_results.items()
    }
    wf_metrics = run_wf_evaluation(
        all_data, pair_signals, pair_params, s1_sharpes, output_dir,
    )

    # ── 6. Enhanced tiering (3-signal: OOS Sharpe + degradation + consistency) ──
    tier_assignments = assign_tiers_enhanced(wf_metrics)
    tier_multipliers = {
        sym: info["multiplier"] for sym, info in tier_assignments.items()
    }
    for sym, info in sorted(
        tier_assignments.items(), key=lambda x: x[1]["sharpe"], reverse=True,
    ):
        logger.info(
            "Tier %s: %s (OOS Sharpe %.2f, degrad %.2f, std %.2f, mult %.2f)",
            info["tier"], sym, info["sharpe"], info["degradation"],
            info["consistency"], info["multiplier"],
        )
    active_count = sum(1 for t in tier_assignments.values() if t["tier"] != "X")
    excluded_count = sum(1 for t in tier_assignments.values() if t["tier"] == "X")
    logger.info("Tiers: %d active, %d excluded (Tier X)", active_count, excluded_count)

    # ── 7. Per-pair evaluation (full data for reporting) ──
    per_pair_metrics = run_per_pair_evaluation(
        all_data, pair_signals, pair_params, output_dir,
    )

    # ── 7b. Post-eval gate: override tier to X if full-eval Sharpe < 0 ──
    for sym, metrics in per_pair_metrics.items():
        eval_sharpe = metrics.get("sharpe_ratio_equity_based", 0.0)
        if eval_sharpe < 0 and sym in tier_assignments:
            old_tier = tier_assignments[sym]["tier"]
            if old_tier != "X":
                logger.warning(
                    "Post-eval gate: %s demoted %s -> X (eval Sharpe %.2f < 0)",
                    sym, old_tier, eval_sharpe,
                )
                tier_assignments[sym]["tier"] = "X"
                tier_assignments[sym]["multiplier"] = 0.0
                tier_multipliers[sym] = 0.0

    # ── 8. Stage 2: portfolio optimization ──
    stage2_result = run_stage2(
        all_data, pair_signals, pair_params, stage2_trials,
        output_dir=output_dir,
        tier_multipliers=tier_multipliers,
    )
    save_json(output_dir / "stage2_result.json", stage2_result)

    # ── 9. Final evaluation ──
    eval_result = run_final_evaluation(
        all_data, pair_signals, pair_params, stage2_result, output_dir,
        per_pair_metrics=per_pair_metrics,
        tier_multipliers=tier_multipliers,
    )

    # ── 10. Save combined results ──
    # Reconstruct stage1_trials from loaded results
    stage1_trials_val = max(
        (r.get("n_trials_requested", 0) for r in stage1_results.values()),
        default=0,
    )
    combined: dict[str, Any] = {
        "symbols": symbols,
        "stage1_trials": stage1_trials_val,
        "stage2_trials": stage2_trials,
        "tag": tag,
        "hours": hours,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resumed_from": str(output_dir),
        "stage1_results": stage1_results,
        "stage2_results": stage2_result,
        "tier_assignments": tier_assignments,
        "wf_eval_metrics": wf_metrics,
    }
    save_json(output_dir / "pipeline_result.json", combined)

    # ── 11. Analyze + Report ──
    analysis = analyze_run(combined, eval_result)
    print_report(analysis, combined, eval_result)
    save_markdown_report(
        output_dir / "report.md", combined, eval_result, analysis,
    )
    notify_complete(analysis)

    logger.info("Resume pipeline complete. Results saved to %s", output_dir)
    return combined


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="MQE Optimization Pipeline")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS)
    parser.add_argument("--s1-trials", type=int, default=TRIALS_LONG)
    parser.add_argument("--s2-trials", type=int, default=DEFAULT_TRIALS_STAGE2)
    parser.add_argument("--hours", type=int, default=26280)
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--s1-jobs", type=int, default=None,
        help="Parallel trial threads per pair (default: auto from CPU count)",
    )
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument(
        "--resume", type=str, default=None, metavar="PATH",
        help="Resume from Stage 2 using existing run directory (e.g. results/20260304_194135)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    if args.resume:
        # Resume mode: skip Stage 1, run Stage 2+ from existing results
        resume_hours = args.hours if args.hours != 8760 else None
        resume_pipeline(
            run_dir=args.resume,
            stage2_trials=args.s2_trials,
            hours=resume_hours,
            tag=args.tag,
            n_jobs=args.s1_jobs,
        )
    else:
        output_dir = Path(args.output) if args.output else None
        run_pipeline(
            symbols=args.symbols,
            stage1_trials=args.s1_trials,
            stage2_trials=args.s2_trials,
            hours=args.hours,
            output_dir=output_dir,
            tag=args.tag,
            max_workers=args.workers,
            n_jobs=args.s1_jobs,
        )


if __name__ == "__main__":
    main()
