# Multi-pair Quant Engine (MQE)

Systematic multi-pair algo trading optimizer — 6-layer Entry Funnel · Two-stage Optuna (CMA-ES + NSGA-II) · Portfolio-level risk management

## Pipeline Overview

```
Data (Local Parquet / Binance OHLCV via ccxt)
  │
  ├── 1H bary (primary, per pair)
  ├── 4H / 8H / 1D bary (HTF trend filter + BTC regime)
  │
  ▼
═══════════════════════════════════════════
  STAGE 1 — Per-pair CMA-ES (parallel)
═══════════════════════════════════════════
  │
  Signály (strategy.py)
  │  Layer 1: MACD crossover
  │  Layer 2: RSI lookback window
  │  Layer 3: HTF trend filter
  │  Layer 4: BTC regime filter
  │  Layer 5: ADX pre-filter
  │  → buy_signal[], sell_signal[], atr[], signal_strength[]
  │
  Backtest (backtest.py, Numba JIT)
  │  5-level exit, fixed 20% sizing, fees + slippage
  │  → trades[], equity_curve[]
  │
  AWF Splity (stage1.py)
  │  3-5 splitů s rostoucím train window
  │  Purge gap 50 barů
  │  Hard constraints (60 trades/yr, 5 trades test)
  │  S1 trains within WF ceiling (70-80% of data)
  │
  Objective (stage1.py)
  │  log(1 + Calmar) × sharpe_decay
  │  Final score = průměr přes splity
  │
  Optuna CMA-ES + TPE warmup, 15 params, N trials per pair
  │  ProcessPoolExecutor → parallel across pairs
  │  → best_params per pair
  │
  ▼
═══════════════════════════════════════════
  WALK-FORWARD EVALUATION (OOS windows)
═══════════════════════════════════════════
  │
  OOS data (beyond S1 ceiling)
  │  Split into 1-3 evaluation windows
  │  Per-pair backtest with S1 best params
  │  → median OOS Sharpe, degradation ratio, consistency
  │
  Enhanced Tiering (3-signal)
  │  Signal 1: Absolute quality (median OOS Sharpe)
  │  Signal 2: Degradation guard (S1/OOS ratio)
  │  Signal 3: Consistency (Sharpe std + worst window)
  │  → Tier A/B/C/X per pair (X = excluded)
  │
  ▼
═══════════════════════════════════════════
  STAGE 2 — Portfolio NSGA-II
═══════════════════════════════════════════
  │
  Portfolio Sim (portfolio.py, pure Python)
  │  Shared equity across all pairs
  │  Layer 6: Correlation gate
  │  Cluster throttle, portfolio heat exit
  │  Inverse-vol sizing + haircuts
  │  Tier multipliers (A=1.0, B=0.6, C=0.25, X=excluded)
  │  → portfolio trades[], equity_curve[]
  │
  Multi-objective (stage2.py)
  │  obj1: portfolio Calmar (maximize)
  │  obj2: worst-pair Calmar (maximize)
  │  obj3: -overfit_penalty (maximize)
  │  → Pareto front → best by portfolio Calmar
  │
  4 global params, N trials
  │  → best_portfolio_params
  │
  ▼
Výsledky
  │  Full portfolio backtest
  │  Per-pair + portfolio metrics
  │  → pipeline_result.json, trades CSV, report.md
```

---

## Entry Logic (6-Layer Funnel)

Vstup vyžaduje průchod **všemi 6 vrstvami**. Layers 1-5 se vyhodnocují v Stage 1 backtestu, Layer 6 v Stage 2 portfolio simu.

```
LONG  = MACD bullish cross
        AND RSI oversold (s lookback)
        AND HTF bullish
        AND BTC regime bullish
        AND ADX > threshold
        AND correlation gate pass

SHORT = MACD bearish cross
        AND RSI overbought (s lookback)
        AND HTF bearish
        AND BTC regime bearish
        AND ADX > threshold
        AND correlation gate pass
```

### Layer 1: MACD Crossover (Trigger)

Generuje vstupní signál na 1H datech.

```
ema_fast    = EMA(close, span=macd_fast)      # macd_fast: float 1.0-20.0
ema_slow    = EMA(close, span=macd_slow)      # macd_slow: int 10-45
macd_line   = ema_fast - ema_slow
signal_line = EMA(macd_line, span=macd_signal) # macd_signal: int 3-15

bullish_cross = (macd_prev <= signal_prev) AND (macd_curr > signal_curr)
bearish_cross = (macd_prev >= signal_prev) AND (macd_curr < signal_curr)
```

Hard constraint: `macd_slow - macd_fast >= 5` (porušení → TrialPruned).

### Layer 2: RSI Lookback Window (Filter)

RSI je SMA-based (ne Wilder's EMA).

```
delta    = close.diff()
avg_gain = SMA(max(delta, 0), rsi_period)      # rsi_period: int 3-30
avg_loss = SMA(abs(min(delta, 0)), rsi_period)
RSI      = 100 - (100 / (1 + avg_gain / avg_loss))

rsi_oversold   = rolling_max(RSI < rsi_lower, window=rsi_lookback + 1)
rsi_overbought = rolling_max(RSI > rsi_upper, window=rsi_lookback + 1)
```

`rsi_lookback` (int 1-4) = "paměť" — `lookback=1` vyžaduje RSI v zóně nyní/předchozí bar, `lookback=4` stačí v posledních 4h.

### Layer 3: HTF Trend Filter (Guard)

Filtruje vstupy proti dominantnímu trendu. Používá **stejné MACD params** jako Layer 1.

```
# Výpočet na vyšším timeframe (trend_tf ∈ {4h, 8h, 1d})
htf_macd, htf_signal = MACD(htf_close, macd_fast, macd_slow, macd_signal)
htf_bullish = (htf_macd > htf_signal)
```

HTF signál se alignuje na 1H bary přes timestamp binary search. `trend_strict=1` (vždy zapnuto).

### Layer 4: BTC Regime Filter (Global Gate)

Globální directional gate — kontroluje BTC 4H MACD pro celý trh.

```
btc_4h_macd, btc_4h_signal = MACD(btc_4h_close, ...)
LONG:  vyžaduje btc_bullish (celý trh v uptrend módu)
SHORT: vyžaduje btc_bearish (celý trh v downtrend módu)
```

Aplikuje se na VŠECHNY páry (ne jen BTC). Vyhodnocuje se vektorizovaně přes `regime.py`.

### Layer 5: ADX Pre-filter (Trend Strength)

```
adx = ADX(high, low, close, period=14)
if adx[bar] < adx_threshold:   # adx_threshold: float 15.0-30.0
    → entry blocked
```

### Layer 6: Correlation Gate (Portfolio-Level, Stage 2 only)

Prevence overkoncentrace v korelovaných pozicích.

```
Před otevřením pozice na páru X:
1. Spočítej kolik otevřených pozic má |corr(X, open)| > corr_gate_threshold
2. Pokud count > 3: vyžaduj signal_strength > 1.5 (vyšší laťka)
   jinak:           vyžaduj signal_strength > 1.0 (normální laťka)
3. Rank kandidáty podle signal_strength, vezmi top N do max_concurrent
```

Signal strength: `|MACD_line - signal_line| / ATR + |RSI - 50| / 50`

---

## Exit Logic (5-Level Priority)

Kontroluje 5 úrovní **v pevném pořadí** per bar. První shoda ukončí pozici.

```
1. Hard Stop         (entry ± hard_stop_mult × ATR)
2. Trailing Stop     (aktivuje se po 1.5×ATR zisku, trails at trail_mult × ATR)
3. Time Exit         (max_hold_bars dosaženo)
4. Opposing Signal   (opačný 3-layer signál, min 2 bary hold)
5. Portfolio Heat    (equity DD > threshold → close worst position, Stage 2 only, po individuálních exitech)
```

### 1. Hard Stop (Emergency)

```
LONG:  exit if low  <= entry_price - hard_stop_mult × ATR(14)
SHORT: exit if high >= entry_price + hard_stop_mult × ATR(14)
```

### 2. Trailing Stop (Profit Protection)

Aktivuje se po dosažení `1.5 × ATR` zisku:

```
LONG:  trail_high = max(trail_high, high)
       exit if close < trail_high - trail_mult × ATR

SHORT: trail_low = min(trail_low, low)
       exit if close > trail_low + trail_mult × ATR
```

### 3. Time Exit

```
if bars_held >= max_hold_bars → exit at close
```

### 4. Opposing Signal Exit

```
allow_flip=0 (default): close → FLAT → čekat na nový entry
allow_flip=1:           close → okamžitě otevřít opačný směr
```

### 5. Portfolio Heat Exit (Stage 2 only)

Kontroluje se na START každého baru, PŘED signal processing:

```
if current_dd > portfolio_heat:
    → close worst-performing open position (lowest unrealized PnL)
```

---

## Two-Stage Optimization

### Stage 1 — Per-pair CMA-ES (AWF splits)

Optuna CMA-ES sampler with TPE warmup. 15 params per pair.

- **S1 trains within WF ceiling** (70% for 3yr+ data, 75% for 1.5-3yr, 80% for shorter) — remaining data reserved for OOS evaluation
- AWF splits: 5 splits (>= 3yr), 3 splits (>= 1.5yr), 2 splits (shorter) — within the ceiling
- Purge gap: 50 bars between train/test
- Active pruning: `trial.report()` + `should_prune()` after each split (SuccessiveHalving, reduction_factor=2)
- Runs in parallel via ProcessPoolExecutor; within each pair `n_jobs` threading (Numba releases GIL)
- Progress: `{SYMBOL}_progress.json` written every 100 trials atomically

**Objective:** `log(1 + Calmar) × sharpe_decay` — no soft trade ramp (hard constraint only: 60 trades/yr).

**Data-adaptive trial counts:** <2.5yr = 35k, >=2.5yr = 50k, >=4.5yr = 65k trials per pair.

### Walk-Forward Evaluation (between S1 and S2)

After S1, each pair is evaluated on OOS data beyond the S1 ceiling:

1. **OOS window backtests** — data beyond ceiling split into 1-3 windows, backtest with S1 best params
2. **Enhanced tiering (3-signal):**
   - Absolute quality: median OOS Sharpe (A >= 1.5, B >= 0.5, C >= 0.0)
   - Degradation guard: S1/OOS Sharpe ratio (A >= 0.5, B >= 0.3)
   - Consistency: worst window Sharpe (A >= 0.5, B >= -0.2, C >= -1.0)
3. **Tier assignment:** A (1.0x), B (0.6x), C (0.25x), X (excluded)
4. **Post-eval gate:** full-data eval Sharpe < 0 → demote to X

### Stage 2 — Portfolio NSGA-II (multi-objective)

4 global params, 3 objectives, Pareto front selection by best portfolio Calmar.

| Param | Range | Description |
|-------|-------|-------------|
| `max_concurrent` | min(3,N)-min(N,10) | Max simultaneous positions |
| `cluster_max` | 1-3 | Max per cluster |
| `portfolio_heat` | 0.15-0.50 | DD threshold for emergency close |
| `corr_gate_threshold` | 0.50-0.80 | Correlation gate strictness |

---

## AWF (Anchored Walk-Forward)

Anchored = train window ROSTE (kotvený ke startu). Test windows se nepřekrývají.

```
Split 1: Train [0% ──── 60%] ··purge·· Test [60.x% ── 70%]
Split 2: Train [0% ──────── 70%] ··purge·· Test [70.x% ── 80%]
Split 3: Train [0% ──────────── 80%] ··purge·· Test [80.x% ── 90%]
```

| Data délka | Splity | Train/Test |
|------------|--------|------------|
| >= 3yr (>= 26,280h) | 5 | 50-100% train, ~10% test each |
| >= 1.5yr (>= 13,140h) | 3 | 60/70/80% train, ~10% test each |
| < 1.5yr (>= 4,000h) | 2 | 70/85% train, 15% test |
| < 4,000h | Error | — |

**Hard Constraints** (trial = 0.0 pokud porušeno):

| Constraint | Hodnota |
|------------|---------|
| `MIN_TRADES_YEAR_HARD` | 60 trades/rok (train set) |
| `MIN_TRADES_TEST_HARD` | 5 trades (každý test split) |

---

## Objective Functions

### Stage 1: Log Calmar (per-pair)

```
score = log(1 + raw_calmar) × sharpe_decay

kde:
  raw_calmar     = max(0, annual_return / max(max_dd, 0.05))
  sharpe_decay   = 1 / (1 + 0.3 × (sharpe - 3.0))   # only if sharpe > 3.0
```

Anti-gaming mechanismy:

| Mechanismus | Co brání |
|-------------|----------|
| DD floor 5% | Minimalizace DD na ~0% |
| Log komprese | Extrémní Calmar hodnoty |
| Sharpe decay | Přeoptimalizované params (nad Sharpe 3.0) |
| AWF průměr | Overfitting na jedno období |
| Hard constraints | Příliš málo obchodů (60/yr train, 5/split test) |

### Stage 2: Multi-Objective NSGA-II (portfolio)

```
obj1 = portfolio_calmar         # maximize
obj2 = worst_pair_calmar        # maximize (robustness)
obj3 = -overfit_penalty         # maximize (minimize overfit)
```

Overfit penalty: penalizuje extreme params (max_concurrent <= 1, portfolio_heat < 0.035, corr_gate < 0.55).

---

## Per-pair Backtest Engine (Stage 1)

### Position Sizing

```
capital_at_entry = equity × 0.20     # 20% equity
position_size    = capital_at_entry / entry_price
```

Start equity: $100,000.

### Trading Costs

Fee: 6 bps per side (Binance VIP0 taker + buffer). Slippage per pair (asymetrický):

| Pair | Slippage | Tier |
|------|----------|------|
| BTC/USDT | 6 bps | S |
| ETH/USDT | 9 bps | S |
| SOL/USDT | 15 bps | A+ |
| XRP/USDT | 15 bps | A |
| BNB/USDT | 12 bps | A |
| LINK/USDT | 18 bps | A |
| SUI/USDT | 22 bps | A- |
| ADA/USDT | 20 bps | B+ |
| DOGE/USDT | 15 bps | B+ |
| NEAR/USDT | 25 bps | B |
| APT/USDT | 25 bps | B |
| FIL/USDT | 25 bps | B |
| ARB/USDT | 30 bps | B- |
| OP/USDT | 30 bps | B- |
| INJ/USDT | 35 bps | B- |

### Per-Bar Flow (Numba JIT)

```
Bar N:
  1. MÁ POZICI?
     a. Check hard stop (low/high vs entry ± ATR×mult)
     b. Check trailing stop (if activated)
     c. Check time exit (bars_held ≥ max_hold_bars)
     d. Check opposing signal exit (if bars_held ≥ 2)
        → if exit & allow_flip=1: okamžitě otevři opačný

  2. NEMÁ POZICI?
     a. if buy_signal & all layers pass: OPEN LONG
     b. elif sell_signal & all layers pass: OPEN SHORT

Konec dat:
  → CLOSE jakákoli otevřená pozice, reason="force_close"
```

---

## Portfolio Simulator (Stage 2)

`portfolio.py:PortfolioSimulator` — Python loop (ne Numba) přes všechny páry se sdíleným equity.

### Simulation Loop

```
For each bar (1H):
    ├── 1. Check SIGNAL EXITS for each open position
    │   Per-pair exit logic (hard stop, trailing, time, opposing)
    │
    ├── 2. Check PORTFOLIO HEAT exit (after individual exits)
    │   If equity DD > portfolio_heat → close worst position
    │
    ├── 3. Collect NEW ENTRY signals
    │   Check: pair already open → skip, max_concurrent → skip, cluster_max → skip
    │
    ├── 4. Apply CORRELATION GATE (Layer 6)
    │   Count correlated open positions → gate logic → rank by signal_strength
    │
    └── 5. OPEN NEW POSITIONS
        compute_position_size() → inverse-vol + haircuts × tier_multiplier
```

### Cluster Throttle

| Cluster | Páry | Max Concurrent |
|---------|------|----------------|
| blue_chip | BTC | 2 |
| smart_contract_l1 | ETH, SOL, ADA, NEAR, APT, SUI | 2 |
| l2 | ARB, OP | 1 |
| exchange | BNB | 1 |
| narrative | XRP, LINK, INJ | 2 |
| meme | DOGE | 1 |
| storage | FIL | 1 |

### Position Sizing (Inverse-Vol)

```
compute_position_size(symbol, open_pairs, equity, atr_dict, corr_dict)
    ├── Step 1: Base weight = 1 / atr_1h_pct
    ├── Step 2: Normalize across all active symbols (weights sum to 1.0)
    ├── Step 3: Correlation haircut (weight *= 0.90 per correlated pair with |corr| > 0.75)
    ├── Step 4: OI/MC danger penalty (weight *= 0.70 if OI/MC > 6%)
    ├── Step 5: Tier multiplier (A=1.0, B=0.6, C=0.25, X=excluded)
    └── Step 6: Clip to [5%, 20%] of equity
```

### Stage 1 vs Stage 2 Differences

| Aspekt | Stage 1 (backtest.py) | Stage 2 (portfolio.py) |
|--------|----------------------|----------------------|
| Scope | Jeden pár | Všechny páry simultánně |
| Equity | Nezávislé per pár | Sdílené across all pairs |
| JIT | Numba-accelerated | Pure Python loop |
| Sizing | Fixed 20% of equity | Inverse-vol + haircuts |
| Layer 6 | Neaplikuje se | Correlation gate aktivní |
| Cluster | Neaplikuje se | Cluster throttle aktivní |
| Heat exit | Neaplikuje se | Portfolio heat exit aktivní |
| Tiers | Neaplikuje se | Tier multipliers aktivní |

---

## Metrics

### Primary

| Metrika | Výpočet | Annualizace |
|---------|---------|-------------|
| **sharpe_equity** | Daily equity returns | sqrt(365) — **PRIMARY** |
| **calmar** | Annual return / \|max_dd\| | Annualizovaný return |
| **max_drawdown** | Peak-to-trough na equity curve | — |

### Secondary

| Metrika | Výpočet |
|---------|---------|
| **sortino** | Daily equity returns, downside vol only, sqrt(365) |
| **win_rate** | count(pnl > 0) / total_trades × 100 |
| **profit_factor** | gross_profit / gross_loss |
| **trades_per_year** | total_trades / (days / 365.25) |

---

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
| ADA/USDT | B+ | smart_contract_l1 | 0.80 | 20 bps |
| DOGE/USDT | B+ | meme | 0.65 | 15 bps |
| NEAR/USDT | B | smart_contract_l1 | 0.73 | 25 bps |
| APT/USDT | B | smart_contract_l1 | 0.73 | 25 bps |
| FIL/USDT | B | storage | 0.65 | 25 bps |
| ARB/USDT | B- | l2 | 0.76 | 30 bps |
| OP/USDT | B- | l2 | 0.76 | 30 bps |
| INJ/USDT | B- | narrative | 0.69 | 35 bps |

Removed (persistently unviable WF): LTC, ATOM, UNI, AVAX, DOT.

Per-tier search spaces — `allow_flip` is disabled for ALL tiers `(0,0)`. Lower tiers have progressively tighter parameter ranges.

## Project Structure

```
mqe/
├── src/mqe/
│   ├── config.py           # Symbols, costs, pair profiles, all constants
│   ├── optimize.py          # Pipeline orchestrator (fetch → S1 → WF eval → S2 → save)
│   ├── stage1.py            # Per-pair CMA-ES optimizer (AWF + log-Calmar)
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
│   # ~470 tests total
├── run.sh                   # CLI entry point (interactive menu + process management)
├── pyproject.toml           # Dependencies (uv)
├── NOTES.md                 # Session notes
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
  --s2-trials 5000 --hours 26280 --tag prod-v1

# Resume from Stage 2 (reuse existing S1 results)
uv run python -m mqe.optimize --resume results/20260304_194135 --s2-trials 10000

# Background with tag
./run.sh --s2-trials 2000 --tag my-run

# Foreground mode
./run.sh --s2-trials 500 --fg
```

### run.sh Presets (interactive menu)

| Preset | S1 Trials | S2 Trials | Pairs | Purpose |
|--------|-----------|-----------|-------|---------|
| Test | adaptive | 500 | 3 (core) | Smoke test |
| Standard | adaptive | 5,000 | 15 (all) | Normal run |
| Full | adaptive | 10,000 | 15 (all) | Max quality |
| Custom | adaptive | user input | user input | Manual override |

S1 trials are **data-adaptive**: <2.5yr = 35k, >=2.5yr = 50k, >=4.5yr = 65k trials per pair.
All presets use `--hours 26280` (~3yr) by default. All runs start in background by default (`--fg` for foreground).

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

All config in `src/mqe/config.py`.

### Stage 1 Parameters (15 per pair, per-tier ranges)

| Param | Typ | S-tier Range | Default |
|-------|-----|-------------|---------|
| `macd_fast` | float | 1.0-20.0 | 10.5 |
| `macd_slow` | int | 10-45 | 27 |
| `macd_signal` | int | 3-15 | 9 |
| `rsi_period` | int | 3-30 | 14 |
| `rsi_lower` | int | 20-40 | 30 |
| `rsi_upper` | int | 60-80 | 70 |
| `rsi_lookback` | int | 1-4 | 3 |
| `trend_tf` | cat | 4h, 8h, 1d | 8h |
| `trend_strict` | int | 1 (fixed) | 1 |
| `allow_flip` | int | 0-1 (S only) | 0 |
| `adx_threshold` | float | 15.0-30.0 | 20.0 |
| `trail_mult` | float | 2.0-4.0 | 3.0 |
| `hard_stop_mult` | float | 1.5-4.0 | 2.5 |
| `max_hold_bars` | int | 48-168 | 168 |
| `vol_sensitivity` | float | 0.3-2.5 | 1.0 |

Lower tiers have progressively tighter ranges (e.g. B-tier: macd_fast 1.0-12.0, hard_stop_mult 1.5-2.0).

### Key Constants

| Constant | Default | Description |
|----------|---------|-------------|
| `STARTING_EQUITY` | $100,000 | Backtest starting capital |
| `BACKTEST_POSITION_PCT` | 20% | Per-pair position size (Stage 1) |
| `FEE` | 0.06% (6 bps) | Trading fee per side |
| `TRIALS_SHORT/MEDIUM/LONG` | 35k/50k/65k | Adaptive S1 trials |
| `DEFAULT_TRIALS_STAGE2` | 10,000 | NSGA-II trials |
| `MIN_TRADES_YEAR_HARD` | 60 | Minimum trades/year constraint |
| `MIN_TRADES_TEST_HARD` | 5 | Minimum trades in test set |
| `PURGE_GAP_BARS` | 50 | AWF purge gap between train/test |
| `MIN_WARMUP_BARS` | 200 | Bars skipped at start |
| `ATR_PERIOD` | 14 | ATR/ADX calculation window |
| `TRAILING_ACTIVATION_MULT` | 1.5 | ATR profit to activate trailing |
| `MIN_HOLD_BARS` | 2 | Min bars before signal exit |
| `MONTE_CARLO_SIMULATIONS` | 1,000 | MC shuffle count |
| `LONG_ONLY` | False | Longs and shorts enabled |

### Portfolio Controls (Stage 2 Optuna overrides defaults)

| Constant | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MAX_CONCURRENT` | 5 | Max open positions |
| `DEFAULT_CLUSTER_MAX` | 2 | Max positions per cluster |
| `DEFAULT_PORTFOLIO_HEAT` | 5% | Portfolio DD threshold |
| `CORRELATION_GATE_THRESHOLD` | 0.75 | Correlation threshold |
| `POSITION_MIN_PCT` / `MAX` | 5% / 20% | Position size clamp |
| `CORRELATION_HAIRCUT_FACTOR` | 0.90 | 10% size reduction per correlated pair |
| `OI_MC_DANGER_THRESHOLD` | 6% | OI/MC ratio danger zone |

### Tier System

| Tier | Eval Sharpe | Sizing mult | Effect |
|------|-------------|-------------|--------|
| A | >= 1.5 | 1.0x | Full allocation |
| B | 0.5 - 1.5 | 0.6x | Reduced allocation |
| C | 0.0 - 0.5 | 0.25x | Minimal allocation |
| X | < 0.0 | 0.0x | Excluded from trading |

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

## TODO — Future Improvements

### Sizing: inverse-vol → GARCH-based weighting
Current portfolio sizing uses backward-looking `1/ATR` for inverse-volatility weighting. After GARCH dynamic sizing (multiplicative, variant A) is tuned and validated, revisit replacing `1/ATR` with `1/GARCH_conditional_vol` (variant B) in `sizing.py` for forward-looking allocation. Requires stable GARCH metrics across multiple runs first.

### Pipeline logic audit
Review the ordering and impact of each pipeline step (S1 → signals → WF eval → tiering → PBO → per-pair eval → post-eval gate → S2 → final eval). Document: which steps are load-bearing for strategy quality vs cosmetic/diagnostic, what is the real impact of each step on final portfolio metrics, and whether the current ordering is optimal or if steps should be reordered/merged.

---

## Dependencies

- Python 3.11+
- Optuna (CMA-ES + NSGA-II) + cmaes
- Numba (JIT backtest)
- ccxt (Binance data)
- numpy, pandas, pyarrow
- rich (TUI monitor/reports)
- uv (package manager)
