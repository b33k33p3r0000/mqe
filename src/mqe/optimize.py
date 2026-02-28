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
  6. Save results (JSON + CSV)
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from mqe.config import (
    DEFAULT_TRIALS_STAGE1,
    DEFAULT_TRIALS_STAGE2,
    DISCORD_WEBHOOK_RUNS,
    STARTING_EQUITY,
    SYMBOLS,
)
from mqe.core.strategy import MultiPairStrategy
from mqe.data.fetch import load_multi_pair_data
from mqe.io import save_json
from mqe.stage1 import run_stage1_pair
from mqe.stage2 import run_stage2

logger = logging.getLogger("mqe.optimize")

# Strategy param keys -- used to extract best params from Stage 1 flat result dict.
_STRATEGY_PARAM_KEYS = set(MultiPairStrategy().get_default_params().keys())


def fetch_all_data(
    symbols: List[str], hours: int = 8760,
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Fetch data for all symbols using ccxt/Binance."""
    import ccxt

    exchange = ccxt.binance({"enableRateLimit": True})
    return load_multi_pair_data(exchange, symbols, hours)


def _extract_strategy_params(stage1_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only strategy params from Stage 1 flat result dict.

    Stage 1 returns a flat dict with both params (macd_fast, rsi_period, etc.)
    and metadata (symbol, objective_value, etc.) mixed together.
    This extracts only the 14 strategy parameters.
    """
    return {k: v for k, v in stage1_result.items() if k in _STRATEGY_PARAM_KEYS}


def precompute_all_signals(
    pair_data: Dict[str, Dict[str, pd.DataFrame]],
    pair_params: Dict[str, Dict[str, Any]],
    btc_stage1_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Pre-compute signals for all pairs using Stage 1 best params.

    Args:
        pair_data: Dict of {symbol: {timeframe: DataFrame}} per pair.
        pair_params: Dict of {symbol: {strategy_param: value}} per pair.
        btc_stage1_params: BTC's optimized strategy params for regime filter.

    Returns:
        Dict of {symbol: (buy_signal, sell_signal, atr_values, signal_strength)}.
    """
    strategy = MultiPairStrategy()
    signals: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
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


def run_stage1_all_pairs(
    symbols: List[str],
    all_data: Dict[str, Dict[str, pd.DataFrame]],
    n_trials: int,
    max_workers: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """Run Stage 1 for all pairs in parallel.

    Args:
        symbols: List of trading pair symbols.
        all_data: Dict of {symbol: {timeframe: DataFrame}}.
        n_trials: Number of Optuna trials per pair.
        max_workers: Max parallel workers (default: min(n_pairs, cpu_count-1)).

    Returns:
        Dict of {symbol: stage1_result_dict}.
    """
    if max_workers is None:
        max_workers = min(len(symbols), max(1, (os.cpu_count() or 4) - 1))

    results: Dict[str, Dict[str, Any]] = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_stage1_pair, symbol, all_data[symbol], n_trials): symbol
            for symbol in symbols
        }
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
    symbols: Optional[List[str]] = None,
    stage1_trials: int = DEFAULT_TRIALS_STAGE1,
    stage2_trials: int = DEFAULT_TRIALS_STAGE2,
    hours: int = 8760,
    output_dir: Optional[Path] = None,
    tag: str = "",
    max_workers: Optional[int] = None,
) -> Dict[str, Any]:
    """Run full MQE optimization pipeline.

    Args:
        symbols: List of trading pairs (default: config.SYMBOLS).
        stage1_trials: Optuna trials per pair for Stage 1.
        stage2_trials: NSGA-II trials for Stage 2.
        hours: How many hours of 1h data to fetch.
        output_dir: Directory to save results (auto-generated if None).
        tag: Optional run tag for identification.
        max_workers: Max parallel workers for Stage 1.

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

    # ── 1. Fetch data ──
    all_data = fetch_all_data(symbols, hours)

    # ── 2. Stage 1: per-pair optimization (parallel) ──
    stage1_results = run_stage1_all_pairs(
        symbols, all_data, stage1_trials, max_workers,
    )

    # Save Stage 1 results
    s1_dir = output_dir / "stage1"
    s1_dir.mkdir(exist_ok=True)
    for sym, result in stage1_results.items():
        safe_name = sym.replace("/", "_")
        save_json(s1_dir / f"{safe_name}.json", result)

    # ── 3. Re-compute signals with best Stage 1 params ──
    pair_params = {
        sym: _extract_strategy_params(res)
        for sym, res in stage1_results.items()
    }
    btc_params = pair_params.get("BTC/USDT")
    pair_signals = precompute_all_signals(all_data, pair_params, btc_params)

    # ── 4. Stage 2: portfolio optimization ──
    stage2_result = run_stage2(
        all_data, pair_signals, pair_params, stage2_trials,
    )
    save_json(output_dir / "stage2_result.json", stage2_result)

    # ── 5. Save combined results ──
    combined: Dict[str, Any] = {
        "symbols": symbols,
        "stage1_trials": stage1_trials,
        "stage2_trials": stage2_trials,
        "tag": tag,
        "stage1_results": stage1_results,
        "stage2_results": stage2_result,
    }
    save_json(output_dir / "pipeline_result.json", combined)

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
    )


if __name__ == "__main__":
    main()
