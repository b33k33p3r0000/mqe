from __future__ import annotations

import json
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
    summary = eval_result.get("portfolio_result_summary", {})
    metrics = eval_result.get("portfolio_metrics", {})

    equity = summary.get("equity", 0.0)
    total_pnl_pct = metrics.get("total_pnl_pct", 0.0)
    calmar = metrics.get("calmar_ratio", 0.0)
    sharpe = metrics.get("sharpe_ratio_equity_based", 0.0)
    max_dd = summary.get("max_drawdown", 0.0)
    total_trades = summary.get("total_trades", 0)

    # Format values
    equity_str = f"${equity:,.2f}"
    pnl_str = f"{total_pnl_pct:+.1f}%"
    calmar_str = f"{calmar:.2f}"
    sharpe_str = f"{sharpe:.2f}"
    dd_display = abs(max_dd) * 100
    dd_str = f"-{dd_display:.1f}%"
    trades_str = str(total_trades)

    # Color classes
    pnl_class = "positive" if total_pnl_pct >= 0 else "negative"
    if dd_display > 5:
        dd_class = "negative"
    elif dd_display > 3:
        dd_class = "warning"
    else:
        dd_class = ""

    cards = [
        ("Final Equity", equity_str, ""),
        ("Total PnL", pnl_str, pnl_class),
        ("Calmar Ratio", calmar_str, ""),
        ("Sharpe (equity)", sharpe_str, ""),
        ("Max Drawdown", dd_str, dd_class),
        ("Total Trades", trades_str, ""),
    ]

    html_cards = []
    for label, value, cls in cards:
        cls_attr = f' {cls}' if cls else ""
        html_cards.append(
            f'<div class="hero-card">'
            f'<div class="hero-label">{label}</div>'
            f'<div class="hero-value{cls_attr}">{value}</div>'
            f'</div>'
        )

    return f'<div class="hero-grid">{"".join(html_cards)}</div>'


def _render_portfolio_equity_curve(
    portfolio_equity_curve: List[float],
    timestamps: List[str],
) -> str:
    if not portfolio_equity_curve:
        return '<div class="no-data">No equity data available</div>'

    # Compute high-water mark and drawdown
    hwm = []
    drawdown = []
    running_max = float("-inf")
    for val in portfolio_equity_curve:
        running_max = max(running_max, val)
        hwm.append(running_max)
        drawdown.append(val - running_max)

    # Use timestamps if available, otherwise generate indices
    x_data = timestamps if timestamps else list(range(len(portfolio_equity_curve)))

    x_json = json.dumps(x_data)
    eq_json = json.dumps(portfolio_equity_curve)
    hwm_json = json.dumps(hwm)
    dd_json = json.dumps(drawdown)

    return f"""<div class="chart-container">
<div id="portfolio-equity-chart" style="width:100%;height:450px;"></div>
<script>
(function() {{
  var x = {x_json};
  var equity = {eq_json};
  var hwm = {hwm_json};
  var dd = {dd_json};
  var traces = [
    {{
      x: x, y: equity, type: 'scatter', mode: 'lines',
      name: 'Equity', line: {{color: '#86e1fc', width: 2}},
      fill: 'tozeroy', fillcolor: 'rgba(134,225,252,0.1)'
    }},
    {{
      x: x, y: hwm, type: 'scatter', mode: 'lines',
      name: 'High-Water Mark', line: {{color: '#ffffff', width: 1, dash: 'dot'}}
    }},
    {{
      x: x, y: dd, type: 'scatter', mode: 'lines',
      name: 'Drawdown', line: {{color: '#ff757f', width: 1}},
      fill: 'tozeroy', fillcolor: 'rgba(255,117,127,0.2)',
      yaxis: 'y2'
    }}
  ];
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'Portfolio Equity Curve', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 60, r: 40, t: 40, b: 40}},
    showlegend: true,
    legend: {{font: {{size: 10}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Equity ($)', gridcolor: '#3b4261', showgrid: true}},
    yaxis2: {{title: 'Drawdown ($)', overlaying: 'y', side: 'right', gridcolor: '#3b4261', showgrid: false}}
  }};
  Plotly.newPlot('portfolio-equity-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_concurrent_positions(
    portfolio_trades: List[Dict[str, Any]],
    timestamps: List[str],
) -> str:
    if not portfolio_trades:
        return '<div class="no-data">No trade data available</div>'

    # Collect all entry/exit events
    events: List[tuple] = []
    for trade in portfolio_trades:
        entry_ts = trade.get("entry_time") or trade.get("entry_timestamp")
        exit_ts = trade.get("exit_time") or trade.get("exit_timestamp")
        if entry_ts and exit_ts:
            events.append((entry_ts, 1))
            events.append((exit_ts, -1))

    if not events:
        return '<div class="no-data">No trade data available</div>'

    # Sort events by timestamp, exits before entries at same time
    events.sort(key=lambda e: (e[0], e[1]))

    # Compute concurrent count over time
    x_vals = []
    y_vals = []
    count = 0
    for ts, delta in events:
        count += delta
        x_vals.append(ts)
        y_vals.append(count)

    max_concurrent = max(y_vals) if y_vals else 0

    x_json = json.dumps(x_vals)
    y_json = json.dumps(y_vals)

    return f"""<div class="chart-container">
<div id="concurrent-positions-chart" style="width:100%;height:350px;"></div>
<script>
(function() {{
  var x = {x_json};
  var y = {y_json};
  var maxConc = {max_concurrent};
  var traces = [
    {{
      x: x, y: y, type: 'scatter', mode: 'lines',
      name: 'Concurrent Positions',
      line: {{color: '#c099ff', width: 2, shape: 'hv'}},
      fill: 'tozeroy', fillcolor: 'rgba(192,153,255,0.1)'
    }},
    {{
      x: [x[0], x[x.length - 1]], y: [maxConc, maxConc],
      type: 'scatter', mode: 'lines',
      name: 'Max Concurrent (' + maxConc + ')',
      line: {{color: '#ff966c', width: 1, dash: 'dash'}}
    }}
  ];
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'Concurrent Positions', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 50, r: 30, t: 40, b: 40}},
    showlegend: true,
    legend: {{font: {{size: 10}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Open Positions', gridcolor: '#3b4261', showgrid: true, dtick: 1}}
  }};
  Plotly.newPlot('concurrent-positions-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""


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
