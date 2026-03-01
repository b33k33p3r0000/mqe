# Multi-pair Quant Engine (MQE)

Systematic multi-pair algo trading optimizer — 6-layer Entry Funnel · Two-stage Optuna (TPE + NSGA-II) · Portfolio-level risk management

## Architecture

- **6-layer entry funnel:** MACD crossover · RSI lookback · HTF trend · BTC regime · ADX pre-filter · Correlation gate
- **5-level exit:** Hard stop (ATR) · Trailing stop · Time exit · Opposing signal · Portfolio heat
- **Two-stage optimization:** Per-pair TPE (14 params) → Portfolio NSGA-II (4 global params)
- **Risk management:** Inverse-vol sizing · Correlation haircut · Cluster limits · Portfolio heat circuit breaker
- **Validation:** Anchored Walk-Forward with purge gaps · Monte Carlo 1,000 shuffles

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

**Signal strength** (composite) = `|MACD histogram| / ATR + |RSI - 50| / 50` — used by portfolio for correlation gate ranking.

## Two-Stage Optimization

**Stage 1 — Per-pair TPE** (Optuna TPE sampler, AWF splits):
- 14 params per pair: MACD (fast/slow/signal), RSI (period/lower/upper/lookback), HTF trend (tf/strict), allow_flip, ADX threshold, exit params (trail_mult/hard_stop_mult/max_hold_bars)
- Objective: `log(1 + Calmar)` with trade-count ramp and Sharpe decay
- AWF splits: 3 splits (0.60/0.70, 0.70/0.80, 0.80/0.90) for data > 13,140 hours; 2 splits for shorter data
- Purge gap: 50 bars between train/test
- Runs in parallel via ProcessPoolExecutor; within each pair `n_jobs` threading (Numba releases GIL)
- Progress: `{SYMBOL}_progress.json` written every 500 trials atomically

**Stage 2 — Portfolio NSGA-II** (multi-objective):
- 4 global params: max_concurrent, cluster_max, portfolio_heat, corr_gate_threshold
- 3 objectives: portfolio Calmar, worst-pair Calmar, negative overfit penalty
- Selects from Pareto front by best portfolio Calmar

## Pairs (15 symbols)

| Pair | Tier | Cluster | BTC Corr | Slippage |
|------|------|---------|----------|----------|
| BTC/USDT | S | blue_chip | 1.00 | 6 bps |
| ETH/USDT | S | smart_contract_l1 | 0.76 | 9 bps |
| SOL/USDT | A+ | smart_contract_l1 | 0.75 | 15 bps |
| XRP/USDT | A | narrative | 0.70 | 15 bps |
| BNB/USDT | A | exchange | 0.84 | 12 bps |
| LINK/USDT | A | narrative | 0.78 | 18 bps |
| SUI/USDT | A- | smart_contract_l1 | 0.69 | 22 bps |
| DOT/USDT | B+ | smart_contract_l1 | 0.75 | 20 bps |
| ADA/USDT | B+ | smart_contract_l1 | 0.80 | 20 bps |
| NEAR/USDT | B | smart_contract_l1 | 0.73 | 25 bps |
| LTC/USDT | B | blue_chip | 0.84 | 15 bps |
| APT/USDT | B | smart_contract_l1 | 0.73 | 25 bps |
| ARB/USDT | B- | l2 | 0.76 | 30 bps |
| OP/USDT | B- | l2 | 0.76 | 30 bps |
| INJ/USDT | B- | narrative | 0.69 | 35 bps |

Core preset uses top 3 (BTC, ETH, SOL). Full preset uses all 15.

Per-tier search spaces exist — S-tier allows `allow_flip: (0,1)`, all other tiers force `allow_flip: (0,0)`. Lower tiers have progressively tighter parameter ranges.

## Project Structure

```
mqe/
├── src/mqe/
│   ├── config.py           # Symbols, costs, pair profiles, all constants
│   ├── optimize.py          # Pipeline orchestrator (fetch → S1 → S2 → save)
│   ├── stage1.py            # Per-pair TPE optimizer (AWF + log-Calmar)
│   ├── stage2.py            # Portfolio NSGA-II optimizer
│   ├── analyze.py           # Per-pair + portfolio health checks
│   ├── report.py            # Rich console + Markdown report formatting
│   ├── compare.py           # Cross-run side-by-side comparison
│   ├── monitor.py           # Live + historical run dashboard (Rich TUI)
│   ├── notify.py            # Discord webhook notifications
│   ├── io.py                # JSON/CSV persistence + fmt()
│   ├── core/
│   │   ├── strategy.py      # 6-layer entry funnel (MultiPairStrategy)
│   │   ├── backtest.py      # Numba JIT trading loop + 5-level exit
│   │   ├── indicators.py    # MACD (EWM), RSI (SMA-based), ATR, ADX
│   │   ├── metrics.py       # Sharpe, Calmar, Sortino, Monte Carlo
│   │   └── portfolio.py     # Portfolio simulator (shared equity)
│   ├── data/
│   │   └── fetch.py         # Local Parquet dataset first, Binance API fallback
│   └── risk/
│       ├── sizing.py        # Inverse-vol + correlation haircut + OI/MC penalty
│       ├── correlation.py   # Rolling correlation matrix + cluster logic
│       └── regime.py        # BTC 4H regime filter
├── tests/
│   ├── unit/                # 18 test modules, 267 tests total
│   └── integration/         # Full pipeline smoke tests
├── run.sh                   # CLI entry point (interactive menu + process management)
├── pyproject.toml           # Dependencies (uv)
└── .env.example             # DISCORD_WEBHOOK_RUNS
```

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -q

# Interactive menu (recommended)
./run.sh

# CLI with specific args
uv run python -m mqe.optimize \
  --symbols BTC/USDT ETH/USDT SOL/USDT \
  --s1-trials 10000 --s2-trials 5000 \
  --hours 8760 --tag prod-v1

# Background with tag
./run.sh --s1-trials 5000 --s2-trials 2000 --tag my-run

# Foreground mode
./run.sh --s1-trials 1000 --s2-trials 500 --fg
```

### run.sh Presets (interactive menu)

| Preset | S1 Trials | S2 Trials | Pairs | Purpose |
|--------|-----------|-----------|-------|---------|
| Test | 1,000 | 500 | 3 (core) | Smoke test |
| Quick | 5,000 | 2,000 | 3 (core) | Quick iteration |
| Main | 10,000 | 5,000 | 3 (core) | Production run |
| Full | 10,000 | 5,000 | 15 (all) | Full search across all clusters |
| Custom | user input | user input | user input | Manual override |

All presets use `--hours 8760` (~1yr) by default. All runs start in background by default (`--fg` for foreground).

### Process Management

```bash
./run.sh attach          # Attach to running/latest log
./run.sh kill            # Kill running MQE process
./run.sh logs            # List recent log files
./run.sh monitor         # Live dashboard for active run
./run.sh monitor --once  # Single snapshot of active run
```

### Other CLI Tools

```bash
uv run python -m mqe.monitor --live              # Live run dashboard
uv run python -m mqe.monitor --once              # Single snapshot
uv run python -m mqe.compare results/run1 results/run2  # Cross-run comparison
```

## Configuration

All config in `src/mqe/config.py`. Key constants:

| Constant | Default | Description |
|----------|---------|-------------|
| `SYMBOLS` | 15 pairs | All optimization pairs (core 3 as default preset) |
| `STARTING_EQUITY` | $100,000 | Backtest starting capital |
| `BACKTEST_POSITION_PCT` | 20% | Per-pair position size (Stage 1) |
| `FEE` | 0.06% (6 bps) | Trading fee per side (Binance VIP0 taker + buffer) |
| `DEFAULT_TRIALS_STAGE1` | 10,000 | Optuna trials per pair |
| `DEFAULT_TRIALS_STAGE2` | 5,000 | NSGA-II trials |
| `MIN_TRADES_YEAR_HARD` | 30 | Minimum trades/year constraint |
| `MIN_TRADES_TEST_HARD` | 5 | Minimum trades in test set |
| `PURGE_GAP_BARS` | 50 | AWF purge gap between train/test |
| `MONTE_CARLO_SIMULATIONS` | 1,000 | MC shuffle count |
| `ATR_PERIOD` | 14 | ATR lookback for exits |
| `TRAILING_ACTIVATION_MULT` | 1.5 | ATR profit to activate trailing stop |
| `LONG_ONLY` | False | Longs and shorts enabled |

### Portfolio Controls (Stage 2 Optuna overrides defaults)

| Constant | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MAX_CONCURRENT` | 5 | Max open positions simultaneously |
| `DEFAULT_CLUSTER_MAX` | 2 | Max positions per cluster |
| `DEFAULT_PORTFOLIO_HEAT` | 5% | Portfolio DD threshold for emergency close |
| `CORRELATION_GATE_THRESHOLD` | 0.75 | Correlation threshold for gate |
| `POSITION_MIN_PCT` / `MAX` | 5% / 20% | Position size clamp (inv-vol sizing) |
| `CORRELATION_HAIRCUT_FACTOR` | 0.90 | 10% size reduction per correlated open pair |
| `OI_MC_DANGER_THRESHOLD` | 6% | OI/MC ratio danger zone |

## Data Pipeline

- **Primary source:** Local Parquet dataset at `~/projects/dataset/data/{SYMBOL}/{tf}.parquet`
- **Fallback:** ccxt Binance API with pagination (1,500 rows/call, 5 retries, safety cap 200,000 rows)
- Always fetches BTC/USDT even if not in symbol list (needed for regime filter)
- Timeframes loaded: 1h (base), 4h, 8h, 1d (trend/regime)

## Environment Variables

```bash
# .env
FEE=0.0006                    # 6 bps (default in config.py)
SLIPPAGE=0.0015                # 15 bps default (per-pair map in config.py)
DISCORD_WEBHOOK_RUNS=https://discord.com/api/webhooks/...
```

## Dependencies

- Python 3.11+
- Optuna (TPE + NSGA-II)
- Numba (JIT backtest)
- ccxt (Binance data)
- numpy, pandas, pyarrow
- rich (TUI monitor/reports)
- uv (package manager)
