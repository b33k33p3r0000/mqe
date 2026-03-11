"""agent/critic.py — Deterministic sanity checks for MQE optimization run results.

Quick mode: 6 lightweight checks that run in <1s from JSON/CSV artifacts.
Full mode: reserved for future LLM-assisted deep analysis.

Usage:
    from critic import quick, full
    results = quick(run_dir)
"""
import csv
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Constants ─────────────────────────────────────────────────────────

_MIN_DD_FLOOR = 0.05          # DD floor used in optimizer objective
_DD_FLOOR_TOL = 0.001         # Tolerance for DD-floor proximity detection
_WF_DEGRADE_FAIL = 0.33       # OOS/S1 ratio below this = FAIL (strong overfit)
_WF_DEGRADE_WARN = 0.70       # Below this = WARNING
_EQUITY_MISMATCH_FAIL = 0.05  # >5% trades sum vs total_pnl = FAIL
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
    detail: str,
    value: Optional[float] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a standardized check result dict."""
    result: Dict[str, Any] = {
        "name": name,
        "status": status,
        "detail": detail,
    }
    if value is not None:
        result["value"] = value
    if threshold is not None:
        result["threshold"] = threshold
    return result


def _extract_metrics(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract key metrics from a loaded run data dict for LLM context."""
    if data is None:
        return None
    portfolio = data.get("portfolio", {})
    return {
        "total_pnl": portfolio.get("total_pnl"),
        "portfolio_max_drawdown": portfolio.get("portfolio_max_drawdown"),
        "sortino_ratio": portfolio.get("sortino_ratio"),
        "calmar_ratio": portfolio.get("calmar_ratio"),
        "sharpe_ratio_equity_based": portfolio.get("sharpe_ratio_equity_based"),
        "trades": portfolio.get("trades"),
        "win_rate": portfolio.get("win_rate"),
    }


def _format_history_summary(history: List[Dict[str, Any]]) -> str:
    """Format history list as a brief text summary."""
    if not history:
        return "No previous history."
    lines = []
    for i, entry in enumerate(history[-5:], 1):
        lines.append(f"  {i}. {json.dumps(entry)}")
    return "\n".join(lines)


# ── Data loading ──────────────────────────────────────────────────────

def load_run_data(run_dir: Path) -> Dict[str, Any]:
    """Load pipeline_result.json and portfolio_metrics.json from a run directory.

    Args:
        run_dir: Path to the run directory (e.g. results/20260307_120000/).

    Returns:
        Dict with keys: pipeline, portfolio, wf_eval_metrics, tier_assignments.

    Raises:
        FileNotFoundError: If pipeline_result.json does not exist.
    """
    run_dir = Path(run_dir)
    pipeline_path = run_dir / "pipeline_result.json"
    if not pipeline_path.exists():
        raise FileNotFoundError(f"pipeline_result.json not found at {pipeline_path}")
    pipeline = _read_json(pipeline_path)

    portfolio_path = run_dir / "evaluation" / "portfolio_metrics.json"
    portfolio: Dict[str, Any] = {}
    if portfolio_path.exists():
        portfolio = _read_json(portfolio_path)

    return {
        "pipeline": pipeline,
        "portfolio": portfolio,
        "wf_eval_metrics": pipeline.get("wf_eval_metrics", {}),
        "tier_assignments": pipeline.get("tier_assignments", {}),
    }


def load_trades(run_dir: Path) -> List[Dict[str, Any]]:
    """Load all per-pair trade CSVs from evaluation/per_pair_trades/.

    Args:
        run_dir: Path to the run directory.

    Returns:
        List of dicts, one per trade row. pnl_abs and pnl_pct are floats.

    Raises:
        FileNotFoundError: If evaluation/per_pair_trades/ does not exist.
    """
    trades_dir = Path(run_dir) / "evaluation" / "per_pair_trades"
    if not trades_dir.exists():
        raise FileNotFoundError(
            f"per_pair_trades/ directory not found at {trades_dir}"
        )
    all_trades: List[Dict[str, Any]] = []
    for csv_path in sorted(trades_dir.glob("*.csv")):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["pnl_abs"] = float(row["pnl_abs"])
                row["pnl_pct"] = float(row["pnl_pct"])
                all_trades.append(row)
    return all_trades


# ── Check functions ───────────────────────────────────────────────────

def check_wf_degradation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check walk-forward degradation ratios, excluding X-tier pairs.

    Flags when OOS/S1 median degradation_ratio is below _WF_DEGRADE_FAIL,
    indicating the strategy may have overfit to training data.

    Args:
        data: Dict from load_run_data() with wf_eval_metrics and tier_assignments.

    Returns:
        Check result dict with status PASS / WARNING / FAIL.
    """
    wf = data.get("wf_eval_metrics", {})
    tiers = data.get("tier_assignments", {})

    if not wf:
        return _check_result(
            "wf_degradation", "WARNING",
            "No wf_eval_metrics found in pipeline data",
        )

    ratios = []
    for sym, metrics in wf.items():
        if tiers.get(sym, {}).get("tier") == "X":
            continue
        ratios.append(metrics.get("degradation_ratio", 0.0))

    if not ratios:
        return _check_result(
            "wf_degradation", "FAIL",
            "No non-X pairs with WF data",
            0.0, _WF_DEGRADE_FAIL,
        )

    median_ratio = statistics.median(ratios)

    if median_ratio < _WF_DEGRADE_FAIL:
        return _check_result(
            "wf_degradation", "FAIL",
            f"Severe overfit: median OOS/S1 = {median_ratio:.3f}",
            median_ratio, _WF_DEGRADE_FAIL,
        )
    if median_ratio < _WF_DEGRADE_WARN:
        return _check_result(
            "wf_degradation", "WARNING",
            f"Elevated WF degradation: median = {median_ratio:.3f}",
            median_ratio, _WF_DEGRADE_WARN,
        )
    return _check_result(
        "wf_degradation", "PASS",
        f"WF degradation OK: median = {median_ratio:.3f}",
        median_ratio, _WF_DEGRADE_WARN,
    )


def check_dd_floor_gaming(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check if portfolio max_drawdown is suspiciously close to the DD floor (5%).

    The optimizer has a 5% DD floor in the objective function. If portfolio
    drawdown is exactly at 5.000%, Optuna may have gamed the floor.

    Args:
        data: Dict from load_run_data() with portfolio key.

    Returns:
        Check result dict with status PASS / WARNING / FAIL.
    """
    portfolio = data.get("portfolio", {})
    if not portfolio:
        return _check_result(
            "dd_floor_gaming", "WARNING",
            "No portfolio metrics found",
        )

    dd = portfolio.get("portfolio_max_drawdown")
    if dd is None:
        return _check_result(
            "dd_floor_gaming", "WARNING",
            "portfolio_max_drawdown not found in portfolio metrics",
        )

    if abs(dd - _MIN_DD_FLOOR) < _DD_FLOOR_TOL:
        return _check_result(
            "dd_floor_gaming", "FAIL",
            f"DD floor gaming detected — portfolio_max_drawdown={dd:.4f} "
            f"within {_DD_FLOOR_TOL} of floor ({_MIN_DD_FLOOR})",
            value=dd,
            threshold=_DD_FLOOR_TOL,
        )
    return _check_result(
        "dd_floor_gaming", "PASS",
        "No DD floor gaming detected",
        value=dd,
    )


def check_equity_reconstruction(
    data: Dict[str, Any],
    trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Check if sum of trade pnl_abs matches the reported portfolio total_pnl.

    A significant mismatch indicates a data pipeline bug (double-counting,
    missing pairs, or incorrect aggregation).

    Args:
        data: Dict from load_run_data() with portfolio key.
        trades: List of trade dicts from load_trades().

    Returns:
        Check result dict with status PASS / WARNING / FAIL.
    """
    portfolio = data.get("portfolio", {})
    total_pnl = portfolio.get("total_pnl")

    if total_pnl is None:
        return _check_result(
            "equity_reconstruction", "WARNING",
            "total_pnl not found in portfolio metrics",
        )
    if not trades:
        return _check_result(
            "equity_reconstruction", "WARNING",
            "No trades found — cannot reconstruct equity",
        )

    trades_sum = sum(t["pnl_abs"] for t in trades)

    if abs(total_pnl) < 1e-9:
        return _check_result(
            "equity_reconstruction", "WARNING",
            "total_pnl is near-zero — cannot compute relative mismatch",
            value=trades_sum,
        )

    mismatch = abs(trades_sum - total_pnl) / abs(total_pnl)

    if mismatch > _EQUITY_MISMATCH_FAIL:
        return _check_result(
            "equity_reconstruction", "FAIL",
            f"Trades PnL sum ({trades_sum:.0f}) vs total_pnl ({total_pnl:.0f}) "
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
        f"Trades PnL sum matches total_pnl within {_EQUITY_MISMATCH_WARN:.0%}",
        value=mismatch,
        threshold=_EQUITY_MISMATCH_FAIL,
    )


def check_trade_distribution(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        pnl = trade["pnl_abs"] if isinstance(trade["pnl_abs"], float) else float(trade.get("pnl_abs", 0))

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


def check_hard_stop_ratio(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    data: Dict[str, Any],
    prev_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Check if key portfolio metrics regressed compared to a previous run.

    Compares portfolio_max_drawdown and sortino_ratio between runs.
    If no previous run provided, reports current metrics as baseline.

    Args:
        data: Dict from load_run_data() for current run.
        prev_data: Dict from load_run_data() for previous run (optional).

    Returns:
        Check result dict with status PASS / WARNING / FAIL / SKIP.
    """
    portfolio = data.get("portfolio", {})
    curr_dd = portfolio.get("portfolio_max_drawdown")
    curr_sortino = portfolio.get("sortino_ratio")

    if curr_dd is None and curr_sortino is None:
        return _check_result(
            "score_regression", "WARNING",
            "No portfolio metrics (drawdown/sortino) found for current run",
        )

    if prev_data is None:
        detail_parts = []
        if curr_dd is not None:
            detail_parts.append(f"DD={curr_dd:.3f}")
        if curr_sortino is not None:
            detail_parts.append(f"Sortino={curr_sortino:.2f}")
        return _check_result(
            "score_regression", "PASS",
            f"Current metrics: {', '.join(detail_parts)} (no previous run to compare)",
            value=curr_sortino if curr_sortino is not None else curr_dd,
        )

    prev_portfolio = prev_data.get("portfolio", {})
    prev_dd = prev_portfolio.get("portfolio_max_drawdown")
    prev_sortino = prev_portfolio.get("sortino_ratio")

    issues = []
    # DD regression: drawdown increased significantly (worse)
    if curr_dd is not None and prev_dd is not None:
        dd_delta = curr_dd - prev_dd
        if dd_delta > 0.05:  # DD worsened by more than 5 percentage points
            issues.append(f"DD worsened {dd_delta:+.3f} ({prev_dd:.3f} → {curr_dd:.3f})")

    # Sortino regression: sortino dropped significantly
    if curr_sortino is not None and prev_sortino is not None:
        sortino_delta = curr_sortino - prev_sortino
        if sortino_delta < -1.0:  # Sortino dropped by more than 1.0
            issues.append(
                f"Sortino regressed {sortino_delta:+.2f} ({prev_sortino:.2f} → {curr_sortino:.2f})"
            )

    if issues:
        return _check_result(
            "score_regression", "FAIL",
            "Metric regression detected: " + "; ".join(issues),
            value=curr_sortino if curr_sortino is not None else curr_dd,
        )

    detail_parts = []
    if curr_sortino is not None and prev_sortino is not None:
        delta = curr_sortino - prev_sortino
        detail_parts.append(f"Sortino {delta:+.2f} ({prev_sortino:.2f} → {curr_sortino:.2f})")
    if curr_dd is not None and prev_dd is not None:
        delta = curr_dd - prev_dd
        detail_parts.append(f"DD {delta:+.3f} ({prev_dd:.3f} → {curr_dd:.3f})")

    return _check_result(
        "score_regression", "PASS",
        "Metrics stable or improved" + (": " + ", ".join(detail_parts) if detail_parts else ""),
        value=curr_sortino if curr_sortino is not None else curr_dd,
    )


# ── Orchestrators ─────────────────────────────────────────────────────

def quick(
    run_dir: Path,
    prev_run_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Run all quick-mode deterministic checks on a run directory.

    Loads pipeline_result.json, portfolio_metrics.json, and per-pair trade CSVs,
    then executes all 6 checks. Runs in <1s from local artifacts — no network, no LLM.

    Args:
        run_dir: Path to the current run directory.
        prev_run_dir: Optional path to a previous run for score regression check.

    Returns:
        List of check result dicts, one per check.
    """
    data = load_run_data(Path(run_dir))
    trades = load_trades(Path(run_dir))

    prev_data: Optional[Dict[str, Any]] = None
    if prev_run_dir is not None:
        try:
            prev_data = load_run_data(Path(prev_run_dir))
        except FileNotFoundError:
            pass

    return [
        check_wf_degradation(data),
        check_dd_floor_gaming(data),
        check_equity_reconstruction(data, trades),
        check_trade_distribution(trades),
        check_hard_stop_ratio(trades),
        check_score_regression(data, prev_data=prev_data),
    ]


def full(
    run_dir: Path,
    history: Optional[List[Dict[str, Any]]] = None,
    git_diff: str = "",
    prev_run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Full mode — assembles LLM context for deep analysis.

    Args:
        run_dir: Path to the current run directory.
        history: Optional list of previous iteration summaries.
        git_diff: Optional git diff string for this iteration.
        prev_run_dir: Optional path to previous run for regression check.

    Returns:
        Dict with metrics, prev_metrics, history_summary, diff_summary, quick_results.
    """
    data = load_run_data(Path(run_dir))
    trades = load_trades(Path(run_dir))

    prev_data: Optional[Dict[str, Any]] = None
    if prev_run_dir is not None:
        try:
            prev_data = load_run_data(Path(prev_run_dir))
        except FileNotFoundError:
            pass

    quick_results = quick(str(run_dir), prev_run_dir=str(prev_run_dir) if prev_run_dir else None)
    metrics = _extract_metrics(data)
    prev_metrics = _extract_metrics(prev_data) if prev_data else None

    return {
        "metrics": metrics,
        "prev_metrics": prev_metrics,
        "history_summary": _format_history_summary(history or []),
        "diff_summary": git_diff,
        "quick_results": {
            "pass": all(c["status"] != "FAIL" for c in quick_results),
            "checks": quick_results,
        },
    }


# ── CLI ────────────────────────────────────────────────────────────────

def _load_history(history_path: str) -> List[Dict[str, Any]]:
    """Load history from a JSON file. Returns empty list for /dev/null or missing."""
    if history_path == "/dev/null":
        return []
    p = Path(history_path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _quick_result_to_output(
    results: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Convert quick() results to CLI output format with pass/fail summary."""
    fails = [r for r in results if r["status"] == "FAIL"]
    warnings = [r for r in results if r["status"] == "WARNING"]
    passed = len([r for r in results if r["status"] == "PASS"])

    return {
        "pass": len(fails) == 0,
        "summary": {
            "pass": passed,
            "warn": len(warnings),
            "fail": len(fails),
        },
        "checks": results,
        "history_entries": len(history),
    }


def _full_result_to_output(
    result: Dict[str, Any],
    history: List[Dict[str, Any]],
    git_diff: str,
) -> Dict[str, Any]:
    """Convert full() results to CLI output format."""
    quick_results_wrapper = result.get("quick_results", {})
    quick_checks = quick_results_wrapper.get("checks", [])
    fails = [r for r in quick_checks if r["status"] == "FAIL"]
    warnings = [r for r in quick_checks if r["status"] == "WARNING"]
    passed = len([r for r in quick_checks if r["status"] == "PASS"])

    return {
        "pass": len(fails) == 0,
        "summary": {
            "pass": passed,
            "warn": len(warnings),
            "fail": len(fails),
        },
        "quick_checks": quick_checks,
        "metrics": result.get("metrics"),
        "history_entries": len(history),
        "git_diff_chars": len(git_diff),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="MQE Critic — deterministic sanity checks for optimization runs",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # quick subcommand
    quick_parser = subparsers.add_parser(
        "quick",
        help="Run 6 lightweight checks (<1s, no LLM)",
    )
    quick_parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to the run directory (must contain pipeline_result.json)",
    )
    quick_parser.add_argument(
        "--history",
        required=True,
        help="Path to history.json (JSON array). Use /dev/null for empty.",
    )
    quick_parser.add_argument(
        "--prev-run-dir",
        default=None,
        help="Path to previous run directory for score regression check",
    )

    # full subcommand
    full_parser = subparsers.add_parser(
        "full",
        help="Run full mode checks with LLM context preparation",
    )
    full_parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to the run directory (must contain pipeline_result.json)",
    )
    full_parser.add_argument(
        "--history",
        required=True,
        help="Path to history.json (JSON array). Use /dev/null for empty.",
    )
    full_parser.add_argument(
        "--git-diff-file",
        required=True,
        help="Path to a file containing the git diff for this iteration",
    )
    full_parser.add_argument(
        "--prev-run-dir",
        default=None,
        help="Path to previous run directory for score regression check",
    )

    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    prev_run_dir = Path(args.prev_run_dir) if args.prev_run_dir else None
    history = _load_history(args.history)

    if args.mode == "quick":
        results = quick(run_dir, prev_run_dir=prev_run_dir)
        output = _quick_result_to_output(results, history)
        print(json.dumps(output, indent=2))

    elif args.mode == "full":
        git_diff_path = Path(args.git_diff_file)
        git_diff = git_diff_path.read_text(encoding="utf-8") if git_diff_path.exists() else ""
        result = full(run_dir, history=history, git_diff=git_diff, prev_run_dir=prev_run_dir)
        output = _full_result_to_output(result, history, git_diff)
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
