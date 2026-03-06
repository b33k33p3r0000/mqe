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
    DEFAULT_TRIALS_STAGE1,
    DEFAULT_TRIALS_STAGE2,
    DISCORD_WEBHOOK_RUNS,
    MIN_WARMUP_BARS,
    STARTING_EQUITY,
    SYMBOLS,
    TIER_MULTIPLIERS,
    TIER_THRESHOLDS,
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
            if adaptive_trials:
                n_bars = len(all_data[symbol][BASE_TF])
                pair_trials = compute_trials(n_bars, n_trials)
            else:
                pair_trials = n_trials
            future = executor.submit(
                run_stage1_pair, symbol, all_data[symbol], pair_trials,
                output_dir=output_dir,
                n_jobs=jobs_per_pair,
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
    stage1_trials: int = DEFAULT_TRIALS_STAGE1,
    stage2_trials: int = DEFAULT_TRIALS_STAGE2,
    hours: int = 8760,
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

    # ── 4. Per-pair evaluation for tier assignment ──
    per_pair_metrics = run_per_pair_evaluation(
        all_data, pair_signals, pair_params, output_dir,
    )
    tier_assignments = assign_tiers(per_pair_metrics)
    tier_multipliers = {
        sym: info["multiplier"] for sym, info in tier_assignments.items()
    }

    for sym, info in sorted(
        tier_assignments.items(), key=lambda x: x[1]["sharpe"], reverse=True,
    ):
        logger.info(
            "Tier %s: %s (Sharpe %.2f, mult %.2f)",
            info["tier"], sym, info["sharpe"], info["multiplier"],
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

    # ── 5. Stage 2: portfolio optimization ──
    stage2_result = run_stage2(
        all_data, pair_signals, pair_params, stage2_trials,
        tier_multipliers=tier_multipliers,
    )
    save_json(output_dir / "stage2_result.json", stage2_result)

    # ── 6. Final evaluation ──
    eval_result = run_final_evaluation(
        all_data, pair_signals, pair_params, stage2_result, output_dir,
        per_pair_metrics=per_pair_metrics,
        tier_multipliers=tier_multipliers,
    )

    # ── 7. Save combined results ──
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
    }
    save_json(output_dir / "pipeline_result.json", combined)

    # ── 8. Analyze + Report ──
    analysis = analyze_run(combined, eval_result)
    print_report(analysis, combined, eval_result)
    save_markdown_report(
        output_dir / "report.md", combined, eval_result, analysis,
    )
    notify_complete(analysis)

    logger.info("Pipeline complete. Results saved to %s", output_dir)
    return combined


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="MQE Optimization Pipeline")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS)
    parser.add_argument("--s1-trials", type=int, default=DEFAULT_TRIALS_STAGE1)
    parser.add_argument("--s2-trials", type=int, default=DEFAULT_TRIALS_STAGE2)
    parser.add_argument("--hours", type=int, default=8760)
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--s1-jobs", type=int, default=None,
        help="Parallel trial threads per pair (default: auto from CPU count)",
    )
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

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
