from __future__ import annotations

import json
import math
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
    padding: 0;
    max-width: 1920px;
    margin: 0 auto;
}

h1, h2, h3 {
    color: var(--text-primary);
    font-family: var(--font-mono);
}

/* Hero grid — 5 columns */
.hero-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
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

/* Sidebar navigation */
.report-layout {
    display: flex;
    gap: 0;
}

.sidebar {
    position: sticky;
    top: 0;
    width: 200px;
    min-width: 200px;
    height: 100vh;
    overflow-y: auto;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    padding: 16px 0;
    font-size: 11px;
    z-index: 100;
}

.sidebar a {
    display: block;
    padding: 4px 16px;
    color: var(--text-secondary);
    text-decoration: none;
    transition: color 0.15s, background 0.15s;
}

.sidebar a:hover {
    color: var(--text-primary);
    background: rgba(134, 225, 252, 0.05);
}

.sidebar a.active {
    color: var(--accent-cyan);
    border-left: 2px solid var(--accent-cyan);
    background: rgba(134, 225, 252, 0.08);
}

.sidebar .nav-section {
    font-weight: 700;
    color: var(--text-primary);
    padding: 12px 16px 4px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.report-content {
    flex: 1;
    min-width: 0;
    padding: 24px 40px;
    max-width: 1920px;
}

@media (max-width: 900px) {
    .sidebar { display: none; }
    .report-content { padding: 16px; }
}

/* Stat cards for new sections */
.stat-grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.stat-grid-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
}

.stat-card .stat-label {
    font-size: 11px;
    color: var(--text-secondary);
    margin-bottom: 4px;
}

.stat-card .stat-value {
    font-size: 20px;
    font-weight: 700;
}

/* Sortable table headers */
th.sortable {
    cursor: pointer;
    user-select: none;
}

th.sortable:hover {
    color: var(--accent-cyan);
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
    sortino = metrics.get("sortino_ratio", 0.0)
    recovery = metrics.get("recovery_factor", 0.0)
    profit_factor = metrics.get("profit_factor", 0.0)
    win_rate = metrics.get("win_rate", 0.0)

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

    # Sortino: green>2, yellow>1, red<1
    if sortino > 2:
        sortino_class = "positive"
    elif sortino > 1:
        sortino_class = "warning"
    else:
        sortino_class = "negative"

    # Calmar: green>3, yellow>1, red<1
    if calmar > 3:
        calmar_class = "positive"
    elif calmar > 1:
        calmar_class = "warning"
    else:
        calmar_class = "negative"

    # Recovery Factor: green>5, yellow>2, red<1
    if recovery > 5:
        recovery_class = "positive"
    elif recovery > 2:
        recovery_class = "warning"
    else:
        recovery_class = "negative"

    # Profit Factor: green>1.5, yellow>1, red<1
    if profit_factor > 1.5:
        pf_class = "positive"
    elif profit_factor > 1:
        pf_class = "warning"
    else:
        pf_class = "negative"

    cards = [
        ("Final Equity", equity_str, ""),
        ("Total PnL", pnl_str, pnl_class),
        ("Calmar Ratio", calmar_str, calmar_class),
        ("Sharpe (equity)", sharpe_str, ""),
        ("Max Drawdown", dd_str, dd_class),
        ("Total Trades", trades_str, ""),
        ("Sortino", f"{sortino:.2f}", sortino_class),
        ("Recovery Factor", f"{recovery:.2f}", recovery_class),
        ("Profit Factor", f"{profit_factor:.2f}", pf_class),
        ("Win Rate", f"{win_rate:.1f}%", ""),
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

    # Compute high-water mark and drawdown (in %)
    hwm = []
    drawdown = []
    running_max = float("-inf")
    for val in portfolio_equity_curve:
        running_max = max(running_max, val)
        hwm.append(running_max)
        dd_pct = ((val - running_max) / running_max * 100) if running_max > 0 else 0.0
        drawdown.append(dd_pct)

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
    yaxis2: {{title: 'Drawdown (%)', overlaying: 'y', side: 'right', gridcolor: '#3b4261', showgrid: false}}
  }};
  Plotly.newPlot('portfolio-equity-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_underwater_chart(
    portfolio_equity_curve: List[float],
    timestamps: List[str],
) -> str:
    if not portfolio_equity_curve:
        return ""

    # Compute drawdown % from running HWM
    drawdown: List[float] = []
    running_max = float("-inf")
    for val in portfolio_equity_curve:
        running_max = max(running_max, val)
        dd_pct = ((val - running_max) / running_max * 100) if running_max > 0 else 0.0
        drawdown.append(dd_pct)

    x_data = timestamps if timestamps else list(range(len(portfolio_equity_curve)))
    x_json = json.dumps(x_data)
    dd_json = json.dumps(drawdown)

    return f"""<div class="chart-container" id="sec-underwater">
<div id="underwater-chart" style="width:100%;height:250px;"></div>
<script>
(function() {{
  var x = {x_json};
  var dd = {dd_json};
  var traces = [
    {{
      x: x, y: dd, type: 'scatter', mode: 'lines',
      name: 'Drawdown %',
      line: {{color: '#ff757f', width: 1.5}},
      fill: 'tozeroy', fillcolor: 'rgba(255,117,127,0.3)'
    }}
  ];
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'Underwater (Drawdown %)', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 60, r: 40, t: 40, b: 40}},
    showlegend: false,
    xaxis: {{gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Drawdown (%)', gridcolor: '#3b4261', showgrid: true}}
  }};
  Plotly.newPlot('underwater-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_rolling_sharpe(
    portfolio_equity_curve: List[float],
    timestamps: List[str],
) -> str:
    WINDOW = 2160  # 90 days * 24 hours
    if len(portfolio_equity_curve) < WINDOW + 1:
        return ""

    # Compute hourly returns
    returns: List[float] = []
    for i in range(1, len(portfolio_equity_curve)):
        prev = portfolio_equity_curve[i - 1]
        curr = portfolio_equity_curve[i]
        ret = (curr - prev) / prev if prev != 0 else 0.0
        returns.append(ret)

    # Rolling Sharpe = mean/std * sqrt(365*24) over WINDOW
    annualization = math.sqrt(365 * 24)
    sharpe_vals: List[float] = []
    sharpe_x: List[Any] = []
    for i in range(WINDOW - 1, len(returns)):
        window = returns[i - WINDOW + 1: i + 1]
        n = len(window)
        mean = sum(window) / n
        variance = sum((r - mean) ** 2 for r in window) / n
        std = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean / std * annualization) if std > 0 else 0.0
        sharpe_vals.append(sharpe)
        # x corresponds to equity index WINDOW + i
        idx = i + 1  # equity index
        if timestamps and idx < len(timestamps):
            sharpe_x.append(timestamps[idx])
        else:
            sharpe_x.append(idx)

    x_json = json.dumps(sharpe_x)
    sharpe_json = json.dumps(sharpe_vals)
    n_points = len(sharpe_vals)

    return f"""<div class="chart-container" id="sec-rolling-sharpe">
<div id="rolling-sharpe-chart" style="width:100%;height:250px;"></div>
<script>
(function() {{
  var x = {x_json};
  var sharpe = {sharpe_json};
  var n = {n_points};
  var traces = [
    {{
      x: x, y: sharpe, type: 'scatter', mode: 'lines',
      name: 'Rolling Sharpe (90d)',
      line: {{color: '#86e1fc', width: 1.5}}
    }}
  ];
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'Rolling Sharpe Ratio (90-day)', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 60, r: 40, t: 40, b: 40}},
    showlegend: false,
    xaxis: {{gridcolor: '#3b4261', showgrid: true}},
    yaxis: {{title: 'Sharpe', gridcolor: '#3b4261', showgrid: true}},
    shapes: [
      {{
        type: 'line', x0: x[0], x1: x[n-1], y0: 0, y1: 0,
        line: {{color: '#ff757f', width: 1, dash: 'dash'}}
      }},
      {{
        type: 'line', x0: x[0], x1: x[n-1], y0: 1, y1: 1,
        line: {{color: '#ffffff', width: 1, dash: 'dash'}}
      }},
      {{
        type: 'rect', x0: x[0], x1: x[n-1], y0: -100, y1: 0,
        fillcolor: 'rgba(255,117,127,0.05)', line: {{width: 0}}
      }},
      {{
        type: 'rect', x0: x[0], x1: x[n-1], y0: 1, y1: 100,
        fillcolor: 'rgba(195,232,141,0.05)', line: {{width: 0}}
      }}
    ]
  }};
  Plotly.newPlot('rolling-sharpe-chart', traces, layout, {{responsive: true}});
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
        entry_ts = (trade.get("entry_time") or trade.get("entry_timestamp")
                    or trade.get("entry_ts"))
        exit_ts = (trade.get("exit_time") or trade.get("exit_timestamp")
                   or trade.get("exit_ts"))
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
    # Sort by exit_bar if available, otherwise by exit_ts
    sort_key = "exit_bar" if "exit_bar" in trades[0] else "exit_ts"
    for t in sorted(trades, key=lambda x: x.get(sort_key, 0)):
        equity += t.get("pnl_abs", 0)
        curve.append(equity)
    return curve


def build_daily_equity_curve(
    trades: list,
    start_equity: float = 100_000.0,
) -> tuple:
    """Build daily-resampled equity curve from trades.

    Returns (dates: List[str], equity: List[float]) with one point per day.
    """
    if not trades:
        return [], []

    from datetime import datetime, timedelta

    sorted_trades = sorted(trades, key=lambda t: t.get("exit_ts", ""))

    # Aggregate PnL per day
    daily_pnl: Dict[str, float] = {}
    for t in sorted_trades:
        exit_ts = str(t.get("exit_ts", ""))[:10]  # YYYY-MM-DD
        if len(exit_ts) == 10 and exit_ts[4] == "-":
            daily_pnl[exit_ts] = daily_pnl.get(exit_ts, 0.0) + t.get("pnl_abs", 0.0)

    if not daily_pnl:
        return [], []

    dates_with_pnl = sorted(daily_pnl.keys())
    start_date = datetime.strptime(dates_with_pnl[0], "%Y-%m-%d")
    end_date = datetime.strptime(dates_with_pnl[-1], "%Y-%m-%d")

    all_dates: List[str] = []
    current = start_date
    while current <= end_date:
        all_dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    equity = start_equity
    eq_curve: List[float] = []
    for d in all_dates:
        equity += daily_pnl.get(d, 0.0)
        eq_curve.append(equity)

    return all_dates, eq_curve


def _render_per_pair_table(
    pipeline_result: Dict[str, Any],
    eval_result: Dict[str, Any],
    analysis: Dict[str, Any] | None = None,
    excluded_symbols: set | None = None,
) -> str:
    per_pair = eval_result.get("per_pair_metrics", {})
    if not per_pair:
        return '<div class="no-data">No per-pair data available</div>'

    if excluded_symbols:
        per_pair = {s: m for s, m in per_pair.items() if s not in excluded_symbols}

    tiers = pipeline_result.get("tier_assignments", {})
    # Build verdict lookup from analysis (explicit param or fallback to pipeline_result["analysis"])
    verdict_map: Dict[str, str] = {}
    effective_analysis = analysis or pipeline_result.get("analysis")
    if effective_analysis:
        verdict_list = effective_analysis.get("per_pair", [])
        if isinstance(verdict_list, list):
            for entry in verdict_list:
                if isinstance(entry, dict):
                    verdict_map[entry.get("symbol", "")] = entry.get("verdict", "—")

    headers = ["Symbol", "Tier", "Verdict", "Trades/yr", "Sharpe", "Calmar", "Max DD%", "PnL%", "Win Rate", "PF"]
    col_types = [False, False, False, True, True, True, True, True, True, True]  # numeric flags
    header_cells = []
    for idx, (h, is_num) in enumerate(zip(headers, col_types)):
        num_str = "true" if is_num else "false"
        header_cells.append(
            f'<th class="sortable" onclick="sortTable(\'per-pair-table\',{idx},{num_str})">{h}</th>'
        )
    header_row = "".join(header_cells)

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
        max_dd = abs(m.get("max_drawdown", 0))
        pnl_pct = m.get("total_pnl_pct", 0)
        win_rate = m.get("win_rate", 0)
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

    sort_js = """<script>
function sortTable(tableId, col, numeric) {
  var table = document.getElementById(tableId);
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var asc = table.dataset.sortCol == col && table.dataset.sortDir == 'asc' ? false : true;
  rows.sort(function(a, b) {
    var av = a.cells[col].textContent.replace(/[%$,+]/g, '');
    var bv = b.cells[col].textContent.replace(/[%$,+]/g, '');
    if (numeric) { av = parseFloat(av) || 0; bv = parseFloat(bv) || 0; }
    return asc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  table.dataset.sortCol = col;
  table.dataset.sortDir = asc ? 'asc' : 'desc';
  var ths = table.querySelectorAll('th');
  for (var i = 0; i < ths.length; i++) {
    ths[i].textContent = ths[i].textContent.replace(/ [▲▼]/, '');
    if (i == col) ths[i].textContent += asc ? ' ▲' : ' ▼';
  }
}
</script>"""

    return (
        f'{sort_js}'
        f'<table id="per-pair-table"><thead><tr>{header_row}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


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


def _render_tier_table(pipeline_result: Dict[str, Any]) -> str:
    tier_data = pipeline_result.get("tier_assignments", {})
    pbo_data = pipeline_result.get("pbo_results", {})
    if not tier_data:
        return '<div class="no-data">No tier assignment data available</div>'

    headers = ["Symbol", "WF Tier", "OOS Sharpe", "Degradation", "Consistency",
               "Worst Sharpe", "PBO", "PBO Action", "Final Tier", "Mult"]
    header_row = "".join(f"<th>{h}</th>" for h in headers)

    rows = []
    for symbol in sorted(tier_data.keys()):
        t = tier_data[symbol]
        pbo = pbo_data.get(symbol, {})
        wf_tier = pbo.get("wf_tier", t.get("tier", "—"))
        final_tier = pbo.get("final_tier", t.get("tier", "—"))
        pbo_score = pbo.get("pbo_score", -1)
        pbo_action = pbo.get("pbo_action", "-")

        tier_cls = f"tier-{final_tier.lower()}" if final_tier in ("A", "B", "C", "S", "X") else ""
        pbo_str = f"{pbo_score:.2f}" if pbo_score >= 0 else "—"
        pbo_cls = (
            "tier-x" if pbo_score > 0.50
            else "tier-c" if pbo_score > 0.30
            else ""
        )

        row = (
            f"<tr>"
            f"<td>{symbol}</td>"
            f"<td>{wf_tier}</td>"
            f"<td>{t.get('sharpe', 0):.2f}</td>"
            f"<td>{t.get('degradation', 0):.2f}</td>"
            f"<td>{t.get('consistency', 0):.2f}</td>"
            f"<td>{t.get('worst_sharpe', 0):.2f}</td>"
            f'<td class="{pbo_cls}">{pbo_str}</td>'
            f"<td>{pbo_action}</td>"
            f'<td class="{tier_cls}">{final_tier}</td>'
            f"<td>{t.get('multiplier', 0):.2f}</td>"
            f"</tr>"
        )
        rows.append(row)

    return f'<table><thead><tr>{header_row}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _render_pbo_chart(pipeline_result: Dict[str, Any]) -> str:
    """Render PBO bar chart with threshold lines at 0.30 and 0.50."""
    pbo_data = pipeline_result.get("pbo_results", {})
    if not pbo_data:
        return '<div class="no-data">No PBO data available</div>'

    symbols = sorted(pbo_data.keys())
    scores = [pbo_data[s].get("pbo_score", 0) for s in symbols]
    short_symbols = [s.split("/")[0] for s in symbols]

    colors = []
    for sc in scores:
        if sc < 0:
            colors.append("var(--text-muted)")
        elif sc > 0.50:
            colors.append("var(--accent-red)")
        elif sc > 0.30:
            colors.append("var(--accent-yellow)")
        else:
            colors.append("var(--accent-green)")

    div_id = "pbo-chart"
    return f"""
    <h3>PBO — Probability of Backtest Overfitting</h3>
    <div id="{div_id}" style="width:100%;height:350px;"></div>
    <script>
    Plotly.newPlot("{div_id}", [{{
        x: {json.dumps(short_symbols)},
        y: {json.dumps(scores)},
        type: "bar",
        marker: {{ color: {json.dumps(colors)} }}
    }}], {{
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: {{ color: "#c8d3f5", family: "JetBrains Mono, monospace" }},
        yaxis: {{ title: "PBO Score", gridcolor: "#3b4261", range: [0, 1] }},
        xaxis: {{ gridcolor: "#3b4261" }},
        shapes: [
            {{ type: "line", x0: -0.5, x1: {len(symbols) - 0.5},
               y0: 0.30, y1: 0.30,
               line: {{ color: "#ffc777", width: 2, dash: "dash" }} }},
            {{ type: "line", x0: -0.5, x1: {len(symbols) - 0.5},
               y0: 0.50, y1: 0.50,
               line: {{ color: "#ff757f", width: 2, dash: "dash" }} }}
        ],
        annotations: [
            {{ x: {len(symbols) - 0.5}, y: 0.30, text: "demote",
               showarrow: false, xanchor: "right",
               font: {{ color: "#ffc777", size: 10 }} }},
            {{ x: {len(symbols) - 0.5}, y: 0.50, text: "exclude",
               showarrow: false, xanchor: "right",
               font: {{ color: "#ff757f", size: 10 }} }}
        ],
        margin: {{ t: 20, r: 20, b: 40, l: 60 }}
    }}, {{ responsive: true }});
    </script>
    """


def _render_wf_evaluation(
    eval_result: Dict[str, Any],
    excluded_symbols: set | None = None,
) -> str:
    wf_metrics = eval_result.get("wf_eval_metrics", {})
    if not wf_metrics:
        return '<div class="no-data">No walk-forward evaluation data available</div>'

    if excluded_symbols:
        wf_metrics = {s: m for s, m in wf_metrics.items() if s not in excluded_symbols}

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
                f"<td>{m.get('sharpe_equity', m.get('sharpe_ratio_equity_based', m.get('sharpe', 0))):.2f}</td>"
                f"<td>{abs(m.get('max_drawdown', 0)):.1f}%</td>"
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
        # Filter out fixed/categorical params (non-numeric only)
        _EXCLUDED_PARAMS = {"allow_flip", "trend_strict", "trend_tf"}
        param_keys = []
        if trials:
            for pk in sorted(trials[0].get("params", {}).keys()):
                if pk in _EXCLUDED_PARAMS:
                    continue
                vals = [t.get("params", {}).get(pk, 0) for t in trials]
                # Skip non-numeric
                if not all(isinstance(v, (int, float)) for v in vals):
                    continue
                param_keys.append(pk)

        dimensions = []
        for pk in param_keys:
            vals = [t.get("params", {}).get(pk, 0) for t in trials]
            dim: Dict[str, Any] = {
                "label": pk,
                "values": vals,
            }
            # Use PARAM_RANGES for axis range so convergence is visible
            if pk in PARAM_RANGES:
                lo, hi = PARAM_RANGES[pk]
                dim["range"] = [float(lo), float(hi)]
            dimensions.append(dim)

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
<h4 style="color:#c099ff;font-size:13px;text-align:center;margin:8px 0 4px 0;font-family:'JetBrains Mono',monospace;">{sym} — Parallel Coordinates</h4>
<div id="{parcoords_div}" style="width:100%;height:400px;"></div>
<script>
(function() {{
  var traces = {parcoords_json};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 10}},
    margin: {{l: 60, r: 60, t: 50, b: 30}}
  }};
  Plotly.newPlot('{parcoords_div}', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""

        # ── Scatter: Sharpe vs Max DD ──
        scatter_sharpe = [
            t.get("metrics", {}).get("sharpe_equity",
                t.get("metrics", {}).get("sharpe_ratio_equity_based",
                    t.get("metrics", {}).get("sharpe", 0)))
            for t in trials
        ]
        scatter_dd = [
            abs(t.get("metrics", {}).get("max_drawdown", 0))
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
    if not per_pair_trades:
        return '<div class="no-data">No P&amp;L contribution data available</div>'

    # Calculate absolute PnL per pair
    pair_pnl: Dict[str, float] = {}
    for symbol, trades in per_pair_trades.items():
        pair_pnl[symbol] = sum(t.get("pnl_abs", 0.0) for t in trades)

    if not pair_pnl:
        return '<div class="no-data">No P&amp;L contribution data available</div>'

    # Sort by absolute contribution (largest first)
    sorted_pairs = sorted(pair_pnl.items(), key=lambda x: abs(x[1]), reverse=True)

    total_abs = sum(abs(v) for v in pair_pnl.values())

    symbols = [p[0] for p in sorted_pairs]
    values = [p[1] for p in sorted_pairs]
    colors = ["#c3e88d" if v >= 0 else "#ff757f" for v in values]
    pct_labels = [
        f"{(v / total_abs * 100):+.1f}%" if total_abs > 0 else "0.0%"
        for v in values
    ]

    symbols_json = json.dumps(symbols)
    values_json = json.dumps(values)
    colors_json = json.dumps(colors)
    labels_json = json.dumps(pct_labels)

    return f"""<div class="chart-container">
<div id="pnl-contribution-chart" style="width:100%;height:400px;"></div>
<script>
(function() {{
  var symbols = {symbols_json};
  var values = {values_json};
  var colors = {colors_json};
  var labels = {labels_json};
  var trace = {{
    y: symbols,
    x: values,
    type: 'bar',
    orientation: 'h',
    marker: {{color: colors}},
    text: labels,
    textposition: 'outside',
    textfont: {{color: '#c8d3f5', size: 11}}
  }};
  var layout = {{
    paper_bgcolor: '#2f334d',
    plot_bgcolor: '#2f334d',
    font: {{color: '#c8d3f5', family: "'JetBrains Mono', monospace", size: 11}},
    title: {{text: 'Per-Pair P&L Contribution', font: {{color: '#c099ff', size: 14}}}},
    margin: {{l: 120, r: 60, t: 40, b: 40}},
    xaxis: {{title: 'P&L ($)', gridcolor: '#3b4261', zeroline: true, zerolinecolor: '#545c7e'}},
    yaxis: {{autorange: 'reversed'}}
  }};
  Plotly.newPlot('pnl-contribution-chart', [trace], layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_correlation_heatmap(corr_matrix: Dict[str, Any]) -> str:
    symbols = corr_matrix.get("symbols", [])
    matrix = corr_matrix.get("matrix", [])
    threshold = corr_matrix.get("corr_gate_threshold", None)

    if not symbols or not matrix:
        return '<div class="no-data">No correlation data available</div>'

    # Build annotation text (correlation values on cells)
    annotations: List[str] = []
    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            annotations.append(
                f"{{x: {j}, y: {i}, text: '{val:.2f}', showarrow: false, "
                f"font: {{color: '#c8d3f5', size: 10}}}}"
            )
    annotations_str = ",\n    ".join(annotations)

    symbols_json = json.dumps(symbols)
    matrix_json = json.dumps(matrix)

    threshold_annotation = ""
    threshold_text = ""
    if threshold is not None:
        threshold_text = f"Correlation Gate Threshold: {threshold}"

    return f"""<div class="chart-container">
<div id="correlation-heatmap" style="width:100%;height:500px;"></div>
<script>
(function() {{
  var symbols = {symbols_json};
  var matrix = {matrix_json};
  var trace = {{
    z: matrix,
    x: symbols,
    y: symbols,
    type: 'heatmap',
    colorscale: 'RdBu',
    reversescale: true,
    zmin: -1,
    zmax: 1,
    colorbar: {{
      title: 'Correlation',
      titlefont: {{color: '#c8d3f5'}},
      tickfont: {{color: '#c8d3f5'}}
    }}
  }};
  var layout = {{
    paper_bgcolor: '#2f334d',
    plot_bgcolor: '#2f334d',
    font: {{color: '#c8d3f5', family: "'JetBrains Mono', monospace", size: 11}},
    title: {{text: '{threshold_text}', font: {{color: '#c099ff', size: 13}}}},
    margin: {{l: 100, r: 40, t: 50, b: 100}},
    xaxis: {{tickangle: -45}},
    yaxis: {{autorange: 'reversed'}},
    annotations: [
    {annotations_str}
    ]
  }};
  Plotly.newPlot('correlation-heatmap', [trace], layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_monthly_returns(
    portfolio_trades: List[Dict[str, Any]],
    timestamps: List[str],
) -> str:
    if not portfolio_trades:
        return '<div class="no-data">No trade data for monthly returns</div>'

    start_equity = 100_000.0

    # Group trades by year-month using exit_ts
    monthly_pnl: Dict[str, float] = {}
    for trade in portfolio_trades:
        exit_ts = trade.get("exit_ts", "")
        if not exit_ts:
            continue
        # Parse year and month from timestamp (ISO format expected)
        try:
            ts_str = str(exit_ts)
            year_month = ts_str[:7]  # "YYYY-MM"
            if len(year_month) == 7 and year_month[4] == "-":
                pnl = trade.get("pnl_abs", 0.0)
                monthly_pnl[year_month] = monthly_pnl.get(year_month, 0.0) + pnl
        except (ValueError, IndexError):
            continue

    if not monthly_pnl:
        return '<div class="no-data">No trade data for monthly returns</div>'

    # Get year range
    years = sorted(set(ym[:4] for ym in monthly_pnl.keys()))
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Build table rows
    rows_html = []
    for year in years:
        cells = [f'<td style="font-weight:600;">{year}</td>']
        year_total = 0.0
        for m_idx in range(1, 13):
            key = f"{year}-{m_idx:02d}"
            pnl = monthly_pnl.get(key, None)
            if pnl is not None:
                ret_pct = (pnl / start_equity) * 100
                year_total += ret_pct
                # Color: green for positive, red for negative, scaled alpha
                magnitude = min(abs(ret_pct) / 10.0, 1.0)  # Scale to max 10%
                alpha = max(0.15, magnitude * 0.6)
                if ret_pct >= 0:
                    bg = f"rgba(195, 232, 141, {alpha:.2f})"
                    color = "#c3e88d"
                else:
                    bg = f"rgba(255, 117, 127, {alpha:.2f})"
                    color = "#ff757f"
                cells.append(
                    f'<td style="background:{bg};color:{color};text-align:center;">'
                    f'{ret_pct:+.1f}%</td>'
                )
            else:
                cells.append('<td style="text-align:center;color:#3b4261;">—</td>')

        # Year total column
        magnitude = min(abs(year_total) / 30.0, 1.0)
        alpha = max(0.15, magnitude * 0.6)
        if year_total >= 0:
            bg = f"rgba(195, 232, 141, {alpha:.2f})"
            color = "#c3e88d"
        else:
            bg = f"rgba(255, 117, 127, {alpha:.2f})"
            color = "#ff757f"
        cells.append(
            f'<td style="background:{bg};color:{color};text-align:center;font-weight:600;">'
            f'{year_total:+.1f}%</td>'
        )
        rows_html.append(f'<tr>{"".join(cells)}</tr>')

    headers = ["Year"] + month_names + ["Year Total"]
    header_cells = "".join(f"<th>{h}</th>" for h in headers)

    return f"""<div class="chart-container">
<h3 style="color:var(--accent-purple);font-size:14px;margin-bottom:12px;">Monthly Returns</h3>
<table>
<thead><tr>{header_cells}</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table>
</div>"""


def _render_per_pair_monthly_heatmaps(
    per_pair_trades: Dict[str, List[Dict[str, Any]]],
    excluded_symbols: set,
) -> str:
    """Render per-pair monthly PnL heatmaps using Plotly (one chart per symbol)."""
    if not per_pair_trades:
        return '<div id="sec-per-pair-monthly" class="no-data">No per-pair trade data for monthly heatmaps</div>'

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    charts: List[str] = []
    for symbol in sorted(per_pair_trades.keys()):
        if symbol in excluded_symbols:
            continue

        trades = per_pair_trades[symbol]
        if not trades:
            continue

        # Group trades by YYYY-MM, sum pnl_abs
        monthly_pnl: Dict[str, float] = {}
        for trade in trades:
            exit_ts = trade.get("exit_ts", "")
            if not exit_ts:
                continue
            try:
                year_month = str(exit_ts)[:7]
                if len(year_month) == 7 and year_month[4] == "-":
                    pnl = float(trade.get("pnl_abs", 0.0))
                    monthly_pnl[year_month] = monthly_pnl.get(year_month, 0.0) + pnl
            except (ValueError, IndexError):
                continue

        if not monthly_pnl:
            continue

        # Build year x month matrix (rows = years ascending, cols = Jan-Dec)
        years = sorted(set(ym[:4] for ym in monthly_pnl.keys()))
        # z[year_idx][month_idx] = pnl or None
        z_matrix: List[List[Any]] = []
        text_matrix: List[List[str]] = []
        for year in years:
            z_row: List[Any] = []
            text_row: List[str] = []
            for m_idx in range(1, 13):
                key = f"{year}-{m_idx:02d}"
                pnl = monthly_pnl.get(key, None)
                if pnl is not None:
                    z_row.append(pnl)
                    sign = "+" if pnl >= 0 else ""
                    text_row.append(f"${sign}{pnl:,.0f}")
                else:
                    z_row.append(None)
                    text_row.append("")
            z_matrix.append(z_row)
            text_matrix.append(text_row)

        safe_id = symbol.replace("/", "_").replace(" ", "_")
        div_id = f"monthly-heatmap-{safe_id}"
        height = max(120, len(years) * 60 + 60)

        z_json = json.dumps(z_matrix)
        text_json = json.dumps(text_matrix)
        years_json = json.dumps(years)
        months_json = json.dumps(month_names)

        chart_html = f"""<div class="chart-container">
<h4 style="color:var(--accent-purple);font-size:13px;margin-bottom:8px;">{symbol} — Monthly Returns</h4>
<div id="{div_id}" style="width:100%;height:{height}px;"></div>
<script>
(function() {{
  var z = {z_json};
  var text = {text_json};
  var years = {years_json};
  var months = {months_json};
  var trace = {{
    z: z,
    x: months,
    y: years,
    text: text,
    texttemplate: '%{{text}}',
    type: 'heatmap',
    colorscale: 'RdYlGn',
    zmid: 0,
    showscale: true,
    colorbar: {{
      title: 'PnL ($)',
      titlefont: {{color: '#c8d3f5'}},
      tickfont: {{color: '#c8d3f5'}}
    }}
  }};
  var layout = {{
    paper_bgcolor: '#2f334d',
    plot_bgcolor: '#2f334d',
    font: {{color: '#c8d3f5', family: "'JetBrains Mono', monospace", size: 11}},
    margin: {{l: 60, r: 60, t: 20, b: 40}},
    xaxis: {{tickangle: 0}},
    yaxis: {{autorange: 'reversed', dtick: 1}}
  }};
  Plotly.newPlot('{div_id}', [trace], layout, {{responsive: true}});
}})();
</script>
</div>"""
        charts.append(chart_html)

    if not charts:
        return '<div id="sec-per-pair-monthly" class="no-data">No per-pair trade data for monthly heatmaps</div>'

    return f'<div id="sec-per-pair-monthly">{"".join(charts)}</div>'


def _render_long_short_analysis(portfolio_trades: List[Dict[str, Any]]) -> str:
    if not portfolio_trades:
        return '<div id="sec-long-short" class="no-data">No trade data for long/short analysis</div>'

    long_trades = [t for t in portfolio_trades if t.get("direction") == "long"]
    short_trades = [t for t in portfolio_trades if t.get("direction") == "short"]

    def _dir_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        count = len(trades)
        wins = sum(1 for t in trades if t.get("pnl_abs", 0.0) > 0)
        win_rate = (wins / count * 100) if count > 0 else 0.0
        avg_pnl_pct = (sum(t.get("pnl_pct", 0.0) for t in trades) / count) if count > 0 else 0.0
        total_pnl = sum(t.get("pnl_abs", 0.0) for t in trades)
        avg_hold = (sum(t.get("hold_bars", 0) for t in trades) / count) if count > 0 else 0.0
        return {
            "count": count,
            "win_rate": win_rate,
            "avg_pnl_pct": avg_pnl_pct,
            "total_pnl": total_pnl,
            "avg_hold": avg_hold,
        }

    ls = _dir_stats(long_trades)
    ss = _dir_stats(short_trades)

    def _stat_card(label: str, stats: Dict[str, Any], border_color: str) -> str:
        pnl_color = "#c3e88d" if stats["total_pnl"] >= 0 else "#ff757f"
        avg_color = "#c3e88d" if stats["avg_pnl_pct"] >= 0 else "#ff757f"
        return (
            f'<div class="stat-card" style="border-top:3px solid {border_color};">'
            f'<div class="stat-label" style="font-size:13px;font-weight:700;color:{border_color};margin-bottom:10px;">{label}</div>'
            f'<div class="wf-metric-row"><span class="wf-metric-label">Trades</span>'
            f'<span class="wf-metric-value">{stats["count"]}</span></div>'
            f'<div class="wf-metric-row"><span class="wf-metric-label">Win Rate</span>'
            f'<span class="wf-metric-value">{stats["win_rate"]:.1f}%</span></div>'
            f'<div class="wf-metric-row"><span class="wf-metric-label">Avg PnL</span>'
            f'<span class="wf-metric-value" style="color:{avg_color}">{stats["avg_pnl_pct"]:+.2f}%</span></div>'
            f'<div class="wf-metric-row"><span class="wf-metric-label">Total PnL</span>'
            f'<span class="wf-metric-value" style="color:{pnl_color}">${stats["total_pnl"]:,.0f}</span></div>'
            f'<div class="wf-metric-row"><span class="wf-metric-label">Avg Hold</span>'
            f'<span class="wf-metric-value">{stats["avg_hold"]:.1f} bars</span></div>'
            f'</div>'
        )

    long_card = _stat_card("LONG", ls, "#c3e88d")
    short_card = _stat_card("SHORT", ss, "#ff757f")
    cards_html = f'<div class="stat-grid-2">{long_card}{short_card}</div>'

    # Stacked bar chart
    total_trades = ls["count"] + ss["count"]
    long_trade_ratio = ls["count"] / total_trades if total_trades > 0 else 0.5
    short_trade_ratio = ss["count"] / total_trades if total_trades > 0 else 0.5

    total_pnl_abs = abs(ls["total_pnl"]) + abs(ss["total_pnl"])
    long_pnl_ratio = abs(ls["total_pnl"]) / total_pnl_abs if total_pnl_abs > 0 else 0.5
    short_pnl_ratio = abs(ss["total_pnl"]) / total_pnl_abs if total_pnl_abs > 0 else 0.5

    chart_html = f"""<div class="chart-container" style="padding:12px;">
<div id="long-short-chart" style="width:100%;height:120px;"></div>
<script>
(function() {{
  var traces = [
    {{
      x: [{long_trade_ratio:.4f}, {long_pnl_ratio:.4f}],
      y: ['Trades', 'PnL Contribution'],
      type: 'bar', orientation: 'h',
      name: 'Long', marker: {{color: '#c3e88d'}},
      text: ['{ls["count"]}', '${ls["total_pnl"]:,.0f}'],
      textposition: 'inside', insidetextanchor: 'middle',
      textfont: {{color: '#222436', size: 11}}
    }},
    {{
      x: [{short_trade_ratio:.4f}, {short_pnl_ratio:.4f}],
      y: ['Trades', 'PnL Contribution'],
      type: 'bar', orientation: 'h',
      name: 'Short', marker: {{color: '#ff757f'}},
      text: ['{ss["count"]}', '${ss["total_pnl"]:,.0f}'],
      textposition: 'inside', insidetextanchor: 'middle',
      textfont: {{color: '#222436', size: 11}}
    }}
  ];
  var layout = {{
    barmode: 'stack',
    paper_bgcolor: '#2f334d', plot_bgcolor: '#2f334d',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    margin: {{l: 120, r: 20, t: 10, b: 20}},
    showlegend: true,
    legend: {{orientation: 'h', x: 0.5, xanchor: 'center', y: 1.2, font: {{size: 10}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{range: [0, 1], showgrid: false, showticklabels: false}},
    yaxis: {{gridcolor: '#3b4261'}}
  }};
  Plotly.newPlot('long-short-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""

    return f'<div id="sec-long-short">{cards_html}{chart_html}</div>'


def _render_top_drawdowns(
    portfolio_equity_curve: List[float],
    timestamps: List[str],
) -> str:
    if len(portfolio_equity_curve) < 3:
        return ""

    # Find all drawdown episodes (non-overlapping peak->trough->recovery)
    episodes: List[Dict[str, Any]] = []
    n = len(portfolio_equity_curve)
    i = 0

    while i < n:
        # Find local peak: move forward while equity is rising or flat
        peak_idx = i
        peak_val = portfolio_equity_curve[i]

        # Advance to find where a drawdown starts
        j = i + 1
        while j < n and portfolio_equity_curve[j] >= peak_val:
            if portfolio_equity_curve[j] > peak_val:
                peak_idx = j
                peak_val = portfolio_equity_curve[j]
            j += 1

        if j >= n:
            break  # No drawdown from this peak

        # We're now in a drawdown — find trough
        trough_idx = j
        trough_val = portfolio_equity_curve[j]
        k = j + 1
        while k < n and portfolio_equity_curve[k] <= peak_val:
            if portfolio_equity_curve[k] < trough_val:
                trough_idx = k
                trough_val = portfolio_equity_curve[k]
            k += 1

        depth_pct = (trough_val - peak_val) / peak_val * 100  # negative

        # Find recovery (first point >= peak after trough)
        recovery_idx = None
        m = trough_idx + 1
        while m < n:
            if portfolio_equity_curve[m] >= peak_val:
                recovery_idx = m
                break
            m += 1

        episodes.append({
            "depth_pct": depth_pct,
            "peak_idx": peak_idx,
            "trough_idx": trough_idx,
            "recovery_idx": recovery_idx,
            "duration_bars": trough_idx - peak_idx,
            "recovery_bars": (recovery_idx - trough_idx) if recovery_idx is not None else None,
        })

        # Move past the recovery (or past trough if no recovery)
        i = recovery_idx if recovery_idx is not None else trough_idx + 1

    if not episodes:
        return ""

    # Sort by depth (most negative first = deepest), take top 5
    top5 = sorted(episodes, key=lambda e: e["depth_pct"])[:5]

    def _ts(idx: int) -> str:
        if timestamps and idx < len(timestamps):
            return str(timestamps[idx])[:10]
        return f"bar {idx}"

    def _depth_color(depth_pct: float) -> str:
        """Scale red intensity with severity."""
        severity = min(abs(depth_pct) / 30.0, 1.0)  # 30% = full red
        r = int(255)
        g = int(117 + (1 - severity) * 100)
        b = int(127 + (1 - severity) * 100)
        return f"rgb({r},{g},{b})"

    rows = []
    for rank, ep in enumerate(top5, 1):
        depth_color = _depth_color(ep["depth_pct"])
        peak_ts = _ts(ep["peak_idx"])
        trough_ts = _ts(ep["trough_idx"])
        if ep["recovery_idx"] is not None:
            recovery_ts = _ts(ep["recovery_idx"])
            recovery_bars_str = str(ep["recovery_bars"])
            recovery_cell = f'<td>{recovery_ts}</td>'
        else:
            recovery_cell = '<td style="color:#ffc777;">ongoing</td>'
            recovery_bars_str = '<span style="color:#ffc777;">—</span>'

        rows.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f'<td style="color:{depth_color};font-weight:600;">{ep["depth_pct"]:.2f}%</td>'
            f"<td>{peak_ts}</td>"
            f"<td>{trough_ts}</td>"
            f"{recovery_cell}"
            f"<td>{ep['duration_bars']}</td>"
            f"<td>{recovery_bars_str}</td>"
            f"</tr>"
        )

    headers = ["#", "Depth", "Peak", "Trough", "Recovery", "Duration (bars)", "Recovery (bars)"]
    header_row = "".join(f"<th>{h}</th>" for h in headers)

    return (
        f'<div id="sec-top-drawdowns" class="chart-container">'
        f'<h4 style="color:var(--accent-purple);margin-bottom:12px;">Top 5 Drawdown Episodes</h4>'
        f'<table><thead><tr>{header_row}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
        f'</div>'
    )


def _render_streak_analysis(
    portfolio_trades: List[Dict[str, Any]],
    portfolio_metrics: Dict[str, Any],
) -> str:
    if not portfolio_trades:
        return '<div id="sec-streaks" class="no-data">No trade data for streak analysis</div>'

    # Build streak sequences from trades
    win_streaks: List[int] = []
    loss_streaks: List[int] = []
    current_win = 0
    current_loss = 0

    for t in portfolio_trades:
        pnl = t.get("pnl_abs", 0.0)
        if pnl > 0:
            if current_loss > 0:
                loss_streaks.append(current_loss)
                current_loss = 0
            current_win += 1
        elif pnl < 0:
            if current_win > 0:
                win_streaks.append(current_win)
                current_win = 0
            current_loss += 1
        else:
            # Breakeven: close any open streak
            if current_win > 0:
                win_streaks.append(current_win)
                current_win = 0
            if current_loss > 0:
                loss_streaks.append(current_loss)
                current_loss = 0

    if current_win > 0:
        win_streaks.append(current_win)
    if current_loss > 0:
        loss_streaks.append(current_loss)

    # Stats — use portfolio_metrics if provided, otherwise compute from streak lists
    max_win = portfolio_metrics.get("max_win_streak", max(win_streaks) if win_streaks else 0)
    max_loss = portfolio_metrics.get("max_loss_streak", max(loss_streaks) if loss_streaks else 0)
    avg_win = (sum(win_streaks) / len(win_streaks)) if win_streaks else 0.0
    avg_loss = (sum(loss_streaks) / len(loss_streaks)) if loss_streaks else 0.0

    cards_html = (
        f'<div class="stat-grid-4">'
        f'<div class="stat-card" style="border-top:3px solid #c3e88d;">'
        f'<div class="stat-label">Max Win Streak</div>'
        f'<div class="stat-value" style="color:#c3e88d;">{max_win}</div>'
        f'</div>'
        f'<div class="stat-card" style="border-top:3px solid #ff757f;">'
        f'<div class="stat-label">Max Loss Streak</div>'
        f'<div class="stat-value" style="color:#ff757f;">{max_loss}</div>'
        f'</div>'
        f'<div class="stat-card" style="border-top:3px solid #c3e88d;">'
        f'<div class="stat-label">Avg Win Streak</div>'
        f'<div class="stat-value" style="color:#c3e88d;">{avg_win:.1f}</div>'
        f'</div>'
        f'<div class="stat-card" style="border-top:3px solid #ff757f;">'
        f'<div class="stat-label">Avg Loss Streak</div>'
        f'<div class="stat-value" style="color:#ff757f;">{avg_loss:.1f}</div>'
        f'</div>'
        f'</div>'
    )

    # Build frequency distributions
    win_max_len = max(win_streaks) if win_streaks else 0
    loss_max_len = max(loss_streaks) if loss_streaks else 0
    max_len = max(win_max_len, loss_max_len, 1)

    win_freq: List[int] = [0] * (max_len + 1)
    loss_freq: List[int] = [0] * (max_len + 1)
    for s in win_streaks:
        win_freq[s] += 1
    for s in loss_streaks:
        loss_freq[s] += 1

    x_vals = list(range(1, max_len + 1))
    win_y = win_freq[1:]
    loss_y = loss_freq[1:]

    x_json = json.dumps(x_vals)
    win_json = json.dumps(win_y)
    loss_json = json.dumps(loss_y)

    chart_html = f"""<div class="chart-container">
<div id="streak-chart" style="width:100%;height:250px;"></div>
<script>
(function() {{
  var x = {x_json};
  var traces = [
    {{
      x: x, y: {win_json}, type: 'bar', name: 'Win Streaks',
      marker: {{color: '#c3e88d', opacity: 0.85}}
    }},
    {{
      x: x, y: {loss_json}, type: 'bar', name: 'Loss Streaks',
      marker: {{color: '#ff757f', opacity: 0.85}}
    }}
  ];
  var layout = {{
    barmode: 'group',
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    title: {{text: 'Win/Loss Streak Distribution', font: {{size: 14, color: '#c099ff'}}}},
    margin: {{l: 50, r: 30, t: 40, b: 40}},
    showlegend: true,
    legend: {{font: {{size: 10}}, bgcolor: 'rgba(0,0,0,0)'}},
    xaxis: {{title: 'Streak Length', gridcolor: '#3b4261', dtick: 1}},
    yaxis: {{title: 'Frequency', gridcolor: '#3b4261'}}
  }};
  Plotly.newPlot('streak-chart', traces, layout, {{responsive: true}});
}})();
</script>
</div>"""

    return f'<div id="sec-streaks">{cards_html}{chart_html}</div>'


def _render_trade_timing(portfolio_trades: List[Dict[str, Any]]) -> str:
    if not portfolio_trades:
        return '<div id="sec-trade-timing" class="no-data">No trade data for timing analysis</div>'

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    # 7 rows (days) x 24 cols (hours) count matrix
    matrix: List[List[int]] = [[0] * 24 for _ in range(7)]
    parsed = 0

    for t in portfolio_trades:
        entry_ts = t.get("entry_ts", "")
        if not entry_ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(str(entry_ts))
            hour = dt.hour
            weekday = dt.weekday()  # 0=Monday, 6=Sunday
            matrix[weekday][hour] += 1
            parsed += 1
        except (ValueError, TypeError):
            continue

    if parsed == 0:
        return '<div id="sec-trade-timing" class="no-data">No valid timestamps for timing analysis</div>'

    z_json = json.dumps(matrix)
    days_json = json.dumps(DAY_NAMES)
    hours_json = json.dumps(list(range(24)))

    # Build annotations for non-zero cells
    annotations: List[str] = []
    for day_idx in range(7):
        for hour in range(24):
            val = matrix[day_idx][hour]
            if val > 0:
                annotations.append(
                    f"{{x: {hour}, y: {day_idx}, text: '{val}', showarrow: false, "
                    f"font: {{color: '#222436', size: 9}}}}"
                )
    annotations_str = ",\n    ".join(annotations)

    return f"""<div id="sec-trade-timing" class="chart-container">
<h4 style="color:var(--accent-purple);margin-bottom:8px;">Trade Entry Timing (UTC)</h4>
<div id="trade-timing-chart" style="width:100%;height:300px;"></div>
<script>
(function() {{
  var z = {z_json};
  var days = {days_json};
  var hours = {hours_json};
  var trace = {{
    z: z,
    x: hours,
    y: days,
    type: 'heatmap',
    colorscale: 'Viridis',
    showscale: true,
    colorbar: {{
      title: 'Trades',
      titlefont: {{color: '#c8d3f5'}},
      tickfont: {{color: '#c8d3f5'}}
    }}
  }};
  var layout = {{
    paper_bgcolor: '#2f334d', plot_bgcolor: '#222436',
    font: {{color: '#c8d3f5', family: 'JetBrains Mono, monospace', size: 11}},
    margin: {{l: 80, r: 60, t: 20, b: 40}},
    xaxis: {{title: 'Hour (UTC)', gridcolor: '#3b4261', dtick: 4}},
    yaxis: {{autorange: 'reversed', gridcolor: '#3b4261'}},
    annotations: [
    {annotations_str}
    ]
  }};
  Plotly.newPlot('trade-timing-chart', [trace], layout, {{responsive: true}});
}})();
</script>
</div>"""


def _render_trade_analysis(
    portfolio_trades: List[Dict[str, Any]],
    per_pair_trades: Dict[str, List[Dict[str, Any]]],
) -> str:
    if not portfolio_trades:
        return '<div class="no-data">No trade data for analysis</div>'

    sections: List[str] = []

    # ── 1. Exit Reason Bar Chart ──
    reason_counts: Dict[str, int] = {}
    for t in portfolio_trades:
        reason = t.get("reason", "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    if reason_counts:
        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        reasons = [r[0] for r in sorted_reasons]
        counts = [r[1] for r in sorted_reasons]
        reasons_json = json.dumps(reasons)
        counts_json = json.dumps(counts)

        sections.append(f"""<div class="chart-container">
<div id="exit-reasons-chart" style="width:100%;height:350px;"></div>
<script>
(function() {{
  var trace = {{
    x: {reasons_json},
    y: {counts_json},
    type: 'bar',
    marker: {{color: '#86e1fc'}}
  }};
  var layout = {{
    paper_bgcolor: '#2f334d',
    plot_bgcolor: '#2f334d',
    font: {{color: '#c8d3f5', family: "'JetBrains Mono', monospace", size: 11}},
    title: {{text: 'Exit Reasons', font: {{color: '#c099ff', size: 14}}}},
    margin: {{l: 50, r: 30, t: 40, b: 80}},
    xaxis: {{tickangle: -30, gridcolor: '#3b4261'}},
    yaxis: {{title: 'Count', gridcolor: '#3b4261'}}
  }};
  Plotly.newPlot('exit-reasons-chart', [trace], layout, {{responsive: true}});
}})();
</script>
</div>""")

    # ── 3. P&L Distribution Histogram ──
    pnl_pcts = [t.get("pnl_pct", 0.0) for t in portfolio_trades if "pnl_pct" in t]
    if pnl_pcts:
        pnl_pcts_json = json.dumps(pnl_pcts)
        sections.append(f"""<div class="chart-container">
<div id="pnl-distribution-chart" style="width:100%;height:350px;"></div>
<script>
(function() {{
  var trace = {{
    x: {pnl_pcts_json},
    type: 'histogram',
    marker: {{color: '#c099ff', line: {{color: '#222436', width: 1}}}},
    opacity: 0.85
  }};
  var layout = {{
    paper_bgcolor: '#2f334d',
    plot_bgcolor: '#2f334d',
    font: {{color: '#c8d3f5', family: "'JetBrains Mono', monospace", size: 11}},
    title: {{text: 'P&L Distribution (%)', font: {{color: '#c099ff', size: 14}}}},
    margin: {{l: 50, r: 30, t: 40, b: 40}},
    xaxis: {{title: 'P&L %', gridcolor: '#3b4261'}},
    yaxis: {{title: 'Count', gridcolor: '#3b4261'}}
  }};
  Plotly.newPlot('pnl-distribution-chart', [trace], layout, {{responsive: true}});
}})();
</script>
</div>""")

    # ── 4. Hold Duration Distribution ──
    hold_bars_vals = [t.get("hold_bars", 0) for t in portfolio_trades if "hold_bars" in t]
    if hold_bars_vals:
        hold_json = json.dumps(hold_bars_vals)
        sections.append(f"""<div class="chart-container">
<div id="hold-duration-chart" style="width:100%;height:350px;"></div>
<script>
(function() {{
  var trace = {{
    x: {hold_json},
    type: 'histogram',
    marker: {{color: '#4fd6be', line: {{color: '#222436', width: 1}}}},
    opacity: 0.85
  }};
  var layout = {{
    paper_bgcolor: '#2f334d',
    plot_bgcolor: '#2f334d',
    font: {{color: '#c8d3f5', family: "'JetBrains Mono', monospace", size: 11}},
    title: {{text: 'Hold Duration Distribution', font: {{color: '#c099ff', size: 14}}}},
    margin: {{l: 50, r: 30, t: 40, b: 40}},
    xaxis: {{title: 'Hold Duration (bars)', gridcolor: '#3b4261'}},
    yaxis: {{title: 'Count', gridcolor: '#3b4261'}}
  }};
  Plotly.newPlot('hold-duration-chart', [trace], layout, {{responsive: true}});
}})();
</script>
</div>""")

    return "\n".join(sections)


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
    # Extract header data (support both original and pipeline key names)
    run_tag = pipeline_result.get("run_tag", pipeline_result.get("tag", "unknown"))
    timestamp = pipeline_result.get("timestamp", datetime.datetime.utcnow().isoformat())
    symbols = pipeline_result.get("symbols", [])
    symbols_str = ", ".join(symbols) if symbols else "—"
    s1_trials = pipeline_result.get("s1_trials", pipeline_result.get("stage1_trials", "—"))
    s2_trials = pipeline_result.get("s2_trials", pipeline_result.get("stage2_trials", "—"))
    hours = pipeline_result.get("duration_hours", pipeline_result.get("hours", "—"))

    # Build per-pair equity curves from trades if not provided
    if not pair_equity_curves and per_pair_trades:
        for sym, trades in per_pair_trades.items():
            curve = _build_equity_curve_from_trades(trades)
            if curve:
                pair_equity_curves[sym] = curve

    # Determine tier-X symbols to exclude from per-pair detail sections
    tier_assignments = pipeline_result.get("tier_assignments", {})
    pbo_results = pipeline_result.get("pbo_results", {})
    excluded_symbols: set = set()
    for sym, t in tier_assignments.items():
        pbo = pbo_results.get(sym, {})
        final_tier = pbo.get("final_tier", t.get("tier", ""))
        if final_tier == "X":
            excluded_symbols.add(sym)

    # Filter per-pair data to exclude tier-X
    filtered_pair_eq = {s: c for s, c in pair_equity_curves.items() if s not in excluded_symbols}
    filtered_s1_top = {s: d for s, d in s1_top_trials.items() if s not in excluded_symbols}
    filtered_s1_hist = {s: d for s, d in s1_history.items() if s not in excluded_symbols}

    # Render all sections
    hero = _render_hero_metrics(pipeline_result, eval_result, analysis)
    portfolio_eq = _render_portfolio_equity_curve(portfolio_equity_curve, timestamps)
    underwater = _render_underwater_chart(portfolio_equity_curve, timestamps)
    rolling_sharpe = _render_rolling_sharpe(portfolio_equity_curve, timestamps)
    concurrent = _render_concurrent_positions(portfolio_trades, timestamps)
    per_pair_tbl = _render_per_pair_table(pipeline_result, eval_result, analysis, excluded_symbols)
    per_pair_eq = _render_per_pair_equity_curves(filtered_pair_eq, timestamps)
    tier_tbl = _render_tier_table(pipeline_result)
    pbo_chart = _render_pbo_chart(pipeline_result)
    wf_eval = _render_wf_evaluation(eval_result, excluded_symbols)
    s1_params = _render_s1_params_table(pipeline_result)
    s1_bullet = _render_s1_bullet_chart(pipeline_result)
    s1_top = _render_s1_top_trials(filtered_s1_top)
    s1_hist = _render_s1_optimization_history(filtered_s1_hist)
    s2_params = _render_s2_params(pareto_front)
    pareto = _render_pareto_front(pareto_front)
    s2_hist = _render_s2_optimization_history(s2_history)
    pnl_contrib = _render_pnl_contribution(portfolio_trades, per_pair_trades)
    corr_heat = _render_correlation_heatmap(corr_matrix)
    monthly = _render_monthly_returns(portfolio_trades, timestamps)
    trade_analysis = _render_trade_analysis(portfolio_trades, per_pair_trades)
    long_short = _render_long_short_analysis(portfolio_trades)
    top_drawdowns = _render_top_drawdowns(portfolio_equity_curve, timestamps)
    streak_analysis = _render_streak_analysis(portfolio_trades, eval_result.get("portfolio_metrics", eval_result))
    trade_timing = _render_trade_timing(portfolio_trades)
    per_pair_monthly = _render_per_pair_monthly_heatmaps(per_pair_trades, excluded_symbols)

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

    divider_overview = '<div class="section-divider" id="sec-portfolio-overview"><h2>Portfolio Overview</h2></div>'
    divider_s1 = '<div class="section-divider" id="sec-stage1"><h2>Stage 1 — Per-Pair Optimization</h2></div>'
    divider_s2 = '<div class="section-divider" id="sec-stage2"><h2>Stage 2 — Portfolio Optimization</h2></div>'
    divider_pairs = '<div class="section-divider" id="sec-per-pair"><h2>Per-Pair Results</h2></div>'
    divider_trades = '<div class="section-divider" id="sec-trade-analysis"><h2>Trade Analysis</h2></div>'

    sidebar_html = """
<nav class="sidebar">
    <div class="nav-section">Portfolio Overview</div>
    <a href="#sec-hero">Hero Metrics</a>
    <a href="#sec-portfolio-eq">Equity Curve</a>
    <a href="#sec-underwater">Underwater</a>
    <a href="#sec-rolling-sharpe">Rolling Sharpe</a>
    <a href="#sec-concurrent">Concurrent Positions</a>
    <a href="#sec-monthly">Monthly Returns</a>
    <div class="nav-section">Trade Analysis</div>
    <a href="#sec-long-short">Long vs Short</a>
    <a href="#sec-top-drawdowns">Top Drawdowns</a>
    <a href="#sec-streaks">Win/Loss Streaks</a>
    <a href="#sec-trade-timing">Trade Timing</a>
    <a href="#sec-pnl-contrib">P&amp;L Contribution</a>
    <a href="#sec-correlation">Correlation</a>
    <a href="#sec-exit-reasons">Exit Reasons</a>
    <div class="nav-section">Per-Pair Results</div>
    <a href="#sec-per-pair">Performance Table</a>
    <a href="#sec-per-pair-eq">Equity Curves</a>
    <a href="#sec-per-pair-monthly">Monthly Heatmaps</a>
    <a href="#sec-tier-pbo">Tier &amp; PBO</a>
    <div class="nav-section">Stage 1</div>
    <a href="#sec-stage1">Parameters</a>
    <a href="#sec-s1-top-trials">Top Trials</a>
    <a href="#sec-s1-history">Optimization History</a>
    <div class="nav-section">Stage 2</div>
    <a href="#sec-stage2">Parameters</a>
    <a href="#sec-pareto">Pareto Front</a>
    <a href="#sec-s2-history">Optimization History</a>
</nav>
"""

    observer_js = """
<script>
(function() {
  var links = document.querySelectorAll('.sidebar a[href^="#"]');
  var sections = [];
  links.forEach(function(link) {
    var id = link.getAttribute('href').substring(1);
    var el = document.getElementById(id);
    if (el) sections.push({el: el, link: link});
  });
  if (!sections.length) return;
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      sections.forEach(function(s) {
        if (s.el === entry.target) {
          if (entry.isIntersecting) s.link.classList.add('active');
          else s.link.classList.remove('active');
        }
      });
    });
  }, {rootMargin: '-50% 0px -50% 0px'});
  sections.forEach(function(s) { observer.observe(s.el); });
})();
</script>"""

    body = f"""
<div class="report-layout">
{sidebar_html}
<main class="report-content">
{header_html}
<div id="sec-hero">{hero}</div>
{divider_overview}
<div id="sec-portfolio-eq">{portfolio_eq}</div>
{underwater}
{rolling_sharpe}
<div id="sec-concurrent">{concurrent}</div>
<div id="sec-monthly">{monthly}</div>
{divider_trades}
{long_short}
{top_drawdowns}
{streak_analysis}
{trade_timing}
<div id="sec-pnl-contrib">{pnl_contrib}</div>
<div id="sec-correlation">{corr_heat}</div>
<div id="sec-exit-reasons">{trade_analysis}</div>
{divider_pairs}
{per_pair_tbl}
<div id="sec-per-pair-eq">{per_pair_eq}</div>
{per_pair_monthly}
<div id="sec-tier-pbo">{tier_tbl}
{pbo_chart}
{wf_eval}</div>
{divider_s1}
{s1_params}
{s1_bullet}
<div id="sec-s1-top-trials">{s1_top}</div>
<div id="sec-s1-history">{s1_hist}</div>
{divider_s2}
{s2_params}
<div id="sec-pareto">{pareto}</div>
<div id="sec-s2-history">{s2_hist}</div>
</main>
</div>
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
{observer_js}
</body>
</html>"""

    return html


def save_html_report(path, **kwargs: Any) -> None:
    """Generate and save HTML report to file."""
    from pathlib import Path as _Path

    path = _Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = generate_html_report(**kwargs)
    path.write_text(html, encoding="utf-8")
