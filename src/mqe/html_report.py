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

/* Grid layouts */
.grid-3col {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

@media (max-width: 900px) {
    .grid-3col {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 600px) {
    .grid-3col {
        grid-template-columns: 1fr;
    }
}

/* Pill badges */
.pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    margin: 4px 4px 4px 0;
}

.pill-green {
    background: rgba(195, 232, 141, 0.15);
    color: var(--accent-green);
}

.pill-yellow {
    background: rgba(255, 199, 119, 0.15);
    color: var(--accent-yellow);
}

.pill-red {
    background: rgba(255, 117, 127, 0.15);
    color: var(--accent-red);
}

/* Tier-X class */
.tier-x {
    color: var(--accent-red);
}

/* WF metric cards */
.wf-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
}

.wf-card h3 {
    color: var(--accent-cyan);
    font-size: 14px;
    margin-bottom: 12px;
}

.wf-metric-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid var(--text-muted);
}

.wf-metric-row:last-child {
    border-bottom: none;
}

.wf-metric-label {
    color: var(--text-secondary);
    font-size: 11px;
}

.wf-metric-value {
    color: var(--text-primary);
    font-weight: 600;
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


def _build_equity_curve_from_trades(
    trades: list,
    start_equity: float = 100_000.0,
) -> list:
    """Build equity curve from trade list."""
    if not trades:
        return []
    equity = start_equity
    curve = [equity]
    for t in sorted(trades, key=lambda x: x.get("exit_bar", 0)):
        equity += t.get("pnl_abs", 0)
        curve.append(equity)
    return curve


def _render_per_pair_table(
    pipeline_result: Dict[str, Any],
    eval_result: Dict[str, Any],
) -> str:
    per_pair = eval_result.get("per_pair_metrics", {})
    if not per_pair:
        return '<div class="no-data">No per-pair data available</div>'

    tiers = pipeline_result.get("tier_assignments", {})
    # Build verdict lookup from analysis if available
    analysis = pipeline_result.get("analysis", {})
    verdict_list = analysis.get("per_pair", []) if isinstance(analysis, dict) else []
    verdict_map: Dict[str, str] = {}
    if isinstance(verdict_list, list):
        for entry in verdict_list:
            if isinstance(entry, dict):
                verdict_map[entry.get("symbol", "")] = entry.get("verdict", "—")

    headers = ["Symbol", "Tier", "Verdict", "Trades/yr", "Sharpe", "Calmar", "Max DD%", "PnL%", "Win Rate", "PF"]
    header_row = "".join(f"<th>{h}</th>" for h in headers)

    rows = []
    for symbol in sorted(per_pair.keys()):
        m = per_pair[symbol]
        tier_info = tiers.get(symbol, {})
        tier = tier_info.get("tier", "—") if isinstance(tier_info, dict) else str(tier_info)
        tier_cls = f"tier-{tier.lower()}" if tier in ("A", "B", "C", "S", "X") else ""

        verdict = verdict_map.get(symbol, "—")
        verdict_lower = verdict.lower()
        if verdict_lower == "pass":
            verdict_cls = "verdict-pass"
        elif verdict_lower == "warn":
            verdict_cls = "verdict-warn"
        elif verdict_lower == "fail":
            verdict_cls = "verdict-fail"
        else:
            verdict_cls = ""

        trades_yr = m.get("trades_per_year", 0)
        sharpe = m.get("sharpe_ratio_equity_based", 0)
        calmar = m.get("calmar_ratio", 0)
        max_dd = abs(m.get("max_drawdown", 0)) * 100
        pnl_pct = m.get("total_pnl_pct", 0)
        win_rate = m.get("win_rate", 0) * 100
        pf = m.get("profit_factor", 0)

        row = (
            f"<tr>"
            f"<td>{symbol}</td>"
            f'<td class="{tier_cls}">{tier}</td>'
            f'<td class="{verdict_cls}">{verdict}</td>'
            f"<td>{trades_yr:.0f}</td>"
            f"<td>{sharpe:.2f}</td>"
            f"<td>{calmar:.2f}</td>"
            f"<td>-{max_dd:.1f}%</td>"
            f"<td>{pnl_pct:+.1f}%</td>"
            f"<td>{win_rate:.1f}%</td>"
            f"<td>{pf:.2f}</td>"
            f"</tr>"
        )
        rows.append(row)

    return f'<table><thead><tr>{header_row}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _render_per_pair_equity_curves(
    pair_equity_curves: Dict[str, List[float]],
    timestamps: List[str],
) -> str:
    if not pair_equity_curves:
        return '<div class="no-data">No per-pair equity data available</div>'

    charts = []
    for symbol in sorted(pair_equity_curves.keys()):
        curve = pair_equity_curves[symbol]
        if not curve:
            continue

        safe_id = symbol.replace("/", "").replace(" ", "")
        div_id = f"pair-equity-{safe_id}"
        x_data = timestamps[:len(curve)] if timestamps else list(range(len(curve)))

        # Determine trade markers if curve was built from trades
        # Curve values: compute per-bar PnL for coloring
        win_x = []
        win_y = []
        loss_x = []
        loss_y = []
        for i in range(1, len(curve)):
            pnl = curve[i] - curve[i - 1]
            if pnl > 0:
                win_x.append(x_data[i] if i < len(x_data) else i)
                win_y.append(curve[i])
            elif pnl < 0:
                loss_x.append(x_data[i] if i < len(x_data) else i)
                loss_y.append(curve[i])

        x_json = json.dumps(x_data)
        eq_json = json.dumps(curve)
        win_x_json = json.dumps(win_x)
        win_y_json = json.dumps(win_y)
        loss_x_json = json.dumps(loss_x)
        loss_y_json = json.dumps(loss_y)

        chart_html = f"""<div class="chart-container">
<div id="{div_id}" style="width:100%;height:280px;"></div>
<script>
(function() {{
  var traces = [
    {{
      x: {x_json}, y: {eq_json}, type: 'scatter', mode: 'lines',
      name: 'Equity', line: {{color: '#86e1fc', width: 1.5}}
    }},
    {{
      x: {win_x_json}, y: {win_y_json}, type: 'scatter', mode: 'markers',
      name: 'Win', marker: {{color: '#c3e88d', size: 4}}
    }},
    {{
      x: {loss_x_json}, y: {loss_y_json}, type: 'scatter', mode: 'markers',
      name: 'Loss', marker: {{color: '#ff757f', size: 4}}
    }}
  ];
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 10}},
    title: {{text: '{symbol}', font: {{size: 12, color: '#c099ff'}}}},
    margin: {{l: 50, r: 20, t: 30, b: 30}},
    showlegend: false,
    xaxis: {{gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{gridcolor: '#3b4261', showgrid: true}}
  }};
  Plotly.newPlot('{div_id}', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""
        charts.append(chart_html)

    if not charts:
        return '<div class="no-data">No per-pair equity data available</div>'

    return f'<div class="grid-3col">{"".join(charts)}</div>'


def _render_tier_table(analysis: Dict[str, Any]) -> str:
    tier_data = analysis.get("tier_assignments", {})
    if not tier_data:
        return '<div class="no-data">No tier assignment data available</div>'

    headers = ["Symbol", "Tier", "Multiplier", "OOS Sharpe", "Degradation", "Consistency", "Worst Sharpe"]
    header_row = "".join(f"<th>{h}</th>" for h in headers)

    rows = []
    for symbol in sorted(tier_data.keys()):
        t = tier_data[symbol]
        tier = t.get("tier", "—")
        tier_cls = f"tier-{tier.lower()}" if tier in ("A", "B", "C", "S", "X") else ""
        multiplier = t.get("multiplier", 0)
        sharpe = t.get("sharpe", 0)
        degradation = t.get("degradation", 0)
        consistency = t.get("consistency", 0)
        worst = t.get("worst_sharpe", 0)

        row = (
            f"<tr>"
            f"<td>{symbol}</td>"
            f'<td class="{tier_cls}">{tier}</td>'
            f"<td>{multiplier:.2f}</td>"
            f"<td>{sharpe:.2f}</td>"
            f"<td>{degradation:.2f}</td>"
            f"<td>{consistency:.2f}</td>"
            f"<td>{worst:.2f}</td>"
            f"</tr>"
        )
        rows.append(row)

    return f'<table><thead><tr>{header_row}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _render_wf_evaluation(eval_result: Dict[str, Any]) -> str:
    wf_metrics = eval_result.get("wf_eval_metrics", {})
    if not wf_metrics:
        return '<div class="no-data">No walk-forward evaluation data available</div>'

    cards = []
    for symbol in sorted(wf_metrics.keys()):
        m = wf_metrics[symbol]
        median_sharpe = m.get("wf_sharpe_median", 0)
        std_sharpe = m.get("wf_sharpe_std", 0)
        worst_sharpe = m.get("wf_worst_sharpe", 0)
        degradation = m.get("degradation_ratio", 0)
        n_windows = m.get("n_windows", 0)

        # Color degradation: < 0.5 = green, 0.5-0.8 = yellow, > 0.8 = red
        if degradation < 0.5:
            deg_cls = "verdict-pass"
        elif degradation < 0.8:
            deg_cls = "verdict-warn"
        else:
            deg_cls = "verdict-fail"

        card = f"""<div class="wf-card">
<h3>{symbol}</h3>
<div class="wf-metric-row"><span class="wf-metric-label">Sharpe (median)</span><span class="wf-metric-value">{median_sharpe:.2f}</span></div>
<div class="wf-metric-row"><span class="wf-metric-label">Sharpe (std)</span><span class="wf-metric-value">{std_sharpe:.2f}</span></div>
<div class="wf-metric-row"><span class="wf-metric-label">Worst Sharpe</span><span class="wf-metric-value">{worst_sharpe:.2f}</span></div>
<div class="wf-metric-row"><span class="wf-metric-label">Degradation</span><span class="wf-metric-value {deg_cls}">{degradation:.2f}</span></div>
<div class="wf-metric-row"><span class="wf-metric-label">Windows</span><span class="wf-metric-value">{n_windows}</span></div>
</div>"""
        cards.append(card)

    return f'<div class="grid-3col">{"".join(cards)}</div>'


def _render_s1_params_table(pipeline_result: Dict[str, Any]) -> str:
    s1_results = pipeline_result.get("stage1_results", {})
    if not s1_results:
        return '<div class="no-data">No S1 parameters available</div>'

    param_names = [
        "macd_fast", "macd_slow", "macd_signal",
        "rsi_period", "rsi_lower", "rsi_upper", "rsi_lookback",
        "trend_tf", "adx_threshold", "trail_mult", "hard_stop_mult", "max_hold_bars",
    ]
    symbols = sorted(s1_results.keys())

    # Table header
    header_row = "<th>Parameter</th>" + "".join(f"<th>{s}</th>" for s in symbols)

    # Table rows
    rows = []
    for param in param_names:
        cells = f"<td>{param}</td>"
        for sym in symbols:
            val = s1_results[sym].get(param, "—")
            if isinstance(val, float):
                cells += f"<td>{val:.4g}</td>"
            else:
                cells += f"<td>{val}</td>"
        rows.append(f"<tr>{cells}</tr>")

    table = f'<table><thead><tr>{header_row}</tr></thead><tbody>{"".join(rows)}</tbody></table>'

    # Fixed params as pill badges
    fixed_params = ["allow_flip", "trend_strict"]
    pills = []
    for fp in fixed_params:
        # Try to get from first symbol
        for sym in symbols:
            val = s1_results[sym].get(fp)
            if val is not None:
                pills.append(f'<span class="pill pill-green">{fp}: {val}</span>')
                break
        else:
            pills.append(f'<span class="pill pill-yellow">{fp}: —</span>')

    pill_html = f'<div style="margin-bottom:24px;">{"".join(pills)}</div>' if pills else ""

    return table + pill_html


PARAM_RANGES = {
    "macd_fast": (1.0, 20.0),
    "macd_slow": (10, 45),
    "macd_signal": (3, 15),
    "rsi_period": (3, 30),
    "rsi_lower": (20, 40),
    "rsi_upper": (60, 80),
    "rsi_lookback": (1, 4),
    "trend_tf": (0, 3),
    "adx_threshold": (15, 35),
    "trail_mult": (1.0, 5.0),
    "hard_stop_mult": (1.0, 5.0),
    "max_hold_bars": (24, 168),
}

S2_RANGES = {
    "max_concurrent": (3, 10),
    "cluster_max": (1, 4),
    "portfolio_heat": (0.03, 0.10),
    "corr_gate_threshold": (0.50, 0.80),
}

_PAIR_COLORS = [
    "#86e1fc", "#c3e88d", "#ff757f", "#ffc777", "#c099ff", "#4fd6be",
]


def _render_s1_bullet_chart(pipeline_result: Dict[str, Any]) -> str:
    s1_results = pipeline_result.get("stage1_results", {})
    if not s1_results:
        return '<div class="no-data">No S1 data for bullet chart</div>'

    symbols = sorted(s1_results.keys())
    param_names = list(PARAM_RANGES.keys())

    traces = []
    # Background range bars (one per param)
    range_y = []
    range_base = []
    range_width = []
    for pname in param_names:
        lo, hi = PARAM_RANGES[pname]
        range_y.append(pname)
        range_base.append(lo)
        range_width.append(hi - lo)

    traces.append({
        "type": "bar",
        "orientation": "h",
        "y": range_y,
        "x": range_width,
        "base": range_base,
        "name": "Search Range",
        "marker": {"color": "rgba(59,66,97,0.6)"},
        "hoverinfo": "skip",
        "showlegend": True,
    })

    # Marker per symbol
    for idx, sym in enumerate(symbols):
        color = _PAIR_COLORS[idx % len(_PAIR_COLORS)]
        params = s1_results[sym]
        marker_y = []
        marker_x = []
        for pname in param_names:
            val = params.get(pname)
            if val is not None:
                try:
                    marker_x.append(float(val))
                    marker_y.append(pname)
                except (TypeError, ValueError):
                    pass
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "y": marker_y,
            "x": marker_x,
            "name": sym,
            "marker": {"color": color, "size": 12, "symbol": "diamond"},
        })

    traces_json = json.dumps(traces)

    return f"""<div class="chart-container">
<div id="s1-bullet-chart" style="width:100%;height:{max(400, len(param_names) * 35)}px;"></div>
<script>
(function() {{
  var traces = {traces_json};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'S1 Strategy Parameters — Bullet Chart', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 130, r: 30, t: 40, b: 40}},
    barmode: 'overlay',
    showlegend: true,
    legend: {{font: {{size: 10}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{gridcolor: '#3b4261', showgrid: false, autorange: 'reversed'}}
  }};
  Plotly.newPlot('s1-bullet-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_s1_top_trials(s1_top_trials: Dict[str, Any]) -> str:
    if not s1_top_trials:
        return '<div class="no-data">No S1 top trials data available</div>'

    sections = []
    for sym in sorted(s1_top_trials.keys()):
        sym_data = s1_top_trials[sym]
        trials = sym_data.get("trials", [])
        n_total = sym_data.get("n_trials_total", 0)
        if not trials:
            continue

        safe_id = sym.replace("/", "").replace(" ", "")

        # ── Top-20 Table ──
        headers = ["Rank", "Objective", "Sharpe", "Max DD", "PnL%", "Trades/yr"]
        header_row = "".join(f"<th>{h}</th>" for h in headers)
        rows = []
        for i, t in enumerate(trials[:20]):
            m = t.get("metrics", {})
            rows.append(
                f"<tr>"
                f"<td>{i + 1}</td>"
                f"<td>{t.get('objective', 0):.4f}</td>"
                f"<td>{m.get('sharpe_ratio_equity_based', m.get('sharpe', 0)):.2f}</td>"
                f"<td>{abs(m.get('max_drawdown', 0)) * 100:.1f}%</td>"
                f"<td>{m.get('total_pnl_pct', m.get('pnl_pct', 0)):.1f}%</td>"
                f"<td>{m.get('trades_per_year', 0):.0f}</td>"
                f"</tr>"
            )
        table_html = (
            f'<h3 style="color:#c099ff;margin:16px 0 8px 0;">{sym} — Top {len(trials[:20])} of {n_total} trials</h3>'
            f'<table><thead><tr>{header_row}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

        # ── Parallel Coordinates Chart ──
        # Build dimensions from params of top trials
        param_keys = []
        if trials:
            param_keys = sorted(trials[0].get("params", {}).keys())

        dimensions = []
        for pk in param_keys:
            vals = [t.get("params", {}).get(pk, 0) for t in trials]
            dimensions.append({
                "label": pk,
                "values": vals,
            })

        obj_vals = [t.get("objective", 0) for t in trials]
        parcoords_trace = {
            "type": "parcoords",
            "line": {
                "color": obj_vals,
                "colorscale": "Viridis",
                "showscale": True,
                "cmin": min(obj_vals) if obj_vals else 0,
                "cmax": max(obj_vals) if obj_vals else 1,
            },
            "dimensions": dimensions,
        }
        parcoords_json = json.dumps([parcoords_trace])
        parcoords_div = f"s1-parcoords-{safe_id}"

        parcoords_html = f"""<div class="chart-container">
<div id="{parcoords_div}" style="width:100%;height:400px;"></div>
<script>
(function() {{
  var traces = {parcoords_json};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 10}},
    title: {{text: '{sym} — Parallel Coordinates', font: {{size: 13, color: '#c099ff'}}}},
    margin: {{l: 60, r: 60, t: 40, b: 30}}
  }};
  Plotly.newPlot('{parcoords_div}', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""

        # ── Scatter: Sharpe vs Max DD ──
        scatter_sharpe = [
            t.get("metrics", {}).get("sharpe_ratio_equity_based", t.get("metrics", {}).get("sharpe", 0))
            for t in trials
        ]
        scatter_dd = [
            abs(t.get("metrics", {}).get("max_drawdown", 0)) * 100
            for t in trials
        ]
        scatter_obj = [t.get("objective", 0) for t in trials]

        scatter_trace = {
            "type": "scatter",
            "mode": "markers",
            "x": scatter_sharpe,
            "y": scatter_dd,
            "marker": {
                "color": scatter_obj,
                "colorscale": "Viridis",
                "showscale": True,
                "size": 8,
                "cmin": min(scatter_obj) if scatter_obj else 0,
                "cmax": max(scatter_obj) if scatter_obj else 1,
            },
            "text": [f"Trial {t.get('number', '?')}" for t in trials],
            "hovertemplate": "Sharpe: %{x:.2f}<br>Max DD: %{y:.1f}%<br>%{text}<extra></extra>",
        }
        scatter_json = json.dumps([scatter_trace])
        scatter_div = f"s1-scatter-{safe_id}"

        scatter_html = f"""<div class="chart-container">
<div id="{scatter_div}" style="width:100%;height:350px;"></div>
<script>
(function() {{
  var traces = {scatter_json};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: '{sym} — Sharpe vs Max DD', font: {{size: 13, color: '#c099ff'}}}},
    margin: {{l: 60, r: 30, t: 40, b: 50}},
    xaxis: {{title: 'Sharpe Ratio', gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Max DD (%)', gridcolor: '#3b4261', showgrid: true}}
  }};
  Plotly.newPlot('{scatter_div}', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""

        sections.append(table_html + parcoords_html + scatter_html)

    if not sections:
        return '<div class="no-data">No S1 top trials data available</div>'

    return "".join(sections)


def _render_s1_optimization_history(s1_history: Dict[str, Any]) -> str:
    if not s1_history:
        return '<div class="no-data">No S1 optimization history available</div>'

    charts = []
    for sym in sorted(s1_history.keys()):
        data = s1_history[sym]
        trial_nums = data.get("trial_numbers", [])
        obj_vals = data.get("objective_values", [])
        best_so_far = data.get("best_so_far", [])

        if not trial_nums:
            continue

        safe_id = sym.replace("/", "").replace(" ", "")
        div_id = f"s1-history-{safe_id}"

        traces = [
            {
                "type": "scatter",
                "mode": "markers",
                "x": trial_nums,
                "y": obj_vals,
                "name": "Objective",
                "marker": {"color": "#86e1fc", "size": 3, "opacity": 0.5},
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": trial_nums,
                "y": best_so_far,
                "name": "Best so far",
                "line": {"color": "#c3e88d", "width": 2},
            },
        ]

        # Highlight best trial
        if obj_vals:
            best_idx = obj_vals.index(max(obj_vals))
            traces.append({
                "type": "scatter",
                "mode": "markers",
                "x": [trial_nums[best_idx]],
                "y": [obj_vals[best_idx]],
                "name": "Best trial",
                "marker": {"color": "#ffc777", "size": 12, "symbol": "star"},
                "showlegend": True,
            })

        traces_json = json.dumps(traces)

        chart_html = f"""<div class="chart-container">
<div id="{div_id}" style="width:100%;height:300px;"></div>
<script>
(function() {{
  var traces = {traces_json};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 10}},
    title: {{text: '{sym} — Optimization History', font: {{size: 12, color: '#c099ff'}}}},
    margin: {{l: 50, r: 20, t: 35, b: 35}},
    showlegend: true,
    legend: {{font: {{size: 9}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{title: 'Trial', gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Objective', gridcolor: '#3b4261', showgrid: true}}
  }};
  Plotly.newPlot('{div_id}', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""
        charts.append(chart_html)

    if not charts:
        return '<div class="no-data">No S1 optimization history available</div>'

    return f'<div class="grid-2col" style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;">{"".join(charts)}</div>'


def _render_s2_params(pareto_front: Dict[str, Any]) -> str:
    # Extract portfolio params from the selected trial in pareto_front,
    # or from a top-level portfolio_params key
    portfolio_params = pareto_front.get("portfolio_params", {})
    if not portfolio_params:
        # Try to get from selected trial
        selected = pareto_front.get("selected_trial")
        trials = pareto_front.get("trials", [])
        for t in trials:
            if t.get("number") == selected:
                portfolio_params = t.get("params", {})
                break
    if not portfolio_params:
        return '<div class="no-data">No S2 portfolio parameters available</div>'

    rows_html = []
    for param_name, (lo, hi) in S2_RANGES.items():
        val = portfolio_params.get(param_name)
        if val is None:
            val_str = "—"
        elif isinstance(val, float):
            val_str = f"{val:.4g}"
        else:
            val_str = str(val)
        rows_html.append(
            f'<div class="wf-metric-row">'
            f'<span class="wf-metric-label">{param_name}</span>'
            f'<span class="wf-metric-value">{val_str} <span style="color:var(--text-muted);font-size:10px;">[{lo} — {hi}]</span></span>'
            f'</div>'
        )

    return (
        f'<div class="card" style="max-width:500px;margin-bottom:24px;">'
        f'<h3 style="color:#c099ff;margin-bottom:12px;">S2 Portfolio Parameters</h3>'
        f'{"".join(rows_html)}'
        f'</div>'
    )


def _render_pareto_front(pareto_front: Dict[str, Any]) -> str:
    trials = pareto_front.get("trials", [])
    if not trials:
        return '<div class="no-data">No Pareto front data available</div>'

    selected = pareto_front.get("selected_trial")

    # Separate selected vs rest
    rest_x = []
    rest_y = []
    rest_color = []
    rest_text = []
    sel_x = []
    sel_y = []
    sel_text = []

    for t in trials:
        obj = t.get("objectives", {})
        px = obj.get("portfolio_calmar", 0)
        py = obj.get("worst_pair_calmar", 0)
        pc = obj.get("neg_overfit_penalty", 0)
        label = f"Trial {t.get('number', '?')}"

        if t.get("number") == selected:
            sel_x.append(px)
            sel_y.append(py)
            sel_text.append(label)
        else:
            rest_x.append(px)
            rest_y.append(py)
            rest_color.append(pc)
            rest_text.append(label)

    traces = []

    # Non-selected trials
    if rest_x:
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "x": rest_x,
            "y": rest_y,
            "name": "Trials",
            "text": rest_text,
            "marker": {
                "color": rest_color,
                "colorscale": "Viridis",
                "showscale": True,
                "size": 8,
                "colorbar": {"title": "Overfit Penalty"},
            },
            "hovertemplate": "Portfolio Calmar: %{x:.2f}<br>Worst Pair Calmar: %{y:.2f}<br>%{text}<extra></extra>",
        })

    # Selected trial (star marker)
    if sel_x:
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "x": sel_x,
            "y": sel_y,
            "name": "Selected",
            "text": sel_text,
            "marker": {
                "color": "#ffc777",
                "size": 16,
                "symbol": "star",
                "line": {"color": "#ffffff", "width": 1},
            },
            "hovertemplate": "Portfolio Calmar: %{x:.2f}<br>Worst Pair Calmar: %{y:.2f}<br>%{text}<extra></extra>",
        })

    traces_json = json.dumps(traces)

    return f"""<div class="chart-container">
<div id="pareto-front-chart" style="width:100%;height:450px;"></div>
<script>
(function() {{
  var traces = {traces_json};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'Pareto Front — Portfolio vs Worst Pair Calmar', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 60, r: 30, t: 40, b: 50}},
    showlegend: true,
    legend: {{font: {{size: 10}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{title: 'Portfolio Calmar', gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Worst Pair Calmar', gridcolor: '#3b4261', showgrid: true}}
  }};
  Plotly.newPlot('pareto-front-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_s2_optimization_history(s2_history: Dict[str, Any]) -> str:
    if not s2_history:
        return '<div class="no-data">No S2 optimization history available</div>'

    trial_nums = s2_history.get("trial_numbers", [])
    calmar_vals = s2_history.get("portfolio_calmar_values", [])
    best_calmar = s2_history.get("best_calmar_so_far", [])

    if not trial_nums:
        return '<div class="no-data">No S2 optimization history available</div>'

    traces = [
        {
            "type": "scatter",
            "mode": "markers",
            "x": trial_nums,
            "y": calmar_vals,
            "name": "Portfolio Calmar",
            "marker": {"color": "#86e1fc", "size": 4, "opacity": 0.5},
        },
        {
            "type": "scatter",
            "mode": "lines",
            "x": trial_nums,
            "y": best_calmar,
            "name": "Best Calmar so far",
            "line": {"color": "#c3e88d", "width": 2},
        },
    ]

    traces_json = json.dumps(traces)

    return f"""<div class="chart-container">
<div id="s2-opt-history-chart" style="width:100%;height:400px;"></div>
<script>
(function() {{
  var traces = {traces_json};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'S2 Optimization History', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 60, r: 30, t: 40, b: 50}},
    showlegend: true,
    legend: {{font: {{size: 10}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{title: 'Trial', gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Portfolio Calmar', gridcolor: '#3b4261', showgrid: true}}
  }};
  Plotly.newPlot('s2-opt-history-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""


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
