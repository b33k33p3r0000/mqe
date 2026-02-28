"""
MQE Cross-Run Comparison — Side-by-side comparison of multiple optimizer runs.
===============================================================================
Loads pipeline_result.json + evaluation metrics from multiple run directories,
builds comparison tables per symbol and portfolio, and outputs via Rich or Markdown.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from mqe.analyze import _normalize_metrics
from mqe.io import load_json

logger = logging.getLogger("mqe.compare")

console = Console()


# ─── DATA LOADING ────────────────────────────────────────────────────────────


def load_run(run_dir: Path) -> Dict[str, Any]:
    """Load pipeline result and evaluation metrics from a run directory.

    Args:
        run_dir: Path to a run directory (e.g. results/20260228_115425/).

    Returns:
        Dict with keys: dir, tag, timestamp, symbols, stage1_trials,
        stage2_trials, hours, stage1_results, stage2_results,
        per_pair_metrics, portfolio_metrics.
    """
    run_dir = Path(run_dir)
    pipeline_path = run_dir / "pipeline_result.json"
    pipeline = load_json(pipeline_path)

    tag = pipeline.get("tag", "") or run_dir.name
    timestamp = pipeline.get("timestamp", "")
    symbols = pipeline.get("symbols", [])
    stage1_trials = pipeline.get("stage1_trials", 0)
    stage2_trials = pipeline.get("stage2_trials", 0)
    hours = pipeline.get("hours", 0)
    stage1_results = pipeline.get("stage1_results", {})
    stage2_results = pipeline.get("stage2_results", {})

    # Load evaluation metrics if available
    eval_dir = run_dir / "evaluation"
    per_pair_metrics: Dict[str, Any] = {}
    portfolio_metrics: Optional[Dict[str, Any]] = None

    if eval_dir.is_dir():
        per_pair_path = eval_dir / "per_pair_metrics.json"
        portfolio_path = eval_dir / "portfolio_metrics.json"

        if per_pair_path.exists():
            try:
                per_pair_metrics = load_json(per_pair_path)
            except Exception as exc:
                logger.warning("Failed to load per_pair_metrics from %s: %s", per_pair_path, exc)

        if portfolio_path.exists():
            try:
                portfolio_metrics = load_json(portfolio_path)
            except Exception as exc:
                logger.warning("Failed to load portfolio_metrics from %s: %s", portfolio_path, exc)

    return {
        "dir": str(run_dir),
        "tag": tag,
        "timestamp": timestamp,
        "symbols": symbols,
        "stage1_trials": stage1_trials,
        "stage2_trials": stage2_trials,
        "hours": hours,
        "stage1_results": stage1_results,
        "stage2_results": stage2_results,
        "per_pair_metrics": per_pair_metrics,
        "portfolio_metrics": portfolio_metrics,
    }


# ─── COMPARISON BUILDER ─────────────────────────────────────────────────────


def _pair_metrics_for_run(
    run: Dict[str, Any], symbol: str
) -> Dict[str, Any]:
    """Extract normalized per-pair metrics for a symbol from a run.

    Prefers evaluation per_pair_metrics; falls back to stage1_results.
    """
    # Try evaluation metrics first
    if symbol in run["per_pair_metrics"]:
        raw = run["per_pair_metrics"][symbol]
    elif symbol in run["stage1_results"]:
        s1 = run["stage1_results"][symbol]
        # Stage 1 may have metrics nested or flat
        raw = s1.get("metrics", s1) if isinstance(s1, dict) else s1
    else:
        return {}

    return _normalize_metrics(raw)


def compare_runs(run_dirs: List[Path]) -> Dict[str, Any]:
    """Load all runs and build a comparison dict.

    Args:
        run_dirs: List of run directory paths.

    Returns:
        Dict with keys:
        - runs: list of loaded run dicts
        - per_pair_comparison: dict keyed by symbol, each with list of metric dicts
        - portfolio_comparison: list of portfolio metric dicts per run
    """
    runs = [load_run(d) for d in run_dirs]

    # Collect all symbols across runs
    all_symbols: List[str] = []
    seen: set = set()
    for run in runs:
        for sym in run["symbols"]:
            if sym not in seen:
                all_symbols.append(sym)
                seen.add(sym)

    # Per-pair comparison
    per_pair_comparison: Dict[str, List[Dict[str, Any]]] = {}
    for symbol in all_symbols:
        entries: List[Dict[str, Any]] = []
        for run in runs:
            norm = _pair_metrics_for_run(run, symbol)
            entries.append({
                "run_tag": run["tag"],
                "sharpe": norm.get("sharpe", 0),
                "calmar": norm.get("calmar", 0),
                "max_dd": norm.get("max_dd", 0),
                "pnl_pct": norm.get("total_pnl_pct", 0),
                "trades_per_year": norm.get("trades_per_year", 0),
                "win_rate": norm.get("win_rate", 0),
            })
        per_pair_comparison[symbol] = entries

    # Portfolio comparison
    portfolio_comparison: List[Dict[str, Any]] = []
    for run in runs:
        s2 = run["stage2_results"]
        objectives = s2.get("objectives", {})

        # Start with stage2 objectives
        entry: Dict[str, Any] = {
            "run_tag": run["tag"],
            "portfolio_calmar": objectives.get("portfolio_calmar", 0),
            "worst_pair_calmar": objectives.get("worst_pair_calmar", 0),
        }

        # Enrich with portfolio evaluation metrics if available
        pm = run["portfolio_metrics"]
        if pm:
            norm_pm = _normalize_metrics(pm)
            entry["sharpe"] = norm_pm.get("sharpe", 0)
            entry["sortino"] = norm_pm.get("sortino", 0)
            entry["max_dd"] = norm_pm.get("max_dd", 0)
            entry["pnl_pct"] = norm_pm.get("total_pnl_pct", 0)
            entry["trades"] = norm_pm.get("trades", 0)
        else:
            entry["sharpe"] = 0
            entry["sortino"] = 0
            entry["max_dd"] = 0
            entry["pnl_pct"] = 0
            entry["trades"] = 0

        portfolio_comparison.append(entry)

    return {
        "runs": runs,
        "per_pair_comparison": per_pair_comparison,
        "portfolio_comparison": portfolio_comparison,
    }


# ─── FORMATTING HELPERS ─────────────────────────────────────────────────────


def _fmt(value: Any, decimals: int = 2) -> str:
    """Format a numeric value safely."""
    if isinstance(value, int):
        return str(value)
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


# ─── RICH CONSOLE OUTPUT ────────────────────────────────────────────────────


def print_comparison(comparison: Dict[str, Any]) -> None:
    """Print comparison tables to console using Rich.

    Args:
        comparison: Dict from compare_runs().
    """
    runs = comparison["runs"]
    per_pair = comparison["per_pair_comparison"]
    portfolio = comparison["portfolio_comparison"]

    # Run overview
    console.print()
    overview = Table(title="Run Overview", show_lines=True)
    overview.add_column("", style="bold")
    for run in runs:
        overview.add_column(run["tag"], justify="center")

    overview.add_row(
        "Timestamp", *[r["timestamp"] or "-" for r in runs]
    )
    overview.add_row(
        "Symbols", *[", ".join(r["symbols"]) for r in runs]
    )
    overview.add_row(
        "S1 Trials", *[str(r["stage1_trials"]) for r in runs]
    )
    overview.add_row(
        "S2 Trials", *[str(r["stage2_trials"]) for r in runs]
    )
    overview.add_row(
        "Hours", *[_fmt(r["hours"], 1) for r in runs]
    )
    console.print(overview)

    # Per-pair tables
    for symbol, entries in per_pair.items():
        console.print()
        table = Table(title=f"Per-Pair: {symbol}", show_lines=True)
        table.add_column("Metric", style="bold")
        for entry in entries:
            table.add_column(entry["run_tag"], justify="right")

        table.add_row("Sharpe", *[_fmt(e["sharpe"]) for e in entries])
        table.add_row("Calmar", *[_fmt(e["calmar"]) for e in entries])
        table.add_row("Max DD %", *[_fmt(e["max_dd"]) for e in entries])
        table.add_row("PnL %", *[_fmt(e["pnl_pct"]) for e in entries])
        table.add_row("Trades/yr", *[_fmt(e["trades_per_year"], 0) for e in entries])
        table.add_row("Win Rate", *[_fmt(e["win_rate"]) for e in entries])

        console.print(table)

    # Portfolio table
    console.print()
    ptable = Table(title="Portfolio Comparison", show_lines=True)
    ptable.add_column("Metric", style="bold")
    for entry in portfolio:
        ptable.add_column(entry["run_tag"], justify="right")

    ptable.add_row("Portfolio Calmar", *[_fmt(e["portfolio_calmar"]) for e in portfolio])
    ptable.add_row("Worst Pair Calmar", *[_fmt(e["worst_pair_calmar"]) for e in portfolio])
    ptable.add_row("Sharpe", *[_fmt(e["sharpe"]) for e in portfolio])
    ptable.add_row("Sortino", *[_fmt(e["sortino"]) for e in portfolio])
    ptable.add_row("Max DD %", *[_fmt(e["max_dd"]) for e in portfolio])
    ptable.add_row("PnL %", *[_fmt(e["pnl_pct"]) for e in portfolio])
    ptable.add_row("Trades", *[_fmt(e["trades"], 0) for e in portfolio])

    console.print(ptable)
    console.print()


# ─── MARKDOWN OUTPUT ─────────────────────────────────────────────────────────


def generate_comparison_markdown(comparison: Dict[str, Any]) -> str:
    """Generate Markdown string with comparison tables.

    Args:
        comparison: Dict from compare_runs().

    Returns:
        Markdown-formatted string.
    """
    runs = comparison["runs"]
    per_pair = comparison["per_pair_comparison"]
    portfolio = comparison["portfolio_comparison"]
    lines: List[str] = []

    # Header
    tags = [r["tag"] for r in runs]
    lines.append(f"# Cross-Run Comparison: {' vs '.join(tags)}")
    lines.append("")

    # Run overview
    lines.append("## Run Overview")
    lines.append("")
    header = "| | " + " | ".join(r["tag"] for r in runs) + " |"
    sep = "|---|" + "|".join(["---:" for _ in runs]) + "|"
    lines.append(header)
    lines.append(sep)
    lines.append(
        "| Timestamp | " + " | ".join(r["timestamp"] or "-" for r in runs) + " |"
    )
    lines.append(
        "| Symbols | " + " | ".join(", ".join(r["symbols"]) for r in runs) + " |"
    )
    lines.append(
        "| S1 Trials | " + " | ".join(str(r["stage1_trials"]) for r in runs) + " |"
    )
    lines.append(
        "| S2 Trials | " + " | ".join(str(r["stage2_trials"]) for r in runs) + " |"
    )
    lines.append(
        "| Hours | " + " | ".join(_fmt(r["hours"], 1) for r in runs) + " |"
    )
    lines.append("")

    # Per-pair tables
    for symbol, entries in per_pair.items():
        lines.append(f"## Per-Pair: {symbol}")
        lines.append("")
        header = "| Metric | " + " | ".join(e["run_tag"] for e in entries) + " |"
        sep = "|---|" + "|".join(["---:" for _ in entries]) + "|"
        lines.append(header)
        lines.append(sep)
        lines.append(
            "| Sharpe | " + " | ".join(_fmt(e["sharpe"]) for e in entries) + " |"
        )
        lines.append(
            "| Calmar | " + " | ".join(_fmt(e["calmar"]) for e in entries) + " |"
        )
        lines.append(
            "| Max DD % | " + " | ".join(_fmt(e["max_dd"]) for e in entries) + " |"
        )
        lines.append(
            "| PnL % | " + " | ".join(_fmt(e["pnl_pct"]) for e in entries) + " |"
        )
        lines.append(
            "| Trades/yr | " + " | ".join(_fmt(e["trades_per_year"], 0) for e in entries) + " |"
        )
        lines.append(
            "| Win Rate | " + " | ".join(_fmt(e["win_rate"]) for e in entries) + " |"
        )
        lines.append("")

    # Portfolio table
    lines.append("## Portfolio Comparison")
    lines.append("")
    header = "| Metric | " + " | ".join(e["run_tag"] for e in portfolio) + " |"
    sep = "|---|" + "|".join(["---:" for _ in portfolio]) + "|"
    lines.append(header)
    lines.append(sep)
    lines.append(
        "| Portfolio Calmar | "
        + " | ".join(_fmt(e["portfolio_calmar"]) for e in portfolio) + " |"
    )
    lines.append(
        "| Worst Pair Calmar | "
        + " | ".join(_fmt(e["worst_pair_calmar"]) for e in portfolio) + " |"
    )
    lines.append(
        "| Sharpe | " + " | ".join(_fmt(e["sharpe"]) for e in portfolio) + " |"
    )
    lines.append(
        "| Sortino | " + " | ".join(_fmt(e["sortino"]) for e in portfolio) + " |"
    )
    lines.append(
        "| Max DD % | " + " | ".join(_fmt(e["max_dd"]) for e in portfolio) + " |"
    )
    lines.append(
        "| PnL % | " + " | ".join(_fmt(e["pnl_pct"]) for e in portfolio) + " |"
    )
    lines.append(
        "| Trades | " + " | ".join(_fmt(e["trades"], 0) for e in portfolio) + " |"
    )
    lines.append("")

    return "\n".join(lines)


# ─── CLI ENTRY POINT ────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point for cross-run comparison.

    Usage: python -m mqe.compare results/run1 results/run2 [--output report.md]
    """
    parser = argparse.ArgumentParser(
        description="MQE Cross-Run Comparison — compare multiple optimizer runs side-by-side."
    )
    parser.add_argument(
        "run_dirs",
        nargs="+",
        type=Path,
        help="Paths to run directories (e.g. results/20260228_115425).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to save Markdown comparison report.",
    )
    args = parser.parse_args()

    comparison = compare_runs(args.run_dirs)
    print_comparison(comparison)

    if args.output:
        md = generate_comparison_markdown(comparison)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md, encoding="utf-8")
        console.print(f"[green]Markdown report saved to {args.output}[/green]")


if __name__ == "__main__":
    main()
