"""
MQE Report — Rich console output + Markdown report for pipeline results.
========================================================================
Displays per-pair summaries, params, portfolio summary, and verdicts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

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

# Stage 1 param display names (ordered)
_S1_PARAM_KEYS = [
    "macd_fast", "macd_slow", "macd_signal",
    "rsi_period", "rsi_lower", "rsi_upper", "rsi_lookback",
    "trend_tf", "adx_threshold",
    "trail_mult", "hard_stop_mult", "max_hold_bars",
]


def _verdict_text(verdict: str) -> Text:
    """Create styled verdict text."""
    style = _VERDICT_STYLE.get(verdict, "bold white")
    return Text(verdict, style=style)


from mqe.io import fmt as _fmt  # noqa: E402


# ─── RICH CONSOLE REPORT ────────────────────────────────────────────────────


def render_pair_table(per_pair: list[dict[str, Any]]) -> Table:
    """Build Rich table with per-pair analysis results."""
    table = Table(
        title="Per-Pair Results (Full Backtest)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Symbol", style="bold", min_width=12)
    table.add_column("Verdict", justify="center", min_width=8)
    table.add_column("Trades/yr", justify="right", min_width=10)
    table.add_column("Sharpe", justify="right", min_width=8)
    table.add_column("Calmar", justify="right", min_width=8)
    table.add_column("Max DD%", justify="right", min_width=8)
    table.add_column("PnL%", justify="right", min_width=8)
    table.add_column("Win Rate", justify="right", min_width=8)
    table.add_column("PF", justify="right", min_width=6)
    table.add_column("Issues", min_width=20)

    for pair in per_pair:
        s = pair.get("metrics_summary", {})
        verdict = pair.get("verdict", "?")
        issues = pair.get("failures", []) + pair.get("warnings", [])
        issues_str = "; ".join(issues[:3]) if issues else "-"

        table.add_row(
            pair.get("symbol", "?"),
            _verdict_text(verdict),
            _fmt(s.get("trades_per_year", 0), 0),
            _fmt(s.get("sharpe", 0)),
            _fmt(s.get("calmar", 0)),
            f"{abs(s.get('max_dd', 0)):.1f}%",
            f"{s.get('total_pnl_pct', 0):.1f}%",
            f"{s.get('win_rate', 0):.1f}%",
            _fmt(s.get("profit_factor", 0)),
            issues_str,
        )

    return table


def render_params_table(
    stage1_results: dict[str, dict[str, Any]],
) -> Table:
    """Build Rich table with per-pair Stage 1 params."""
    table = Table(
        title="Stage 1 Parameters",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Param", style="bold", min_width=16)
    for sym in stage1_results:
        table.add_column(sym, justify="right", min_width=10)

    for key in _S1_PARAM_KEYS:
        row = [key]
        for sym in stage1_results:
            val = stage1_results[sym].get(key, "-")
            if isinstance(val, float):
                row.append(f"{val:.3f}" if val < 10 else f"{val:.1f}")
            else:
                row.append(str(val))
        table.add_row(*row)

    return table


def render_portfolio_panel(
    portfolio: dict[str, Any],
    eval_result: dict[str, Any] | None = None,
) -> Panel:
    """Build Rich panel with portfolio analysis summary."""
    verdict = portfolio.get("verdict", "?")
    pcalmar = portfolio.get("portfolio_calmar", 0)
    wcalmar = portfolio.get("worst_pair_calmar", 0)
    params = portfolio.get("portfolio_params", {})
    pm = portfolio.get("portfolio_metrics", {})

    lines: list[str] = []
    lines.append(f"Portfolio Calmar:      {pcalmar:.2f}")
    lines.append(f"Worst Pair Calmar:     {wcalmar:.2f}")

    if pm:
        lines.append(f"Sharpe (equity):       {pm.get('sharpe', 0):.2f}")
        lines.append(f"Sortino:               {pm.get('sortino', 0):.2f}")
        lines.append(f"Max DD:                {abs(pm.get('max_dd', 0)):.1f}%")
        lines.append(f"PnL:                   {pm.get('total_pnl_pct', 0):.1f}%")
        lines.append(f"Total trades:          {pm.get('trades', 0)}")
        lines.append(f"Win rate:              {pm.get('win_rate', 0):.1f}%")
        lines.append(f"Profit factor:         {pm.get('profit_factor', 0):.2f}")

    if eval_result:
        ps = eval_result.get("portfolio_result_summary", {})
        if ps:
            lines.append(f"Max concurrent:        {ps.get('max_positions_open', '-')}")
            lines.append(f"Final equity:          ${ps.get('equity', 0):,.0f}")

    if params:
        lines.append("")
        lines.append("[bold]Stage 2 Params:[/bold]")
        lines.append(f"  max_concurrent:      {params.get('max_concurrent', '-')}")
        lines.append(f"  cluster_max:         {params.get('cluster_max', '-')}")
        lines.append(f"  portfolio_heat:      {params.get('portfolio_heat', 0):.3f}")
        lines.append(f"  corr_gate_threshold: {params.get('corr_gate_threshold', 0):.3f}")

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


def print_report(
    analysis: dict[str, Any],
    pipeline_result: dict[str, Any] | None = None,
    eval_result: dict[str, Any] | None = None,
) -> None:
    """Print full analysis report to console using Rich."""
    per_pair = analysis.get("per_pair", [])
    portfolio = analysis.get("portfolio", {})
    tag = (pipeline_result or {}).get("tag", "")

    console.print()
    title = f"[bold cyan]MQE Run Report[/bold cyan]"
    if tag:
        title += f" [dim]({tag})[/dim]"
    console.rule(title)
    console.print()

    if per_pair:
        table = render_pair_table(per_pair)
        console.print(table)
        console.print()

    if pipeline_result:
        stage1 = pipeline_result.get("stage1_results", {})
        if stage1:
            params_table = render_params_table(stage1)
            console.print(params_table)
            console.print()

    panel = render_portfolio_panel(portfolio, eval_result)
    console.print(panel)
    console.print()


# ─── MARKDOWN REPORT ────────────────────────────────────────────────────────


def generate_markdown_report(
    pipeline_result: dict[str, Any],
    eval_result: dict[str, Any],
    analysis: dict[str, Any],
) -> str:
    """Generate Markdown report string."""
    lines: list[str] = []
    tag = pipeline_result.get("tag", "")
    timestamp = pipeline_result.get("timestamp", "")
    symbols = pipeline_result.get("symbols", [])
    s1_trials = pipeline_result.get("stage1_trials", 0)
    s2_trials = pipeline_result.get("stage2_trials", 0)
    hours = pipeline_result.get("hours", 0)

    # ── Header ──
    title = f"MQE Run Report"
    if tag:
        title += f" — {tag}"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- **Date:** {timestamp}")
    lines.append(f"- **Symbols:** {', '.join(symbols)}")
    lines.append(f"- **Data:** {hours}h ({hours/8760:.1f}yr)")
    lines.append(f"- **S1 trials:** {s1_trials} per pair | **S2 trials:** {s2_trials}")
    lines.append("")

    # ── Per-pair summary ──
    per_pair = analysis.get("per_pair", [])
    lines.append("## Stage 1 — Per-pair Results")
    lines.append("")
    lines.append("| Symbol | Verdict | Trades/yr | Sharpe | Calmar | Max DD | PnL% | Win Rate | PF |")
    lines.append("|--------|---------|-----------|--------|--------|--------|------|----------|-----|")

    for pair in per_pair:
        s = pair.get("metrics_summary", {})
        lines.append(
            f"| {pair.get('symbol', '?')} "
            f"| {pair.get('verdict', '?')} "
            f"| {s.get('trades_per_year', 0):.0f} "
            f"| {s.get('sharpe', 0):.2f} "
            f"| {s.get('calmar', 0):.2f} "
            f"| {abs(s.get('max_dd', 0)):.1f}% "
            f"| {s.get('total_pnl_pct', 0):.1f}% "
            f"| {s.get('win_rate', 0):.1f}% "
            f"| {s.get('profit_factor', 0):.2f} |"
        )
    lines.append("")

    # ── Per-pair params ──
    stage1 = pipeline_result.get("stage1_results", {})
    if stage1:
        lines.append("### Parameters")
        lines.append("")
        header = "| Param |"
        sep = "|-------|"
        for sym in stage1:
            short = sym.split("/")[0]
            header += f" {short} |"
            sep += "------|"
        lines.append(header)
        lines.append(sep)

        for key in _S1_PARAM_KEYS:
            row = f"| `{key}` |"
            for sym in stage1:
                val = stage1[sym].get(key, "-")
                if isinstance(val, float):
                    row += f" {val:.3f} |" if val < 10 else f" {val:.1f} |"
                else:
                    row += f" {val} |"
            lines.append(row)
        lines.append("")

    # ── Issues ──
    has_issues = False
    for pair in per_pair:
        issues = pair.get("failures", []) + pair.get("warnings", [])
        if issues:
            if not has_issues:
                lines.append("### Issues")
                lines.append("")
                has_issues = True
            for issue in issues:
                lines.append(f"- **{pair.get('symbol', '?')}:** {issue}")
    if has_issues:
        lines.append("")

    # ── Portfolio summary ──
    portfolio = analysis.get("portfolio", {})
    s2 = pipeline_result.get("stage2_results", {})
    pm = portfolio.get("portfolio_metrics", {})
    ps = (eval_result or {}).get("portfolio_result_summary", {})

    lines.append("## Stage 2 — Portfolio")
    lines.append("")

    s2_params = s2.get("portfolio_params", {})
    objectives = s2.get("objectives", {})
    lines.append("### Objectives")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Portfolio Calmar | {objectives.get('portfolio_calmar', 0):.2f} |")
    lines.append(f"| Worst-pair Calmar | {objectives.get('worst_pair_calmar', 0):.2f} |")
    lines.append(f"| Overfit penalty | {objectives.get('neg_overfit_penalty', 0):.2f} |")
    if ps:
        lines.append(f"| Final equity | ${ps.get('equity', 0):,.0f} |")
        lines.append(f"| Max DD (portfolio) | {ps.get('max_drawdown', 0)*100:.1f}% |")
        lines.append(f"| Total trades | {ps.get('total_trades', 0)} |")
        lines.append(f"| Max concurrent | {ps.get('max_positions_open', 0)} |")
    lines.append("")

    if pm:
        lines.append("### Portfolio Metrics")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Sharpe | {pm.get('sharpe', 0):.2f} |")
        lines.append(f"| Sortino | {pm.get('sortino', 0):.2f} |")
        lines.append(f"| Win rate | {pm.get('win_rate', 0):.1f}% |")
        lines.append(f"| Profit factor | {pm.get('profit_factor', 0):.2f} |")
        lines.append(f"| Expectancy | ${pm.get('expectancy', 0):.2f} |")
        lines.append(f"| PnL | {pm.get('total_pnl_pct', 0):.1f}% |")
        lines.append("")

    lines.append("### Parameters")
    lines.append("")
    lines.append("| Param | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| `max_concurrent` | {s2_params.get('max_concurrent', '-')} |")
    lines.append(f"| `cluster_max` | {s2_params.get('cluster_max', '-')} |")
    lines.append(f"| `portfolio_heat` | {s2_params.get('portfolio_heat', 0):.3f} |")
    lines.append(f"| `corr_gate_threshold` | {s2_params.get('corr_gate_threshold', 0):.3f} |")
    lines.append("")

    # ── Portfolio verdict ──
    pv = portfolio.get("verdict", "?")
    lines.append(f"### Verdict: **{pv}**")
    lines.append("")
    p_failures = portfolio.get("failures", [])
    p_warnings = portfolio.get("warnings", [])
    if p_failures:
        for f in p_failures:
            lines.append(f"- FAIL: {f}")
    if p_warnings:
        for w in p_warnings:
            lines.append(f"- WARN: {w}")
    if not p_failures and not p_warnings:
        lines.append("No issues detected.")
    lines.append("")

    return "\n".join(lines)


def save_markdown_report(
    path: Path,
    pipeline_result: dict[str, Any],
    eval_result: dict[str, Any],
    analysis: dict[str, Any],
) -> None:
    """Generate and save Markdown report to file."""
    md = generate_markdown_report(pipeline_result, eval_result, analysis)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(md, encoding="utf-8")
    logger.info("Report saved to %s", path)


# ─── DISCORD ────────────────────────────────────────────────────────────────


def format_discord_summary(analysis: dict[str, Any]) -> str:
    """Format analysis as compact Discord code block."""
    lines: list[str] = []
    lines.append("```")
    lines.append("MQE RUN ANALYSIS")
    lines.append("=" * 30)

    per_pair = analysis.get("per_pair", [])
    portfolio = analysis.get("portfolio", {})

    for pair in per_pair:
        symbol = pair.get("symbol", "?")
        verdict = pair.get("verdict", "?")
        s = pair.get("metrics_summary", {})
        sharpe = s.get("sharpe", 0)
        calmar = s.get("calmar", 0)
        tag = "[ok]" if verdict == "PASS" else "[!!]" if verdict == "WARN" else "[XX]"
        lines.append(f"  {tag} {symbol:<12} Sharpe={sharpe:.2f} Calmar={calmar:.2f}")

    lines.append("-" * 30)

    pv = portfolio.get("verdict", "?")
    pcalmar = portfolio.get("portfolio_calmar", 0)
    lines.append(f"PORTFOLIO:  {pv}  (Calmar={pcalmar:.2f})")

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
    if len(result) > 1900:
        result = result[:1890] + "\n```"

    return result
