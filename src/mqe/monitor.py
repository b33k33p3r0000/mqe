"""
MQE Monitor — Compact dashboard for completed + running optimization runs.
==========================================================================
Scans results/ directory, shows one line per run in a Rich table.
Running runs detected by missing pipeline_result.json + stage1/ file count.

Usage:
    uv run python -m mqe.monitor                  # default results/
    uv run python -m mqe.monitor --results-dir /path/to/results
    uv run python -m mqe.monitor --watch           # auto-refresh every 30s
    uv run python -m mqe.monitor smoke             # filter by name/tag
    uv run python -m mqe.monitor --live            # live TUI for active run
    uv run python -m mqe.monitor --once            # single live snapshot
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()


# ─── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class RunInfo:
    """Parsed info for one optimization run (completed or running)."""

    run_dir: Path
    run_id: str  # directory name (timestamp)
    tag: str = ""
    status: str = "unknown"  # "completed", "running", "partial"
    n_symbols: int = 0
    symbols: List[str] = field(default_factory=list)
    s1_trials: int = 0
    s2_trials: int = 0
    hours: int = 0
    timestamp: str = ""

    # Stage 1 progress (for running runs)
    s1_completed: int = 0  # pairs with S1 results

    # Per-pair verdicts (completed runs)
    n_pass: int = 0
    n_warn: int = 0
    n_fail: int = 0

    # Portfolio metrics (completed runs)
    portfolio_sharpe: Optional[float] = None
    portfolio_calmar: Optional[float] = None
    portfolio_dd: Optional[float] = None
    portfolio_pnl: Optional[float] = None
    portfolio_trades: int = 0
    portfolio_equity: Optional[float] = None

    # S2 objectives
    worst_pair_calmar: Optional[float] = None
    s2_max_concurrent: Optional[int] = None


@dataclass
class LivePairStatus:
    """Status of a single pair in a running optimization."""

    symbol: str
    status: str  # "done", "running", "pending"
    trials_completed: int = 0
    trials_total: int = 0
    best_value: float = 0.0
    best_sharpe: float = 0.0
    best_drawdown: float = 0.0
    best_trades: int = 0
    best_pnl_pct: float = 0.0
    timestamp: str = ""


# ─── Data Loading ─────────────────────────────────────────────────────────────


def _load_json(path: Path) -> Optional[dict]:
    """Load JSON file, return None on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _count_verdicts(
    pipeline: dict, eval_metrics: Optional[dict],
) -> tuple:
    """Count PASS/WARN/FAIL verdicts from pipeline data."""
    n_pass = n_warn = n_fail = 0
    s1_results = pipeline.get("stage1_results", {})

    for sym, res in s1_results.items():
        sharpe = res.get("sharpe_equity", 0)
        tpy = res.get("trades_per_year", 0)
        dd = abs(res.get("max_drawdown", 0))

        # Same logic as analyze.py
        issues = []
        if tpy < 30:
            issues.append("low_trades")
        if sharpe < 0.5:
            issues.append("low_sharpe")
        if dd > 15:
            issues.append("high_dd")

        if not issues:
            if sharpe > 3.0:
                n_warn += 1
            else:
                n_pass += 1
        elif "low_sharpe" in issues or "high_dd" in issues:
            n_fail += 1
        else:
            n_warn += 1

    return n_pass, n_warn, n_fail


def load_run(run_dir: Path) -> Optional[RunInfo]:
    """Load run info from a results directory."""
    if not run_dir.is_dir():
        return None

    run_id = run_dir.name
    info = RunInfo(run_dir=run_dir, run_id=run_id)

    pipeline = _load_json(run_dir / "pipeline_result.json")
    s2_result = _load_json(run_dir / "stage2_result.json")
    portfolio_metrics = _load_json(run_dir / "evaluation" / "portfolio_metrics.json")

    # Check stage1 directory for progress
    s1_dir = run_dir / "stage1"
    s1_files = list(s1_dir.glob("*.json")) if s1_dir.exists() else []
    info.s1_completed = len(s1_files)

    if pipeline:
        # Completed run
        info.status = "completed"
        info.tag = pipeline.get("tag", "")
        info.symbols = pipeline.get("symbols", [])
        info.n_symbols = len(info.symbols)
        info.s1_trials = pipeline.get("stage1_trials", 0)
        info.s2_trials = pipeline.get("stage2_trials", 0)
        info.hours = pipeline.get("hours", 0)
        info.timestamp = pipeline.get("timestamp", "")

        info.n_pass, info.n_warn, info.n_fail = _count_verdicts(
            pipeline, portfolio_metrics,
        )

        # Portfolio metrics
        if portfolio_metrics:
            info.portfolio_sharpe = portfolio_metrics.get(
                "sharpe_ratio_equity_based",
            )
            info.portfolio_calmar = portfolio_metrics.get("calmar_ratio")
            info.portfolio_dd = portfolio_metrics.get("max_drawdown")
            if info.portfolio_dd is None:
                info.portfolio_dd = portfolio_metrics.get(
                    "portfolio_max_drawdown",
                )
                if info.portfolio_dd is not None:
                    info.portfolio_dd = info.portfolio_dd * -100  # frac -> %
            info.portfolio_pnl = portfolio_metrics.get("total_pnl_pct")
            info.portfolio_trades = portfolio_metrics.get("trades", 0)
            info.portfolio_equity = portfolio_metrics.get("equity")

        # S2 objectives
        if s2_result:
            obj = s2_result.get("objectives", {})
            info.worst_pair_calmar = obj.get("worst_pair_calmar")
            params = s2_result.get("portfolio_params", {})
            info.s2_max_concurrent = params.get("max_concurrent")

    elif s1_files:
        # Running — has some S1 results but no pipeline_result yet
        info.status = "running"
        # Try to infer symbol count from first S1 result
        first_s1 = _load_json(s1_files[0])
        if first_s1:
            info.s1_trials = first_s1.get("n_trials_requested", 0)

        if s2_result:
            info.status = "partial"  # S2 done but no pipeline_result (rare)

    else:
        # Empty directory — skip (artifact or just started)
        return None

    return info


def scan_results(
    results_dir: Path,
    name_filter: Optional[str] = None,
) -> List[RunInfo]:
    """Scan results directory for all runs."""
    if not results_dir.exists():
        return []

    runs: List[RunInfo] = []
    for d in sorted(results_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if name_filter and name_filter not in d.name:
            # Also check tag
            pipeline = _load_json(d / "pipeline_result.json")
            if pipeline and name_filter not in pipeline.get("tag", ""):
                continue
            elif not pipeline:
                continue

        info = load_run(d)
        if info:
            runs.append(info)

    return runs


def load_live_run(run_dir: Path) -> List[LivePairStatus]:
    """Read stage1/ directory and return per-pair live status.

    - ``{SYMBOL}.json`` (no ``_progress`` suffix) = done pair.
    - ``{SYMBOL}_progress.json`` = running pair.
    - Sort: done first, then running.
    """
    s1_dir = run_dir / "stage1"
    if not s1_dir.exists():
        return []

    pairs: List[LivePairStatus] = []

    # Completed pairs: *.json excluding *_progress.json
    for f in sorted(s1_dir.glob("*.json")):
        if f.stem.endswith("_progress"):
            continue
        data = _load_json(f)
        if data is None:
            continue
        pairs.append(LivePairStatus(
            symbol=data.get("symbol", f.stem.replace("_", "/")),
            status="done",
            trials_completed=data.get("n_trials_completed", 0),
            trials_total=data.get("n_trials_requested", 0),
            best_value=data.get("objective_value", 0.0),
            best_sharpe=data.get("sharpe_equity", 0.0),
            best_drawdown=data.get("max_drawdown", 0.0),
            best_trades=data.get("trades", 0),
            best_pnl_pct=data.get("total_pnl_pct", 0.0),
        ))

    # Running pairs: *_progress.json
    for f in sorted(s1_dir.glob("*_progress.json")):
        data = _load_json(f)
        if data is None:
            continue
        pairs.append(LivePairStatus(
            symbol=data.get("symbol", f.stem.replace("_progress", "").replace("_", "/")),
            status="running",
            trials_completed=data.get("trials_completed", 0),
            trials_total=data.get("trials_total", 0),
            best_value=data.get("best_value", 0.0),
            best_sharpe=data.get("best_sharpe", 0.0),
            best_drawdown=data.get("best_drawdown", 0.0),
            best_trades=data.get("best_trades", 0),
            best_pnl_pct=data.get("best_pnl_pct", 0.0),
            timestamp=data.get("timestamp", ""),
        ))

    return pairs


def find_active_run(results_dir: Path) -> Optional[Path]:
    """Find the most recent run directory without ``pipeline_result.json``.

    Returns None if all runs are completed or directory is empty.
    """
    if not results_dir.exists():
        return None

    candidates: List[Path] = []
    for d in sorted(results_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        # Active = no pipeline_result.json AND has stage1/ with files
        if (d / "pipeline_result.json").exists():
            continue
        s1_dir = d / "stage1"
        if s1_dir.exists() and any(s1_dir.glob("*.json")):
            candidates.append(d)

    if not candidates:
        return None

    # Most recent = last in sorted order (timestamp-based names)
    return candidates[-1]


# ─── Formatting Helpers ───────────────────────────────────────────────────────


def _format_elapsed(seconds: int) -> str:
    """Format seconds as Xh Ym."""
    h, m = divmod(seconds // 60, 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def _progress_bar(completed: int, total: int, width: int = 8) -> str:
    """Render a text-based progress bar."""
    if total <= 0:
        return " " * width
    frac = min(1.0, completed / total)
    filled = int(frac * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _fmt_float(val: Optional[float], decimals: int = 1, sign: bool = False) -> str:
    if val is None:
        return "-"
    fmt = f"+.{decimals}f" if sign else f".{decimals}f"
    return f"{val:{fmt}}"


def _fmt_pct(val: Optional[float], decimals: int = 1) -> str:
    if val is None:
        return "-"
    return f"{val:+.{decimals}f}%"


def _fmt_int(val: Optional[int]) -> str:
    if val is None:
        return "-"
    return str(val)


def _verdict_text(n_pass: int, n_warn: int, n_fail: int, total: int) -> Text:
    """Format verdict counts as colored text."""
    parts = Text()
    parts.append(f"{n_pass}", style="green")
    parts.append("/")
    if n_warn > 0:
        parts.append(f"{n_warn}", style="yellow")
    else:
        parts.append("0")
    parts.append("/")
    if n_fail > 0:
        parts.append(f"{n_fail}", style="red")
    else:
        parts.append("0")
    return parts


def _status_text(info: RunInfo) -> Text:
    """Format run status."""
    if info.status == "completed":
        return Text("DONE", style="bold green")
    elif info.status == "running":
        progress = f"S1 {info.s1_completed}/?"
        if info.n_symbols > 0:
            progress = f"S1 {info.s1_completed}/{info.n_symbols}"
        return Text(progress, style="bold cyan")
    else:
        return Text("PARTIAL", style="bold yellow")


# ─── Render ───────────────────────────────────────────────────────────────────


def render_table(runs: List[RunInfo]) -> Table:
    """Render compact runs table."""
    table = Table(
        title="MQE Runs",
        show_header=True,
        header_style="bold",
        show_lines=False,
        padding=(0, 1),
        expand=False,
    )

    table.add_column("Run", style="dim", no_wrap=True)
    table.add_column("Tag", no_wrap=True, max_width=15)
    table.add_column("Status", no_wrap=True)
    table.add_column("Pairs", justify="right")
    table.add_column("S1/S2", justify="right", no_wrap=True)
    table.add_column("P/W/F", no_wrap=True)
    table.add_column("Sharpe", justify="right")
    table.add_column("Calmar", justify="right")
    table.add_column("DD", justify="right")
    table.add_column("PnL%", justify="right")
    table.add_column("Trades", justify="right")
    table.add_column("Equity", justify="right")

    for info in runs:
        status = _status_text(info)

        if info.status == "completed":
            verdicts = _verdict_text(
                info.n_pass, info.n_warn, info.n_fail, info.n_symbols,
            )
            trials = f"{info.s1_trials}/{info.s2_trials}"

            # Color Sharpe
            sharpe_str = _fmt_float(info.portfolio_sharpe, 2)
            sharpe_style = ""
            if info.portfolio_sharpe is not None:
                if info.portfolio_sharpe >= 2.0:
                    sharpe_style = "green"
                elif info.portfolio_sharpe >= 1.0:
                    sharpe_style = "yellow"
                else:
                    sharpe_style = "red"

            # Color DD
            dd_str = _fmt_pct(info.portfolio_dd)
            dd_style = ""
            if info.portfolio_dd is not None:
                dd_abs = abs(info.portfolio_dd)
                if dd_abs < 5:
                    dd_style = "green"
                elif dd_abs < 10:
                    dd_style = "yellow"
                else:
                    dd_style = "red"

            # Format equity
            equity_str = "-"
            if info.portfolio_equity is not None:
                equity_str = f"${info.portfolio_equity:,.0f}"

            table.add_row(
                info.run_id,
                info.tag or "-",
                status,
                str(info.n_symbols),
                trials,
                verdicts,
                Text(sharpe_str, style=sharpe_style),
                _fmt_float(info.portfolio_calmar, 1),
                Text(dd_str, style=dd_style),
                _fmt_pct(info.portfolio_pnl),
                str(info.portfolio_trades),
                equity_str,
            )
        else:
            # Running/partial — minimal info
            table.add_row(
                info.run_id,
                info.tag or "-",
                status,
                str(info.n_symbols) if info.n_symbols > 0 else "?",
                f"{info.s1_trials}/?" if info.s1_trials else "?/?",
                Text("-"),
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
            )

    return table


def render_dashboard(
    results_dir: Path,
    name_filter: Optional[str] = None,
) -> None:
    """Render the full monitor dashboard."""
    runs = scan_results(results_dir, name_filter)

    if not runs:
        console.print(f"[dim]No runs found in {results_dir}[/dim]")
        return

    table = render_table(runs)
    console.print(table)
    console.print(
        f"[dim]{len(runs)} run(s) | {results_dir} | "
        f"{time.strftime('%H:%M:%S')}[/dim]",
    )


# ─── Live Dashboard ─────────────────────────────────────────────────────────


_LIVE_STATUS_ICONS = {
    "done": ("✓", "green"),
    "running": ("▶", "cyan"),
    "pending": ("⏳", "dim"),
}


def render_live_table(
    pairs: List[LivePairStatus],
    tag: str = "",
    elapsed_s: int = 0,
) -> Table:
    """Render Rich Table for live optimization progress."""
    title = "MQE Live"
    if tag:
        title += f" [{tag}]"

    table = Table(
        title=title,
        show_header=True,
        header_style="bold",
        show_lines=False,
        padding=(0, 1),
        expand=False,
    )

    table.add_column("", no_wrap=True, width=2)  # status icon
    table.add_column("Pair", no_wrap=True)
    table.add_column("Trials", justify="right", no_wrap=True)
    table.add_column("Progress", no_wrap=True)
    table.add_column("Value", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("DD", justify="right")

    for p in pairs:
        icon_char, icon_style = _LIVE_STATUS_ICONS.get(
            p.status, ("?", "dim"),
        )
        icon = Text(icon_char, style=icon_style)

        # Trials count
        if p.trials_total > 0:
            trials_str = f"{p.trials_completed:,}/{p.trials_total:,}"
        else:
            trials_str = "-"

        # Progress bar
        bar = _progress_bar(p.trials_completed, p.trials_total)

        # Value
        value_str = _fmt_float(p.best_value, 2) if p.best_value else "-"

        # Sharpe with color
        sharpe_str = _fmt_float(p.best_sharpe, 2) if p.best_sharpe else "-"
        sharpe_style = ""
        if p.best_sharpe >= 2.0:
            sharpe_style = "green"
        elif p.best_sharpe >= 1.0:
            sharpe_style = "yellow"
        elif p.best_sharpe > 0:
            sharpe_style = "red"

        # DD with color
        dd_str = f"{p.best_drawdown:.1f}%" if p.best_drawdown else "-"
        dd_style = ""
        if p.best_drawdown:
            dd_abs = abs(p.best_drawdown)
            if dd_abs < 5:
                dd_style = "green"
            elif dd_abs < 10:
                dd_style = "yellow"
            else:
                dd_style = "red"

        table.add_row(
            icon,
            p.symbol,
            trials_str,
            bar,
            value_str,
            Text(sharpe_str, style=sharpe_style),
            Text(dd_str, style=dd_style),
        )

    # Caption: summary stats
    n_done = sum(1 for p in pairs if p.status == "done")
    n_total = len(pairs)
    trials_done = sum(p.trials_completed for p in pairs)
    trials_total = sum(p.trials_total for p in pairs)
    trials_pct = (trials_done / trials_total * 100) if trials_total > 0 else 0
    elapsed_str = _format_elapsed(elapsed_s)

    caption = (
        f"Pairs {n_done}/{n_total} | "
        f"Trials {trials_done:,}/{trials_total:,} ({trials_pct:.0f}%) | "
        f"Elapsed {elapsed_str}"
    )
    table.caption = caption

    return table


def run_live_dashboard(
    results_dir: Path,
    refresh_interval: float = 3.0,
    once: bool = False,
) -> None:
    """Main live dashboard loop.

    Finds active run, displays live table with Rich Live.
    When ``pipeline_result.json`` appears, shows completion and exits.
    """
    from rich.live import Live

    run_dir = find_active_run(results_dir)

    if run_dir is None:
        # No active run — show completed runs summary and return
        console.print("[dim]No active run found.[/dim]")
        render_dashboard(results_dir)
        return

    run_id = run_dir.name
    tag = ""

    # Try to detect tag from config or directory structure
    config = _load_json(run_dir / "run_config.json")
    if config:
        tag = config.get("tag", "")

    start_time = time.time()

    if once:
        # Single snapshot
        pairs = load_live_run(run_dir)
        elapsed_s = int(time.time() - start_time)
        table = render_live_table(pairs, tag=tag or run_id, elapsed_s=elapsed_s)
        console.print(table)
        return

    # Live loop
    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                # Check for completion
                if (run_dir / "pipeline_result.json").exists():
                    pairs = load_live_run(run_dir)
                    elapsed_s = int(time.time() - start_time)
                    table = render_live_table(
                        pairs, tag=tag or run_id, elapsed_s=elapsed_s,
                    )
                    live.update(table)
                    console.print(
                        f"\n[bold green]Run {run_id} completed![/bold green]",
                    )
                    break

                pairs = load_live_run(run_dir)
                elapsed_s = int(time.time() - start_time)
                table = render_live_table(
                    pairs, tag=tag or run_id, elapsed_s=elapsed_s,
                )
                live.update(table)
                time.sleep(refresh_interval)

    except KeyboardInterrupt:
        console.print("\n[dim]Live dashboard stopped.[/dim]")


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MQE Monitor — compact dashboard for optimization runs",
    )
    parser.add_argument(
        "filter", nargs="?", default=None,
        help="Filter runs by name or tag",
    )
    parser.add_argument(
        "--results-dir", type=str, default="results",
        help="Path to results directory (default: results/)",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Auto-refresh every 30 seconds",
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Refresh interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Live dashboard for active optimization run",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Show single live snapshot and exit",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        console.print(f"[red]Results directory not found: {results_dir}[/red]")
        sys.exit(1)

    if args.live or args.once:
        run_live_dashboard(results_dir, once=args.once)
    elif args.watch:
        try:
            while True:
                console.clear()
                render_dashboard(results_dir, args.filter)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            console.print("\n[dim]Monitor stopped.[/dim]")
    else:
        render_dashboard(results_dir, args.filter)


if __name__ == "__main__":
    main()
