"""
MQE Report — Rich console output for pipeline results.
========================================================
Adapted from QRE report.py. Console-only for v1 (no HTML).

Displays per-pair summaries and portfolio summary using Rich tables.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

logger = logging.getLogger("mqe.report")

console = Console()

# Verdict color mapping
_VERDICT_STYLE = {
    "PASS": "bold green",
    "WARN": "bold yellow",
    "FAIL": "bold red",
}


def _verdict_text(verdict: str) -> Text:
    """Create styled verdict text."""
    style = _VERDICT_STYLE.get(verdict, "bold white")
    return Text(verdict, style=style)


# ─── PER-PAIR TABLE ──────────────────────────────────────────────────────────


def render_pair_table(per_pair: List[Dict[str, Any]]) -> Table:
    """Build Rich table with per-pair analysis results.

    Args:
        per_pair: List of per-pair analysis dicts from analyze_pair().

    Returns:
        Rich Table object.
    """
    table = Table(
        title="Per-Pair Results",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Symbol", style="bold", min_width=12)
    table.add_column("Verdict", justify="center", min_width=8)
    table.add_column("Trades/yr", justify="right", min_width=10)
    table.add_column("Sharpe", justify="right", min_width=8)
    table.add_column("Calmar", justify="right", min_width=8)
    table.add_column("Max DD%", justify="right", min_width=8)
    table.add_column("Win Rate", justify="right", min_width=8)
    table.add_column("Issues", min_width=20)

    for pair in per_pair:
        summary = pair.get("metrics_summary", {})
        verdict = pair.get("verdict", "?")
        issues = pair.get("failures", []) + pair.get("warnings", [])
        issues_str = "; ".join(issues[:3]) if issues else "-"

        table.add_row(
            pair.get("symbol", "?"),
            _verdict_text(verdict),
            f"{summary.get('trades_per_year', 0):.0f}",
            f"{summary.get('sharpe', 0):.2f}",
            f"{summary.get('calmar', 0):.2f}",
            f"{summary.get('max_dd', 0):.1f}%",
            f"{summary.get('win_rate', 0):.1%}",
            issues_str,
        )

    return table


# ─── PORTFOLIO PANEL ─────────────────────────────────────────────────────────


def render_portfolio_panel(portfolio: Dict[str, Any]) -> Panel:
    """Build Rich panel with portfolio analysis summary.

    Args:
        portfolio: Portfolio analysis dict from analyze_portfolio().

    Returns:
        Rich Panel object.
    """
    verdict = portfolio.get("verdict", "?")
    pcalmar = portfolio.get("portfolio_calmar", 0)
    wcalmar = portfolio.get("worst_pair_calmar", 0)
    params = portfolio.get("portfolio_params", {})

    lines: List[str] = []
    lines.append(f"Portfolio Calmar:      {pcalmar:.2f}")
    lines.append(f"Worst Pair Calmar:     {wcalmar:.2f}")

    if params:
        lines.append("")
        lines.append("Portfolio Params:")
        for key, value in params.items():
            lines.append(f"  {key}: {value}")

    failures = portfolio.get("failures", [])
    warnings = portfolio.get("warnings", [])
    if failures:
        lines.append("")
        lines.append("[red]Failures:[/red]")
        for f in failures:
            lines.append(f"  [red]X[/red] {f}")
    if warnings:
        lines.append("")
        lines.append("[yellow]Warnings:[/yellow]")
        for w in warnings:
            lines.append(f"  [yellow]![/yellow] {w}")

    content = "\n".join(lines)
    style = _VERDICT_STYLE.get(verdict, "white")

    return Panel(
        content,
        title=f"Portfolio: {verdict}",
        title_align="left",
        border_style=style,
    )


# ─── MAIN REPORT ─────────────────────────────────────────────────────────────


def print_report(analysis: Dict[str, Any]) -> None:
    """Print full analysis report to console using Rich.

    Args:
        analysis: Full analysis dict from analyze_run(), with keys:
            per_pair (list) and portfolio (dict).
    """
    per_pair = analysis.get("per_pair", [])
    portfolio = analysis.get("portfolio", {})

    console.print()
    console.rule("[bold cyan]MQE Run Analysis[/bold cyan]")
    console.print()

    if per_pair:
        table = render_pair_table(per_pair)
        console.print(table)
        console.print()

    panel = render_portfolio_panel(portfolio)
    console.print(panel)
    console.print()


def format_discord_summary(analysis: Dict[str, Any]) -> str:
    """Format analysis as compact Discord code block.

    Args:
        analysis: Full analysis dict from analyze_run().

    Returns:
        Formatted string for Discord webhook.
    """
    lines: List[str] = []
    lines.append("```")
    lines.append("MQE RUN ANALYSIS")
    lines.append("=" * 30)

    per_pair = analysis.get("per_pair", [])
    portfolio = analysis.get("portfolio", {})

    # Per-pair summary
    for pair in per_pair:
        symbol = pair.get("symbol", "?")
        verdict = pair.get("verdict", "?")
        summary = pair.get("metrics_summary", {})
        sharpe = summary.get("sharpe", 0)
        calmar = summary.get("calmar", 0)
        tag = "[ok]" if verdict == "PASS" else "[!!]" if verdict == "WARN" else "[XX]"
        lines.append(f"  {tag} {symbol:<12} Sharpe={sharpe:.2f} Calmar={calmar:.2f}")

    lines.append("-" * 30)

    # Portfolio verdict
    pv = portfolio.get("verdict", "?")
    pcalmar = portfolio.get("portfolio_calmar", 0)
    lines.append(f"PORTFOLIO:  {pv}  (Calmar={pcalmar:.2f})")

    # Issues
    failures = portfolio.get("failures", [])
    warnings = portfolio.get("warnings", [])
    if failures or warnings:
        lines.append("")
        for f in failures:
            lines.append(f"  [XX] {f}")
        for w in warnings:
            lines.append(f"  [!!] {w}")

    lines.append("```")

    result = "\n".join(lines)
    # Truncate to Discord limit
    if len(result) > 1900:
        result = result[:1890] + "\n```"

    return result
