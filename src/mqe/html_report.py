from __future__ import annotations

from typing import Any, Dict, List
import datetime

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.27.0.min.js"

CSS_THEME = """
:root {
    --bg-primary: #222436;
    --bg-deep: #1e2030;
    --bg-secondary: #2f334d;
    --text-primary: #c8d3f5;
    --text-secondary: #636da6;
    --text-muted: #3b4261;
    --accent-green: #c3e88d;
    --accent-red: #ff757f;
    --accent-purple: #c099ff;
    --accent-cyan: #86e1fc;
    --accent-teal: #4fd6be;
    --accent-yellow: #ffc777;
    --accent-orange: #ff966c;
    --accent-blue: #82aaff;
    --border: #545c7e;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    background: var(--bg-deep);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
    padding: 24px;
}

h1, h2, h3 {
    color: var(--text-primary);
    font-family: var(--font-mono);
}

/* Hero grid — 3 columns */
.hero-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 32px;
}

@media (max-width: 900px) {
    .hero-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 600px) {
    .hero-grid {
        grid-template-columns: 1fr;
    }
}

/* Cards */
.card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
}

.card-label {
    color: var(--text-secondary);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
}

.card-value {
    color: var(--text-primary);
    font-size: 20px;
    font-weight: 600;
}

/* Chart containers */
.chart-container {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 24px;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    background: var(--bg-secondary);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 24px;
}

th {
    background: var(--bg-deep);
    color: var(--text-secondary);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border);
}

td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--text-muted);
    color: var(--text-primary);
}

tr:last-child td {
    border-bottom: none;
}

tr:hover td {
    background: var(--bg-primary);
}

/* Section dividers with purple accent */
.section-divider {
    display: flex;
    align-items: center;
    gap: 16px;
    margin: 40px 0 24px 0;
}

.section-divider::before {
    content: '';
    width: 4px;
    height: 24px;
    background: var(--accent-purple);
    border-radius: 2px;
    flex-shrink: 0;
}

.section-divider h2 {
    color: var(--accent-purple);
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.04em;
}

.section-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* Verdict / tier color classes */
.verdict-pass, .tier-s {
    color: var(--accent-green);
}

.verdict-fail, .tier-d {
    color: var(--accent-red);
}

.verdict-warn, .tier-b {
    color: var(--accent-yellow);
}

.tier-a {
    color: var(--accent-cyan);
}

.tier-c {
    color: var(--accent-orange);
}

/* No-data placeholder */
.no-data {
    background: var(--bg-secondary);
    border: 1px dashed var(--border);
    border-radius: 8px;
    padding: 32px;
    text-align: center;
    color: var(--text-muted);
    margin-bottom: 24px;
    font-style: italic;
}

/* Report header */
.report-header {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}

.report-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--accent-purple);
}

.report-meta {
    color: var(--text-secondary);
    font-size: 11px;
}
"""


def _render_hero_metrics(
    pipeline_result: Dict[str, Any],
    eval_result: Dict[str, Any],
    analysis: Dict[str, Any],
) -> str:
    return '<div class="no-data">Hero Metrics placeholder</div>'


def _render_portfolio_equity_curve(
    portfolio_equity_curve: List[float],
    timestamps: List[str],
) -> str:
    return '<div class="no-data">Portfolio Equity Curve placeholder</div>'


def _render_concurrent_positions(
    portfolio_trades: List[Dict[str, Any]],
    timestamps: List[str],
) -> str:
    return '<div class="no-data">Concurrent Positions placeholder</div>'


def _render_per_pair_table(
    pipeline_result: Dict[str, Any],
    eval_result: Dict[str, Any],
) -> str:
    return '<div class="no-data">Per-Pair Table placeholder</div>'


def _render_per_pair_equity_curves(
    pair_equity_curves: Dict[str, List[float]],
    timestamps: List[str],
) -> str:
    return '<div class="no-data">Per-Pair Equity Curves placeholder</div>'


def _render_tier_table(analysis: Dict[str, Any]) -> str:
    return '<div class="no-data">Tier Table placeholder</div>'


def _render_wf_evaluation(eval_result: Dict[str, Any]) -> str:
    return '<div class="no-data">Walk-Forward Evaluation placeholder</div>'


def _render_s1_params_table(pipeline_result: Dict[str, Any]) -> str:
    return '<div class="no-data">S1 Params Table placeholder</div>'


def _render_s1_bullet_chart(pipeline_result: Dict[str, Any]) -> str:
    return '<div class="no-data">S1 Bullet Chart placeholder</div>'


def _render_s1_top_trials(s1_top_trials: Dict[str, Any]) -> str:
    return '<div class="no-data">S1 Top Trials placeholder</div>'


def _render_s1_optimization_history(s1_history: Dict[str, Any]) -> str:
    return '<div class="no-data">S1 Optimization History placeholder</div>'


def _render_s2_params(pareto_front: Dict[str, Any]) -> str:
    return '<div class="no-data">S2 Params placeholder</div>'


def _render_pareto_front(pareto_front: Dict[str, Any]) -> str:
    return '<div class="no-data">Pareto Front placeholder</div>'


def _render_s2_optimization_history(s2_history: Dict[str, Any]) -> str:
    return '<div class="no-data">S2 Optimization History placeholder</div>'


def _render_pnl_contribution(
    portfolio_trades: List[Dict[str, Any]],
    per_pair_trades: Dict[str, List[Dict[str, Any]]],
) -> str:
    return '<div class="no-data">PnL Contribution placeholder</div>'


def _render_correlation_heatmap(corr_matrix: Dict[str, Any]) -> str:
    return '<div class="no-data">Correlation Heatmap placeholder</div>'


def _render_monthly_returns(
    portfolio_trades: List[Dict[str, Any]],
    timestamps: List[str],
) -> str:
    return '<div class="no-data">Monthly Returns placeholder</div>'


def _render_trade_analysis(
    portfolio_trades: List[Dict[str, Any]],
    per_pair_trades: Dict[str, List[Dict[str, Any]]],
) -> str:
    return '<div class="no-data">Trade Analysis placeholder</div>'


def generate_html_report(
    pipeline_result: Dict[str, Any],
    eval_result: Dict[str, Any],
    analysis: Dict[str, Any],
    portfolio_trades: List[Dict[str, Any]],
    per_pair_trades: Dict[str, List[Dict[str, Any]]],
    s1_top_trials: Dict[str, Any],
    s1_history: Dict[str, Any],
    pareto_front: Dict[str, Any],
    s2_history: Dict[str, Any],
    corr_matrix: Dict[str, Any],
    pair_equity_curves: Dict[str, List[float]],
    portfolio_equity_curve: List[float],
    timestamps: List[str],
) -> str:
    # Extract header data
    run_tag = pipeline_result.get("run_tag", "unknown")
    timestamp = pipeline_result.get("timestamp", datetime.datetime.utcnow().isoformat())
    symbols = pipeline_result.get("symbols", [])
    symbols_str = ", ".join(symbols) if symbols else "—"
    s1_trials = pipeline_result.get("s1_trials", "—")
    s2_trials = pipeline_result.get("s2_trials", "—")
    hours = pipeline_result.get("duration_hours", "—")

    # Render all sections
    hero = _render_hero_metrics(pipeline_result, eval_result, analysis)
    portfolio_eq = _render_portfolio_equity_curve(portfolio_equity_curve, timestamps)
    concurrent = _render_concurrent_positions(portfolio_trades, timestamps)
    per_pair_tbl = _render_per_pair_table(pipeline_result, eval_result)
    per_pair_eq = _render_per_pair_equity_curves(pair_equity_curves, timestamps)
    tier_tbl = _render_tier_table(analysis)
    wf_eval = _render_wf_evaluation(eval_result)
    s1_params = _render_s1_params_table(pipeline_result)
    s1_bullet = _render_s1_bullet_chart(pipeline_result)
    s1_top = _render_s1_top_trials(s1_top_trials)
    s1_hist = _render_s1_optimization_history(s1_history)
    s2_params = _render_s2_params(pareto_front)
    pareto = _render_pareto_front(pareto_front)
    s2_hist = _render_s2_optimization_history(s2_history)
    pnl_contrib = _render_pnl_contribution(portfolio_trades, per_pair_trades)
    corr_heat = _render_correlation_heatmap(corr_matrix)
    monthly = _render_monthly_returns(portfolio_trades, timestamps)
    trade_analysis = _render_trade_analysis(portfolio_trades, per_pair_trades)

    header_html = f"""
    <div class="report-header">
        <div>
            <div class="report-title">MQE Optimization Report</div>
            <div class="report-meta">Run: {run_tag} &nbsp;|&nbsp; {timestamp}</div>
        </div>
        <div class="report-meta" style="text-align:right;">
            Symbols: {symbols_str}<br>
            S1 trials: {s1_trials} &nbsp;|&nbsp; S2 trials: {s2_trials}<br>
            Duration: {hours}h
        </div>
    </div>
    """

    divider_s1 = '<div class="section-divider"><h2>Stage 1 — Per-Pair</h2></div>'
    divider_s2 = '<div class="section-divider"><h2>Stage 2 — Portfolio</h2></div>'
    divider_trades = '<div class="section-divider"><h2>Trade Analysis</h2></div>'

    body = f"""
{header_html}
{hero}
{portfolio_eq}
{concurrent}
{per_pair_tbl}
{per_pair_eq}
{tier_tbl}
{wf_eval}
{divider_s1}
{s1_params}
{s1_bullet}
{s1_top}
{s1_hist}
{divider_s2}
{s2_params}
{pareto}
{s2_hist}
{pnl_contrib}
{corr_heat}
{monthly}
{divider_trades}
{trade_analysis}
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MQE Report — {run_tag}</title>
<script src="{PLOTLY_CDN}"></script>
<style>
{CSS_THEME}
</style>
</head>
<body>
{body}
</body>
</html>"""

    return html


def save_html_report(path: str, **kwargs: Any) -> None:
    """Generate and write HTML report to the given file path."""
    html = generate_html_report(**kwargs)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
