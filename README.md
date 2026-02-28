# MQE — Multi-pair Quant Engine

Multi-pair MACD/RSI funnel optimizer for crypto perpetual futures.
Hierarchical two-stage Optuna optimization: per-pair signal calibration (Stage 1) + portfolio-level tuning (Stage 2).

## Strategy Overview

MQE runs a **6-layer entry funnel** combined with a **5-level exit system** across multiple crypto pairs simultaneously with shared equity.

**Entry (all must pass for a signal to fire):**

1. MACD crossover — bullish/bearish trigger
2. RSI lookback window — oversold/overbought confirmation
3. HTF trend filter — higher-timeframe MACD alignment (4h/8h/1d)
4. BTC regime filter — global directional gate (longs only when BTC bullish)
5. ADX pre-filter — minimum trend strength
6. Correlation gate — prevents overconcentration in correlated positions

**Exit (first-match wins per bar):**

1. Hard stop — entry +/- `hard_stop_mult x ATR(14)`
2. Trailing stop — activates after 1.5xATR profit, trails at `trail_mult x ATR`
3. Time exit — close after `max_hold_bars`
4. Opposing signal — close or flip position
5. Portfolio heat — DD threshold emergency close (portfolio-level)

See `docs/strategy/` for full signal flow diagrams and parameter reference.

## Two-Stage Optimization

**Stage 1 — Per-pair TPE** (Optuna TPE sampler, AWF splits):
- 14 params per pair: MACD (fast/slow/signal), RSI (period/lower/upper/lookback), HTF trend (tf/strict), allow_flip, ADX threshold, exit params (trail_mult/hard_stop_mult/max_hold_bars)
- Objective: `log(1 + Calmar)` with trade-count ramp and Sharpe decay
- Runs in parallel via ProcessPoolExecutor

**Stage 2 — Portfolio NSGA-II** (multi-objective):
- 4 global params: max_concurrent, cluster_max, portfolio_heat, corr_gate_threshold
- 3 objectives: portfolio Calmar, worst-pair Calmar, negative overfit penalty
- Selects from Pareto front by best portfolio Calmar

## Default Pairs

| Pair | Tier | Cluster | BTC Corr | Slippage |
|------|------|---------|----------|----------|
| BTC/USDT | S | blue_chip | 1.00 | 6 bps |
| ETH/USDT | S | smart_contract_l1 | 0.76 | 9 bps |
| SOL/USDT | A+ | smart_contract_l1 | 0.75 | 15 bps |

Expandable to 15 pairs — see `config.py:PAIR_PROFILES` and `docs/strategy/Multi-pair_MACD-RSI_Funnel.md` for the full ranking.

## Project Structure

```
mqe/
├── src/mqe/
│   ├── config.py           # Symbols, costs, pair profiles, all constants
│   ├── optimize.py          # Pipeline orchestrator (fetch → S1 → S2 → save)
│   ├── stage1.py            # Per-pair TPE optimizer (AWF + log-Calmar)
│   ├── stage2.py            # Portfolio NSGA-II optimizer
│   ├── analyze.py           # Per-pair + portfolio health checks
│   ├── report.py            # Text report formatting
│   ├── notify.py            # Discord webhook notifications
│   ├── io.py                # JSON/CSV persistence
│   ├── core/
│   │   ├── strategy.py      # 6-layer entry funnel (MultiPairStrategy)
│   │   ├── backtest.py      # Numba trading loop + 5-level exit
│   │   ├── indicators.py    # MACD, RSI, ATR, ADX
│   │   ├── metrics.py       # Sharpe, Calmar, Sortino, Monte Carlo
│   │   └── portfolio.py     # Portfolio simulator (shared equity)
│   ├── data/
│   │   └── fetch.py         # Binance OHLCV via ccxt (paginated)
│   └── risk/
│       ├── sizing.py        # Inverse-vol + correlation haircut + OI/MC penalty
│       ├── correlation.py   # Rolling correlation matrix + cluster logic
│       └── regime.py        # BTC 4H regime filter
├── tests/
│   ├── unit/                # 14 test modules, 165 tests total
│   └── integration/         # Full pipeline smoke test
├── run.sh                   # CLI entry point (5 presets)
├── pyproject.toml           # Dependencies (uv)
└── .env.example             # DISCORD_WEBHOOK_RUNS
```

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -q

# Run optimization (test preset: 2 trials, 500 bars)
./run.sh            # interactive menu
./run.sh --preset test
./run.sh --preset main --tag my-run

# Custom run
uv run python -m mqe.optimize \
  --symbols BTC/USDT ETH/USDT SOL/USDT \
  --s1-trials 10000 --s2-trials 5000 \
  --hours 8760 --tag prod-v1
```

### run.sh Presets

| Preset | S1 Trials | S2 Trials | Hours | Purpose |
|--------|-----------|-----------|-------|---------|
| test | 2 | 2 | 500 | Smoke test |
| quick | 500 | 200 | 4380 | Quick iteration |
| main | 10000 | 5000 | 8760 | Production run (1yr) |
| full | 20000 | 10000 | 17520 | Full search (2yr) |
| custom | CLI args | CLI args | CLI args | Manual override |

## Configuration

All config in `src/mqe/config.py`. Key constants:

| Constant | Default | Description |
|----------|---------|-------------|
| `SYMBOLS` | BTC, ETH, SOL | Default optimization pairs |
| `STARTING_EQUITY` | $50,000 | Backtest starting capital |
| `FEE` | 0.075% | Trading fee per side |
| `MIN_TRADES_YEAR_HARD` | 30 | Minimum trades/year constraint |
| `DEFAULT_TRIALS_STAGE1` | 10,000 | Optuna trials per pair |
| `DEFAULT_TRIALS_STAGE2` | 5,000 | NSGA-II trials |
| `PURGE_GAP_BARS` | 50 | AWF purge gap between train/test |

## Environment Variables

```bash
# .env
FEE=0.00075
SLIPPAGE=0.0015
DISCORD_WEBHOOK_RUNS=https://discord.com/api/webhooks/...
```

## Dependencies

- Python 3.11+
- Optuna (TPE + NSGA-II)
- Numba (JIT backtest)
- ccxt (Binance data)
- numpy, pandas
- uv (package manager)
