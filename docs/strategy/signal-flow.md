# Signal Flow & Exit System

## Entry Funnel — 6 Layers

All 6 layers must pass simultaneously for a signal to fire. Each bar is evaluated independently.

```
1H OHLCV bar arrives
    │
    ▼
┌─────────────────────────────────┐
│  Layer 1: MACD CROSSOVER        │  ← per-pair params (macd_fast/slow/signal)
│  macd_prev <= signal_prev       │
│  macd_now  >  signal_now        │  = bullish cross (buy)
│  (opposite for bearish cross)   │
└────────────┬────────────────────┘
             │ pass
             ▼
┌─────────────────────────────────┐
│  Layer 2: RSI LOOKBACK          │  ← per-pair params (rsi_period/lower/upper/lookback)
│  RSI < rsi_lower at any bar     │
│  within [now - lookback, now]   │  = oversold confirmation (buy)
│  RSI > rsi_upper               │  = overbought confirmation (sell)
└────────────┬────────────────────┘
             │ pass
             ▼
┌─────────────────────────────────┐
│  Layer 3: HTF TREND FILTER      │  ← per-pair params (trend_tf, trend_strict)
│  Compute MACD on trend_tf       │
│  (4h / 8h / 1d)                │
│  HTF MACD > signal = bullish   │
│  Must align with entry direction │
└────────────┬────────────────────┘
             │ pass
             ▼
┌─────────────────────────────────┐
│  Layer 4: BTC REGIME FILTER     │  ← global (BTC 4H MACD state)
│  Non-BTC pairs only            │
│  Longs allowed when BTC 4H     │
│  MACD > signal (bullish)       │
│  Shorts allowed when bearish   │
│  Uses BTC's Stage 1 params     │
└────────────┬────────────────────┘
             │ pass
             ▼
┌─────────────────────────────────┐
│  Layer 5: ADX PRE-FILTER        │  ← per-pair param (adx_threshold)
│  ADX(14) >= adx_threshold       │
│  Filters out range-bound bars   │
└────────────┬────────────────────┘
             │ pass
             ▼
┌─────────────────────────────────┐
│  Layer 6: CORRELATION GATE      │  ← portfolio-level (corr_gate_threshold)
│  Handled by portfolio.py        │
│  If >3 correlated pairs open:  │
│  require signal_strength > 1.5  │
│  (vs normal threshold 1.0)      │
└────────────┬────────────────────┘
             │ pass
             ▼
        ╔═══════════╗
        ║  ENTRY    ║
        ╚═══════════╝
```

### Signal Generation Code Path

```
strategy.py:MultiPairStrategy.precompute_signals()
    ├── Layer 1: macd() → macd_bullish_cross / macd_bearish_cross
    ├── Layer 2: rsi() → rsi_oversold / rsi_overbought (with rolling lookback)
    ├── Layer 3: macd() on htf data → htf_bullish_aligned / htf_bearish_aligned
    ├── Layer 4: macd() on BTC 4H → regime_allows_long / regime_allows_short
    ├── Layer 5: adx() → adx_pass
    └── Combine: buy_signal = L1 & L2 & L3 & L4 & L5 & ~has_nan
                 (Layer 6 applied later in portfolio.py)
```

Returns: `(buy_signal, sell_signal, atr_values, signal_strength)`

### Signal Strength (for correlation gate ranking)

```
signal_strength = macd_strength + rsi_strength

where:
  macd_strength = |MACD_line - signal_line| / ATR    (normalized momentum)
  rsi_strength  = |RSI - 50| / 50                    (distance from neutral)
```

Used by portfolio.py to rank competing entry signals when correlation gate is active.

---

## Exit System — 5 Levels

Evaluated every bar for each open position. **First match wins** — no further checks after a trigger.

```
Bar arrives, position is open
    │
    ▼
┌─────────────────────────────────────┐
│  Level 1: HARD STOP (highest prio)  │
│  Long:  low <= entry - hard_stop_mult × ATR  │
│  Short: high >= entry + hard_stop_mult × ATR │
│  Exit at stop level (not market)    │
└────────────┬────────────────────────┘
             │ not triggered
             ▼
┌─────────────────────────────────────┐
│  Level 2: TRAILING STOP            │
│  Activation: unrealized >= 1.5×ATR │
│  Once active:                       │
│  Long:  low <= highest - trail_mult × ATR   │
│  Short: high >= lowest + trail_mult × ATR   │
│  Tracks highest/lowest price seen   │
└────────────┬────────────────────────┘
             │ not triggered
             ▼
┌─────────────────────────────────────┐
│  Level 3: TIME EXIT                 │
│  bars_held >= max_hold_bars         │
│  Exit at current market price       │
└────────────┬────────────────────────┘
             │ not triggered
             ▼
┌─────────────────────────────────────┐
│  Level 4: OPPOSING SIGNAL           │
│  Requires min_hold_bars (2) met     │
│  If allow_flip=1: close + open      │
│  opposite direction immediately     │
│  If allow_flip=0: just close        │
└────────────┬────────────────────────┘
             │ not triggered
             ▼
┌─────────────────────────────────────┐
│  Level 5: PORTFOLIO HEAT            │
│  (portfolio.py only, not backtest)  │
│  If portfolio DD > portfolio_heat:  │
│  close worst-performing position    │
└─────────────────────────────────────┘
```

### Exit at end of data

If any position is still open at `end_idx`, it is force-closed at market (exit reason: `force_close`).

### Exit Reason Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | opposing_signal | Opposing entry signal fired |
| 1 | hard_stop | ATR-based hard stop hit |
| 2 | trailing_stop | Trailing stop triggered (after activation) |
| 3 | time_exit | Max hold bars exceeded |
| 4 | portfolio_heat | Portfolio DD limit (portfolio.py only) |
| 5 | force_close | End of data |

---

## Data Flow — Full Pipeline

```
ccxt/Binance
    │
    ▼
fetch.py: load_multi_pair_data()          ← 1H + 4H/8H/1D per symbol
    │                                        Always includes BTC/USDT
    ▼
┌──────────────────────────────┐
│  STAGE 1 (parallel)          │
│  Per pair: stage1.py         │
│  ├── strategy.precompute_signals()
│  ├── backtest.simulate_trades_fast()   ← Numba JIT
│  ├── metrics.calculate_metrics()
│  └── Optuna TPE + AWF splits
│  Output: 14 best params/pair │
└──────────────┬───────────────┘
               ▼
optimize.py: precompute_all_signals()    ← Re-compute with best S1 params
               │                            Uses BTC's S1 params for regime
               ▼
┌──────────────────────────────┐
│  STAGE 2                     │
│  stage2.py: NSGA-II          │
│  ├── portfolio.PortfolioSimulator()
│  │   ├── Shared equity across all pairs
│  │   ├── Correlation gate (Layer 6)
│  │   ├── Cluster throttle
│  │   ├── Portfolio heat exit
│  │   └── Inverse-vol sizing
│  └── 3 objectives: portfolio Calmar,
│      worst-pair Calmar, overfit penalty
│  Output: 4 global params     │
└──────────────┬───────────────┘
               ▼
analyze.py + report.py + notify.py
    │
    ▼
results/{timestamp}/
    ├── stage1/{symbol}.json
    ├── stage2_result.json
    └── pipeline_result.json
```

---

## Key Interactions Between Layers

**MACD params shared across layers:** The same `macd_fast/slow/signal` used for Layer 1 entry crossover are also used for Layer 3 HTF trend filter on the same pair. This creates a coupling — fast MACD params that catch many crossovers also produce a noisier HTF filter.

**BTC regime uses BTC's own optimized params:** In Stage 1, BTC is optimized like any other pair. In Stage 2 (and signal precomputation), BTC's optimized MACD params are used for the regime filter applied to non-BTC pairs. This means BTC's optimization indirectly affects all other pairs' signal quality.

**ADX and MACD are complementary:** ADX measures trend strength regardless of direction. MACD measures directional momentum. A bar can have a strong MACD crossover but low ADX (choppy market) — ADX filter blocks this. Conversely, high ADX with no MACD crossover means strong trend but no entry trigger.

**Correlation gate is the only post-signal filter:** Layers 1-5 produce raw buy/sell signals in strategy.py. Layer 6 (correlation gate) is applied in portfolio.py at the time of position opening. A signal can pass all 5 layers but still be rejected by the correlation gate if too many correlated positions are already open.
