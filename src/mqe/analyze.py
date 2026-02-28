"""
MQE Run Analysis — Per-pair and portfolio health checks.
=========================================================
Adapted from QRE analyze.py with portfolio-level extensions.

Per-pair: trade count, Sharpe, Calmar, drawdown, win rate.
Portfolio: pair failure concentration, portfolio Calmar, worst-pair Calmar.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from mqe.config import MIN_TRADES_YEAR_HARD, SHARPE_SUSPECT_THRESHOLD

logger = logging.getLogger("mqe.analyze")


# ─── PER-PAIR ANALYSIS ───────────────────────────────────────────────────────


def analyze_pair(symbol: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single pair's optimization results.

    Checks trade count, Sharpe, Calmar, drawdown, win rate.
    Returns verdict: PASS / WARN / FAIL.

    Args:
        symbol: Pair symbol (e.g. "BTC/USDT").
        metrics: Dict with keys: trades_per_year, sharpe_equity, calmar,
            max_drawdown_pct, win_rate.

    Returns:
        Dict with symbol, verdict, warnings, failures, metrics_summary.
    """
    verdict = "PASS"
    warnings: List[str] = []
    failures: List[str] = []

    trades_per_year = metrics.get("trades_per_year", 0)
    sharpe = metrics.get("sharpe_equity", 0)
    calmar = metrics.get("calmar", 0)
    max_dd = metrics.get("max_drawdown_pct", 0)
    win_rate = metrics.get("win_rate", 0)

    # --- Trade count check ---
    if trades_per_year < MIN_TRADES_YEAR_HARD:
        failures.append(
            f"Too few trades: {trades_per_year:.0f}/yr (min {MIN_TRADES_YEAR_HARD})"
        )
        verdict = "FAIL"

    # --- Sharpe check ---
    if sharpe < 0.5:
        failures.append(f"Sharpe too low: {sharpe:.2f}")
        verdict = "FAIL"
    elif sharpe > SHARPE_SUSPECT_THRESHOLD:
        warnings.append(f"Sharpe suspiciously high: {sharpe:.2f}")

    # --- Calmar check ---
    if calmar < 0.5:
        warnings.append(f"Calmar low: {calmar:.2f}")
        if verdict != "FAIL":
            verdict = "WARN"

    # --- Drawdown check ---
    if max_dd > 15:
        warnings.append(f"High drawdown: {max_dd:.1f}%")
        if verdict != "FAIL":
            verdict = "WARN"

    return {
        "symbol": symbol,
        "verdict": verdict,
        "warnings": warnings,
        "failures": failures,
        "metrics_summary": {
            "trades_per_year": trades_per_year,
            "sharpe": sharpe,
            "calmar": calmar,
            "max_dd": max_dd,
            "win_rate": win_rate,
        },
    }


# ─── PORTFOLIO ANALYSIS ──────────────────────────────────────────────────────


def analyze_portfolio(
    stage2_result: Dict[str, Any],
    per_pair_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze portfolio-level optimization results.

    Checks portfolio Calmar, worst-pair Calmar, pair failure concentration.

    Args:
        stage2_result: Stage 2 result dict with objectives and portfolio_params.
        per_pair_results: List of per-pair analysis dicts from analyze_pair().

    Returns:
        Dict with verdict, warnings, failures, portfolio_calmar,
        worst_pair_calmar, portfolio_params.
    """
    verdict = "PASS"
    warnings: List[str] = []
    failures: List[str] = []

    objectives = stage2_result.get("objectives", {})
    portfolio_calmar = objectives.get("portfolio_calmar", 0)
    worst_calmar = objectives.get("worst_pair_calmar", 0)
    params = stage2_result.get("portfolio_params", {})

    # --- Portfolio Calmar check ---
    if portfolio_calmar < 0.5:
        failures.append(f"Portfolio Calmar too low: {portfolio_calmar:.2f}")
        verdict = "FAIL"

    # --- Worst-pair Calmar check ---
    if worst_calmar < 0.2:
        warnings.append(f"Worst pair Calmar low: {worst_calmar:.2f}")
        if verdict != "FAIL":
            verdict = "WARN"

    # --- Pair failure concentration ---
    if per_pair_results:
        failed_pairs = [r for r in per_pair_results if r["verdict"] == "FAIL"]
        if len(failed_pairs) > len(per_pair_results) // 2:
            failures.append(
                f"More than half of pairs failed "
                f"({len(failed_pairs)}/{len(per_pair_results)})"
            )
            verdict = "FAIL"

    return {
        "verdict": verdict,
        "warnings": warnings,
        "failures": failures,
        "portfolio_calmar": portfolio_calmar,
        "worst_pair_calmar": worst_calmar,
        "portfolio_params": params,
    }


# ─── ORCHESTRATOR ─────────────────────────────────────────────────────────────


def analyze_run(pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
    """Full analysis of pipeline run.

    Runs per-pair analysis on each Stage 1 result, then portfolio analysis
    on Stage 2 result.

    Args:
        pipeline_result: Dict with stage1_results (per-pair) and
            stage2_results (portfolio).

    Returns:
        Dict with per_pair (list of per-pair analyses) and
        portfolio (portfolio analysis).
    """
    stage1 = pipeline_result.get("stage1_results", {})
    stage2 = pipeline_result.get("stage2_results", {})

    per_pair: List[Dict[str, Any]] = []
    for symbol, result in stage1.items():
        metrics = result.get("metrics", {})
        pair_analysis = analyze_pair(symbol, metrics)
        per_pair.append(pair_analysis)
        logger.debug(
            "analyze_run: %s verdict=%s", symbol, pair_analysis["verdict"]
        )

    portfolio = analyze_portfolio(stage2, per_pair)
    logger.info("analyze_run: portfolio verdict=%s", portfolio["verdict"])

    return {
        "per_pair": per_pair,
        "portfolio": portfolio,
    }
