# Parameter Reference

## Stage 1 — Per-pair Parameters (14 total)

Optimized independently per symbol via Optuna TPE.

### MACD (Layer 1 + Layer 3)

| Param | Type | Range | Default | Effect |
|-------|------|-------|---------|--------|
| `macd_fast` | float | 1.0 – 20.0 | 10.5 | Fast EMA period. Lower = more responsive, more signals, more noise |
| `macd_slow` | int | 10 – 45 | 27 | Slow EMA period. Constraint: `slow - fast >= 5` (pruned otherwise) |
| `macd_signal` | int | 3 – 15 | 9 | Signal line smoothing. Lower = faster crossovers |

**Interactions:**
- `macd_fast` close to 1.0 = near-price tracking, extremely reactive. Common in selective mode (allow_flip=0).
- `macd_slow - macd_fast` gap determines sensitivity. Larger gap = fewer but higher-conviction crossovers.
- Same params are used for HTF trend filter (Layer 3) on the pair's higher-timeframe data.

### RSI (Layer 2)

| Param | Type | Range | Default | Effect |
|-------|------|-------|---------|--------|
| `rsi_period` | int | 3 – 30 | 14 | RSI calculation period. Lower = more reactive |
| `rsi_lower` | int | 20 – 40 | 30 | Oversold threshold for buy confirmation |
| `rsi_upper` | int | 60 – 80 | 70 | Overbought threshold for sell confirmation |
| `rsi_lookback` | int | 1 – 4 | 3 | Bars to look back for RSI condition. `rsi_lookback=3` means RSI must have been oversold at any point in the last 4 bars (current + 3 back) |

**Interactions:**
- `rsi_period=3` (floor) is intentional — Optuna gravitates to reactive RSI. Not edge concern.
- `rsi_lookback=4` (max) is consistent across runs — strategy prefers longer memory.
- Wider `rsi_lower/rsi_upper` spread = more selective (fewer signals but higher quality).

### HTF Trend (Layer 3)

| Param | Type | Range | Default | Effect |
|-------|------|-------|---------|--------|
| `trend_tf` | categorical | 4h, 8h, 1d | 8h | Higher timeframe for trend confirmation |
| `trend_strict` | int | 1 (fixed) | 1 | Always on. MACD on HTF must align with entry direction |

**Note:** `trend_strict` is fixed at 1 via `trial.suggest_int("trend_strict", 1, 1)`. Not actually optimized.

### Allow Flip (Layer 4 interaction)

| Param | Type | Range | Default | Effect |
|-------|------|-------|---------|--------|
| `allow_flip` | int | 0 (fixed) | 0 | 0=selective (close on opposing signal), 1=always-in (flip to opposite) |

**Note:** Fixed at 0 via `trial.suggest_int("allow_flip", 0, 0)`. Can be overridden per-run.

### ADX (Layer 5)

| Param | Type | Range | Default | Effect |
|-------|------|-------|---------|--------|
| `adx_threshold` | float | 15.0 – 30.0 | 20.0 | Minimum ADX(14) for entry. Higher = only strong trends |

**Effect:** Filters out range-bound / choppy market bars. ADX < 20 = no clear trend. ADX > 25 = strong trend.

### Exit Params

| Param | Type | Range | Default | Effect |
|-------|------|-------|---------|--------|
| `trail_mult` | float | 2.0 – 4.0 | 3.0 | Trailing stop distance in ATR multiples. Higher = wider trailing |
| `hard_stop_mult` | float | 1.5 – 3.0 | 2.5 | Hard stop distance in ATR multiples. Higher = more room |
| `max_hold_bars` | int | 48 – 168 | 168 | Max bars before time exit. 48=2 days, 168=7 days |

**Interactions:**
- `hard_stop_mult < trail_mult` is typical — hard stop is tighter than trailing stop.
- Trailing activates only after 1.5×ATR profit (`TRAILING_ACTIVATION_MULT` in config, not optimized).
- `max_hold_bars` acts as a safety net for positions that neither trail nor stop out.

---

## Stage 2 — Global Portfolio Parameters (4 total)

Optimized via NSGA-II multi-objective after Stage 1 params are fixed.

| Param | Type | Range | Default | Effect |
|-------|------|-------|---------|--------|
| `max_concurrent` | int | 2 – min(n_pairs, 8) | 5 | Max simultaneous open positions |
| `cluster_max` | int | 1 – 3 | 2 | Max positions per correlation cluster |
| `portfolio_heat` | float | 0.03 – 0.10 | 0.05 | DD threshold — close worst position if portfolio DD exceeds this |
| `corr_gate_threshold` | float | 0.60 – 0.90 | 0.75 | Correlation gate — higher = stricter filtering |

**Interactions:**
- `max_concurrent=2` with 3 pairs = very restrictive, may overfit to best 2 pairs.
- `portfolio_heat < 0.035` = too tight for crypto volatility, penalized in objective.
- `corr_gate_threshold < 0.65` = nearly all pairs pass the gate (no real filtering).

---

## Fixed Constants (not optimized)

These are in `config.py` and affect strategy behavior but are not in Optuna search space.

| Constant | Value | Where used | Description |
|----------|-------|------------|-------------|
| `ATR_PERIOD` | 14 | ADX, ATR, exits | ATR calculation window |
| `TRAILING_ACTIVATION_MULT` | 1.5 | backtest.py | ATR profit needed before trailing activates |
| `MIN_HOLD_BARS` | 2 | backtest.py | Min bars before opposing signal exit allowed |
| `BACKTEST_POSITION_PCT` | 0.25 | backtest.py | Per-trade position size (Stage 1 only) |
| `FEE` | 0.00075 | backtest.py | Trading fee per side |
| `SLIPPAGE_MAP` | per-pair | backtest.py | BTC=6bps, ETH=9bps, SOL=15bps |
| `STARTING_EQUITY` | 50,000 | everywhere | Backtest starting capital |
| `MIN_WARMUP_BARS` | 200 | backtest.py | Bars skipped at start for indicator warmup |
| `PURGE_GAP_BARS` | 50 | stage1.py | Gap between AWF train/test splits |
| `MIN_TRADES_YEAR_HARD` | 30 | stage1.py | Minimum trades/year for valid trial |
| `MIN_TRADES_TEST_HARD` | 5 | stage1.py | Minimum trades in test fold |

---

## Sizing Parameters (portfolio.py)

Position sizing in Stage 2 uses inverse-vol with haircuts. Not optimized — computed from data.

| Constant | Value | Description |
|----------|-------|-------------|
| `POSITION_MIN_PCT` | 5% | Minimum position size per pair |
| `POSITION_MAX_PCT` | 20% | Maximum position size per pair |
| `OI_MC_DANGER_THRESHOLD` | 0.06 | OI/market-cap ratio danger zone |
| `OI_MC_DANGER_PENALTY` | 0.70 | 30% size reduction for danger pairs |
| `CORRELATION_GATE_THRESHOLD` | 0.75 | Default; overridden by Stage 2 |
| `CORRELATION_GATE_MAX_OPEN` | 3 | Max correlated open positions before gate activates |
| `SIGNAL_STRENGTH_NORMAL` | 1.0 | Normal signal strength threshold |
| `SIGNAL_STRENGTH_GATED` | 1.5 | Required strength when correlation gate active |

---

## Objective Function

Stage 1 objective (per-pair):

```
score = log(1 + raw_calmar) × trade_mult × sharpe_penalty

where:
  raw_calmar      = max(0, annual_return / max(max_dd, 0.05))
  trade_mult      = min(1, trades_per_year / 100)        # ramp to 100 trades/yr
  sharpe_penalty   = 1 / (1 + 0.3 × (sharpe - 3.0))     # only if sharpe > 3.0
```

Stage 2 objectives (portfolio):

```
obj1 = portfolio_calmar           # maximize
obj2 = worst_pair_calmar          # maximize (robustness)
obj3 = -overfit_penalty           # maximize (minimize overfit)
```
