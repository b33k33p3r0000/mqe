"""agent/critic.py — Deterministic sanity checks for MQE optimization run results.

Quick mode: 6 lightweight checks that run in <1s from JSON/CSV artifacts.
Full mode: reserved for future LLM-assisted deep analysis.

Usage:
    from critic import quick, full
    results = quick(run_dir)
"""
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Constants ─────────────────────────────────────────────────────────

_MIN_DD_FLOOR = 0.05          # DD floor used in optimizer objective
_DD_FLOOR_TOL = 0.001         # Tolerance for DD-floor proximity detection
_WF_DEGRADE_FAIL = 0.33       # OOS/S1 ratio below this = FAIL (strong overfit)
_WF_DEGRADE_WARN = 0.70       # Below this = WARNING
_EQUITY_MISMATCH_FAIL = 0.05  # >5% per-pair sum vs total_pnl = FAIL
_EQUITY_MISMATCH_WARN = 0.02  # >2% = WARNING
_TRADE_CONC_FAIL = 0.60       # Single quarter > 60% of total PnL = FAIL
_TRADE_CONC_WARN = 0.50       # > 50% = WARNING
_HARD_STOP_FAIL = 0.30        # > 30% hard_stop exits = FAIL
_HARD_STOP_WARN = 0.20        # > 20% = WARNING


# ── Internal helpers ──────────────────────────────────────────────────

def _read_json(path: Path) -> Dict[str, Any]:
    """Read and parse a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_result(
    name: str,
    status: str,
    message: str,
    value: Optional[float] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a standardized check result dict."""
    result: Dict[str, Any] = {
        "check": name,
        "status": status,
        "message": message,
    }
    if value is not None:
        result["value"] = value
    if threshold is not None:
        result["threshold"] = threshold
    return result


# ── Data loading ──────────────────────────────────────────────────────

def load_run_data(run_dir: Path) -> Dict[str, Any]:
    """Load pipeline.json from a run directory.

    Args:
        run_dir: Path to the run directory (e.g. results/20260307_120000/).

    Returns:
        Parsed pipeline.json as a dict.

    Raises:
        FileNotFoundError: If evaluation/pipeline.json does not exist.
    """
    pipeline_path = run_dir / "evaluation" / "pipeline.json"
    if not pipeline_path.exists():
        raise FileNotFoundError(f"pipeline.json not found at {pipeline_path}")
    return _read_json(pipeline_path)


def load_trades(run_dir: Path) -> List[Dict[str, str]]:
    """Load trades.csv from a run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        List of dicts, one per trade row (all values as strings).

    Raises:
        FileNotFoundError: If evaluation/trades.csv does not exist.
    """
    trades_path = run_dir / "evaluation" / "trades.csv"
    if not trades_path.exists():
        raise FileNotFoundError(f"trades.csv not found at {trades_path}")
    with open(trades_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ── Check functions ───────────────────────────────────────────────────

def check_wf_degradation(run_data: Dict[str, Any]) -> Dict[str, Any]:
    """Check walk-forward degradation ratios across all pairs.

    Flags pairs where OOS/S1 degradation_ratio is below thresholds,
    indicating the strategy may have overfit to training data.

    Args:
        run_data: Parsed pipeline.json dict.

    Returns:
        Check result dict with status PASS / WARNING / FAIL.
    """
    wf_metrics = run_data.get("wf_eval_metrics", {})
    if not wf_metrics:
        return _check_result(
            "wf_degradation", "WARNING",
            "No wf_eval_metrics found in pipeline data",
        )

    fail_pairs = []
    warn_pairs = []
    min_ratio = 1.0

    for symbol, metrics in wf_metrics.items():
        ratio = metrics.get("degradation_ratio", 1.0)
        if ratio < min_ratio:
            min_ratio = ratio
        if ratio < _WF_DEGRADE_FAIL:
            fail_pairs.append(f"{symbol}={ratio:.2f}")
        elif ratio < _WF_DEGRADE_WARN:
            warn_pairs.append(f"{symbol}={ratio:.2f}")

    if fail_pairs:
        return _check_result(
            "wf_degradation", "FAIL",
            f"Strong overfit signal — degradation_ratio < {_WF_DEGRADE_FAIL} "
            f"for: {', '.join(fail_pairs)}",
            value=min_ratio,
            threshold=_WF_DEGRADE_FAIL,
        )
    if warn_pairs:
        return _check_result(
            "wf_degradation", "WARNING",
            f"Elevated WF degradation for: {', '.join(warn_pairs)}",
            value=min_ratio,
            threshold=_WF_DEGRADE_WARN,
        )
    return _check_result(
        "wf_degradation", "PASS",
        "Walk-forward degradation ratios within acceptable range",
        value=min_ratio,
        threshold=_WF_DEGRADE_WARN,
    )


def check_dd_floor_gaming(run_data: Dict[str, Any]) -> Dict[str, Any]:
    """Check if any pair's max_drawdown is suspiciously close to the DD floor (5%).

    The optimizer has a 5% DD floor in the objective function. If a pair's
    drawdown is exactly at 5.000%, Optuna may have gamed the floor.

    Args:
        run_data: Parsed pipeline.json dict.

    Returns:
        Check result dict with status PASS / FAIL.
    """
    per_pair = run_data.get("per_pair_results", {})
    if not per_pair:
        return _check_result(
            "dd_floor_gaming", "WARNING",
            "No per_pair_results found in pipeline data",
        )

    gamed_pairs = []
    for symbol, metrics in per_pair.items():
        dd = metrics.get("max_drawdown", 0.0)
        if abs(dd - _MIN_DD_FLOOR) < _DD_FLOOR_TOL:
            gamed_pairs.append(f"{symbol}={dd:.4f}")

    if gamed_pairs:
        return _check_result(
            "dd_floor_gaming", "FAIL",
            f"DD floor gaming detected — max_drawdown within {_DD_FLOOR_TOL} "
            f"of floor ({_MIN_DD_FLOOR}) for: {', '.join(gamed_pairs)}",
            value=_MIN_DD_FLOOR,
            threshold=_DD_FLOOR_TOL,
        )
    return _check_result(
        "dd_floor_gaming", "PASS",
        "No DD floor gaming detected",
    )


def check_equity_reconstruction(run_data: Dict[str, Any]) -> Dict[str, Any]:
    """Check if sum of per-pair PnL matches the reported total_pnl.

    A significant mismatch indicates a data pipeline bug (double-counting,
    missing pairs, or incorrect aggregation).

    Args:
        run_data: Parsed pipeline.json dict.

    Returns:
        Check result dict with status PASS / WARNING / FAIL.
    """
    total_pnl = run_data.get("total_pnl")
    per_pair = run_data.get("per_pair_results", {})

    if total_pnl is None:
        return _check_result(
            "equity_reconstruction", "WARNING",
            "total_pnl not found in pipeline data",
        )
    if not per_pair:
        return _check_result(
            "equity_reconstruction", "WARNING",
            "No per_pair_results found in pipeline data",
        )

    pair_sum = sum(m.get("total_pnl", 0.0) for m in per_pair.values())

    if abs(total_pnl) < 1e-9:
        return _check_result(
            "equity_reconstruction", "WARNING",
            "total_pnl is near-zero — cannot compute relative mismatch",
            value=pair_sum,
        )

    mismatch = abs(pair_sum - total_pnl) / abs(total_pnl)

    if mismatch > _EQUITY_MISMATCH_FAIL:
        return _check_result(
            "equity_reconstruction", "FAIL",
            f"Per-pair PnL sum ({pair_sum:.0f}) vs total_pnl ({total_pnl:.0f}) "
            f"mismatch = {mismatch:.1%} (>{_EQUITY_MISMATCH_FAIL:.0%})",
            value=mismatch,
            threshold=_EQUITY_MISMATCH_FAIL,
        )
    if mismatch > _EQUITY_MISMATCH_WARN:
        return _check_result(
            "equity_reconstruction", "WARNING",
            f"Minor PnL mismatch = {mismatch:.1%} (>{_EQUITY_MISMATCH_WARN:.0%})",
            value=mismatch,
            threshold=_EQUITY_MISMATCH_WARN,
        )
    return _check_result(
        "equity_reconstruction", "PASS",
        f"Per-pair PnL sum matches total_pnl within {_EQUITY_MISMATCH_WARN:.0%}",
        value=mismatch,
        threshold=_EQUITY_MISMATCH_FAIL,
    )


def check_trade_distribution(trades: List[Dict[str, str]]) -> Dict[str, Any]:
    """Check if PnL is concentrated in a single calendar quarter.

    Highly concentrated PnL (>60% in one quarter) suggests the strategy
    profited from a single market regime rather than robust signal generation.

    Args:
        trades: List of trade dicts from load_trades().

    Returns:
        Check result dict with status PASS / WARNING / FAIL.
    """
    if not trades:
        return _check_result(
            "trade_distribution", "WARNING",
            "No trades found — cannot check distribution",
        )

    quarter_pnl: Dict[str, float] = {}
    for trade in trades:
        entry_ts = trade.get("entry_ts", "")
        pnl_str = trade.get("pnl_usd", "0")
        try:
            pnl = float(pnl_str)
        except (ValueError, TypeError):
            pnl = 0.0

        # Parse quarter from ISO timestamp (YYYY-MM-DD...)
        if len(entry_ts) >= 7:
            month_str = entry_ts[5:7]
            year_str = entry_ts[:4]
            try:
                month = int(month_str)
                quarter = (month - 1) // 3 + 1
                key = f"{year_str}-Q{quarter}"
            except ValueError:
                key = "unknown"
        else:
            key = "unknown"

        quarter_pnl[key] = quarter_pnl.get(key, 0.0) + pnl

    total_pnl = sum(quarter_pnl.values())
    if abs(total_pnl) < 1e-9:
        return _check_result(
            "trade_distribution", "WARNING",
            "Total trade PnL near zero — cannot compute concentration",
        )

    # Only check concentration for positive total_pnl
    if total_pnl <= 0:
        return _check_result(
            "trade_distribution", "WARNING",
            f"Total trade PnL is negative ({total_pnl:.0f}) — skipping concentration check",
            value=total_pnl,
        )

    max_quarter = max(quarter_pnl, key=lambda k: quarter_pnl[k])
    max_pnl = quarter_pnl[max_quarter]

    # Only flag if the max quarter itself is positive (avoids false positives)
    if max_pnl <= 0:
        return _check_result(
            "trade_distribution", "PASS",
            "No single quarter dominates PnL positively",
        )

    concentration = max_pnl / total_pnl

    if concentration > _TRADE_CONC_FAIL:
        return _check_result(
            "trade_distribution", "FAIL",
            f"{max_quarter} accounts for {concentration:.1%} of total PnL "
            f"(>{_TRADE_CONC_FAIL:.0%} threshold)",
            value=concentration,
            threshold=_TRADE_CONC_FAIL,
        )
    if concentration > _TRADE_CONC_WARN:
        return _check_result(
            "trade_distribution", "WARNING",
            f"{max_quarter} accounts for {concentration:.1%} of total PnL "
            f"(>{_TRADE_CONC_WARN:.0%} threshold)",
            value=concentration,
            threshold=_TRADE_CONC_WARN,
        )
    return _check_result(
        "trade_distribution", "PASS",
        f"PnL well distributed — max quarter {max_quarter} = {concentration:.1%}",
        value=concentration,
        threshold=_TRADE_CONC_FAIL,
    )


def check_hard_stop_ratio(trades: List[Dict[str, str]]) -> Dict[str, Any]:
    """Check ratio of hard_stop exits across all trades.

    High hard_stop ratio indicates the strategy hits catastrophic stop-losses
    frequently, suggesting overly aggressive position sizing or poor signal quality.

    Args:
        trades: List of trade dicts from load_trades().

    Returns:
        Check result dict with status PASS / WARNING / FAIL.
    """
    if not trades:
        return _check_result(
            "hard_stop_ratio", "WARNING",
            "No trades found — cannot check hard stop ratio",
        )

    total = len(trades)
    hard_stops = sum(1 for t in trades if t.get("reason") == "hard_stop")
    ratio = hard_stops / total

    if ratio > _HARD_STOP_FAIL:
        return _check_result(
            "hard_stop_ratio", "FAIL",
            f"{hard_stops}/{total} exits ({ratio:.1%}) via hard_stop "
            f"(>{_HARD_STOP_FAIL:.0%} threshold)",
            value=ratio,
            threshold=_HARD_STOP_FAIL,
        )
    if ratio > _HARD_STOP_WARN:
        return _check_result(
            "hard_stop_ratio", "WARNING",
            f"{hard_stops}/{total} exits ({ratio:.1%}) via hard_stop "
            f"(>{_HARD_STOP_WARN:.0%} threshold)",
            value=ratio,
            threshold=_HARD_STOP_WARN,
        )
    return _check_result(
        "hard_stop_ratio", "PASS",
        f"Hard stop ratio {ratio:.1%} within acceptable range",
        value=ratio,
        threshold=_HARD_STOP_FAIL,
    )


def check_score_regression(
    run_data: Dict[str, Any],
    current_score: Optional[float] = None,
    prev_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Check if resilience score regressed compared to a previous run.

    When both current_score and prev_score are provided explicitly and
    current_score <= prev_score, the check is skipped (caller context).

    Args:
        run_data: Parsed pipeline.json dict from current run.
        current_score: Override current resilience score (optional).
        prev_score: Previous run's resilience score for comparison (optional).

    Returns:
        Check result dict with status PASS / WARNING / FAIL / SKIP.
    """
    # If both explicit scores provided and current <= prev, skip
    if current_score is not None and prev_score is not None:
        if current_score <= prev_score:
            return _check_result(
                "score_regression", "SKIP",
                f"Score regression noted ({current_score:.1f} <= {prev_score:.1f}) "
                "— skipping per caller context",
                value=current_score,
                threshold=prev_score,
            )

    # Use explicit score or fall back to run_data
    score = current_score if current_score is not None else run_data.get("resilience_score")

    if score is None:
        return _check_result(
            "score_regression", "WARNING",
            "resilience_score not found in pipeline data",
        )

    # If no prev_score reference, can't compare — just report current
    if prev_score is None:
        return _check_result(
            "score_regression", "PASS",
            f"Current resilience score: {score:.1f} (no previous run to compare)",
            value=score,
        )

    delta = score - prev_score
    if delta < -5.0:
        return _check_result(
            "score_regression", "FAIL",
            f"Score regressed {delta:+.1f} ({prev_score:.1f} → {score:.1f})",
            value=score,
            threshold=prev_score,
        )
    if delta < 0:
        return _check_result(
            "score_regression", "WARNING",
            f"Minor score decrease {delta:+.1f} ({prev_score:.1f} → {score:.1f})",
            value=score,
            threshold=prev_score,
        )
    return _check_result(
        "score_regression", "PASS",
        f"Score improved or stable {delta:+.1f} ({prev_score:.1f} → {score:.1f})",
        value=score,
        threshold=prev_score,
    )


# ── Orchestrators ─────────────────────────────────────────────────────

def quick(
    run_dir: Path,
    prev_run_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Run all quick-mode deterministic checks on a run directory.

    Loads pipeline.json and trades.csv, then executes all 6 checks.
    Runs in <1s from local artifacts — no network, no LLM.

    Args:
        run_dir: Path to the current run directory.
        prev_run_dir: Optional path to a previous run for score regression check.

    Returns:
        List of check result dicts, one per check.
    """
    run_data = load_run_data(run_dir)
    trades = load_trades(run_dir)

    prev_score: Optional[float] = None
    if prev_run_dir is not None:
        try:
            prev_data = load_run_data(prev_run_dir)
            prev_score = prev_data.get("resilience_score")
        except FileNotFoundError:
            pass

    results = [
        check_wf_degradation(run_data),
        check_dd_floor_gaming(run_data),
        check_equity_reconstruction(run_data),
        check_trade_distribution(trades),
        check_hard_stop_ratio(trades),
        check_score_regression(run_data, prev_score=prev_score),
    ]
    return results


def full(
    run_dir: Path,
    prev_run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Full mode — reserved for future LLM-assisted deep analysis.

    Currently returns quick() results plus a placeholder for LLM context.

    Args:
        run_dir: Path to the current run directory.
        prev_run_dir: Optional path to previous run.

    Returns:
        Dict with 'quick_checks' and 'llm_context' (placeholder).
    """
    quick_results = quick(run_dir, prev_run_dir=prev_run_dir)
    return {
        "quick_checks": quick_results,
        "llm_context": None,  # Reserved for Task 5
    }
