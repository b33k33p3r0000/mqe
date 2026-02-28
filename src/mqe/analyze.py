"""
MQE Run Analysis — Per-pair and portfolio health checks.
=========================================================
Adapted from QRE analyze.py with portfolio-level extensions.

Per-pair: trade count, Sharpe, Calmar, drawdown, win rate.
Portfolio: pair failure concentration, portfolio Calmar, worst-pair Calmar.
"""

from __future__ import annotations

import logging
from typing import Any

from mqe.config import MIN_TRADES_YEAR_HARD, SHARPE_SUSPECT_THRESHOLD

logger = logging.getLogger("mqe.analyze")


# ─── PER-PAIR ANALYSIS ───────────────────────────────────────────────────────


def _normalize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Normalize MetricsResult dict keys to analysis keys.

    Handles both raw MetricsResult keys (from calculate_metrics)
    and legacy keys (from Stage 1 user_attrs).
    """
    return {
        "trades_per_year": metrics.get("trades_per_year", 0),
        "sharpe": metrics.get(
            "sharpe_ratio_equity_based",
            metrics.get("sharpe_equity", 0),
        ),
        "calmar": metrics.get(
            "calmar_ratio",
            metrics.get("calmar", 0),
        ),
        "max_dd": abs(metrics.get("max_drawdown", metrics.get("max_drawdown_pct", 0))),
        "win_rate": metrics.get("win_rate", 0),
        "sortino": metrics.get("sortino_ratio", 0),
        "profit_factor": metrics.get("profit_factor", 0),
        "total_pnl_pct": metrics.get("total_pnl_pct", 0),
        "trades": metrics.get("trades", 0),
        "expectancy": metrics.get("expectancy", 0),
        "max_win_streak": metrics.get("max_win_streak", 0),
        "max_loss_streak": metrics.get("max_loss_streak", 0),
        "time_in_market": metrics.get("time_in_market", 0),
    }


def analyze_pair(symbol: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """Analyze a single pair's optimization results.

    Checks trade count, Sharpe, Calmar, drawdown, win rate.
    Returns verdict: PASS / WARN / FAIL.

    Args:
        symbol: Pair symbol (e.g. "BTC/USDT").
        metrics: Dict from MetricsResult (calculate_metrics) or legacy format.

    Returns:
        Dict with symbol, verdict, warnings, failures, metrics_summary.
    """
    verdict = "PASS"
    warnings: list[str] = []
    failures: list[str] = []

    norm = _normalize_metrics(metrics)
    trades_per_year = norm["trades_per_year"]
    sharpe = norm["sharpe"]
    calmar = norm["calmar"]
    max_dd = norm["max_dd"]
    win_rate = norm["win_rate"]

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
        "metrics_summary": norm,
    }


# ─── PORTFOLIO ANALYSIS ──────────────────────────────────────────────────────


def analyze_portfolio(
    stage2_result: dict[str, Any],
    per_pair_results: list[dict[str, Any]],
    portfolio_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze portfolio-level optimization results.

    Checks portfolio Calmar, worst-pair Calmar, pair failure concentration.

    Args:
        stage2_result: Stage 2 result dict with objectives and portfolio_params.
        per_pair_results: List of per-pair analysis dicts from analyze_pair().
        portfolio_metrics: Optional full portfolio metrics from final evaluation.

    Returns:
        Dict with verdict, warnings, failures, portfolio_calmar,
        worst_pair_calmar, portfolio_params, portfolio_metrics.
    """
    verdict = "PASS"
    warnings: list[str] = []
    failures: list[str] = []

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

    result = {
        "verdict": verdict,
        "warnings": warnings,
        "failures": failures,
        "portfolio_calmar": portfolio_calmar,
        "worst_pair_calmar": worst_calmar,
        "portfolio_params": params,
    }
    if portfolio_metrics:
        result["portfolio_metrics"] = _normalize_metrics(portfolio_metrics)

    return result


# ─── ORCHESTRATOR ─────────────────────────────────────────────────────────────


def analyze_run(
    pipeline_result: dict[str, Any],
    eval_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full analysis of pipeline run.

    Uses evaluation metrics (full backtest) if available,
    otherwise falls back to Stage 1 trial user_attrs.

    Args:
        pipeline_result: Dict with stage1_results and stage2_results.
        eval_result: Optional evaluation result from run_final_evaluation().

    Returns:
        Dict with per_pair (list of per-pair analyses) and
        portfolio (portfolio analysis).
    """
    stage1 = pipeline_result.get("stage1_results", {})
    stage2 = pipeline_result.get("stage2_results", {})
    eval_metrics = (eval_result or {}).get("per_pair_metrics", {})
    portfolio_metrics = (eval_result or {}).get("portfolio_metrics")

    per_pair: list[dict[str, Any]] = []
    for symbol in stage1:
        # Prefer full evaluation metrics, fall back to Stage 1 data
        if symbol in eval_metrics:
            metrics = eval_metrics[symbol]
        else:
            # Stage 1 result may have metrics nested or flat
            s1 = stage1[symbol]
            metrics = s1.get("metrics", s1) if isinstance(s1, dict) else s1

        pair_analysis = analyze_pair(symbol, metrics)
        per_pair.append(pair_analysis)
        logger.debug(
            "analyze_run: %s verdict=%s", symbol, pair_analysis["verdict"]
        )

    portfolio = analyze_portfolio(stage2, per_pair, portfolio_metrics)
    logger.info("analyze_run: portfolio verdict=%s", portfolio["verdict"])

    return {
        "per_pair": per_pair,
        "portfolio": portfolio,
    }
