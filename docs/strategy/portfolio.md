# Portfolio Simulator Logic

## Overview

`portfolio.py:PortfolioSimulator` runs a bar-by-bar simulation across all pairs with **shared equity**. Unlike Stage 1 (per-pair Numba backtest), the portfolio sim is a Python loop that handles cross-pair interactions.

## Simulation Loop

```
For each bar (1H):
    │
    ├── 1. Check PORTFOLIO HEAT exit
    │   If equity DD > portfolio_heat:
    │       close worst-performing open position
    │
    ├── 2. Check SIGNAL EXITS for each open position
    │   Per-pair exit logic (hard stop, trailing, time, opposing)
    │   Uses same 5-level priority as backtest.py
    │
    ├── 3. Collect NEW ENTRY signals
    │   For each pair with buy/sell signal at this bar:
    │       check if pair already has open position → skip
    │       check max_concurrent → skip if at limit
    │       check cluster_max → skip if cluster full
    │
    ├── 4. Apply CORRELATION GATE (Layer 6)
    │   Count correlated open positions (corr > threshold)
    │   If count > CORRELATION_GATE_MAX_OPEN (3):
    │       require signal_strength > SIGNAL_STRENGTH_GATED (1.5)
    │       else: require signal_strength > SIGNAL_STRENGTH_NORMAL (1.0)
    │   Rank remaining candidates by signal_strength, take top N
    │
    └── 5. OPEN NEW POSITIONS
        For each accepted entry:
            compute_position_size() → inverse-vol + haircuts
            deduct capital from shared equity
            record entry
```

## Position Sizing Flow

```
compute_position_size(symbol, open_pairs, equity, atr_dict, corr_dict)
    │
    ├── Step 1: Base weight = 1 / atr_1h_pct
    │   BTC (low vol) gets higher weight, SOL (high vol) gets lower
    │
    ├── Step 2: Normalize across all active symbols
    │   weights sum to 1.0
    │
    ├── Step 3: Correlation haircut
    │   For each open position with |corr| > 0.75:
    │       weight *= 0.90 (10% reduction per correlated pair)
    │
    ├── Step 4: OI/MC danger penalty
    │   If pair's OI/MC ratio > 6%:
    │       weight *= 0.70 (30% reduction)
    │   Currently affects SOL (OI/MC = 13.4%)
    │
    └── Step 5: Clip to [5%, 20%] of equity
        size = equity × weight
        return max(min_size, min(size, max_size))
```

### Example sizing (3 pairs, $50k equity)

```
               ATR%    inv_vol   normalized   after corr haircut   after OI/MC   final size
BTC/USDT      0.004    250.0     0.483        0.483 (no open)      0.483         $20,000 (cap)
ETH/USDT      0.006    166.7     0.322        0.290 (BTC open)     0.290         $14,500
SOL/USDT      0.009    111.1     0.215        0.193 (BTC+ETH)      0.135 (×0.70) $6,750
```

## Correlation Gate Detail

The correlation gate prevents overconcentration in highly correlated positions.

```
Before opening position on pair X:

1. Count how many open positions have |corr(X, open)| > corr_gate_threshold
   (default 0.75, optimized by Stage 2)

2. If count > CORRELATION_GATE_MAX_OPEN (3):
      require signal_strength[X][bar] > 1.5   (higher bar)
   else:
      require signal_strength[X][bar] > 1.0   (normal bar)

3. If multiple candidates pass the gate:
      rank by signal_strength, take best N up to max_concurrent
```

**Signal strength formula:**
```
signal_strength = |MACD_line - signal_line| / ATR + |RSI - 50| / 50
```

## Cluster Throttle

Pairs are grouped into clusters (defined in `config.py:CLUSTER_DEFINITIONS`):

| Cluster | Pairs | Max Concurrent |
|---------|-------|----------------|
| blue_chip | BTC, LTC | 2 |
| smart_contract_l1 | ETH, SOL, ADA, AVAX, NEAR, APT, SUI | 2 |
| l2 | ARB, OP | 1 |
| exchange | BNB | 1 |
| narrative | XRP, LINK, INJ, DOGE | 2 |

Before opening a position, the simulator checks if the pair's cluster already has `cluster_max` positions open. If yes, the entry is blocked regardless of signal strength.

## Portfolio Heat

Portfolio heat is a drawdown-based emergency mechanism:

```
equity_peak = max(equity seen so far)
current_dd = (equity_peak - current_equity) / equity_peak

if current_dd > portfolio_heat:
    find worst-performing open position (lowest unrealized PnL)
    close it immediately
```

- Default: 5% (`DEFAULT_PORTFOLIO_HEAT`)
- Optimized by Stage 2: range 3% – 10%
- Checked at the START of each bar, before any signal processing

## Trade Output Format

Each closed trade produces a dict:

```python
{
    "entry_bar": 1234,          # bar index
    "exit_bar": 1280,           # bar index
    "entry_ts": "2025-06-15T12:00:00+00:00",
    "exit_ts": "2025-06-17T10:00:00+00:00",
    "entry_price": 67500.0,
    "exit_price": 68200.0,
    "direction": "long",        # or "short"
    "symbol": "BTC/USDT",
    "pnl_abs": 145.20,          # absolute PnL
    "pnl_pct": 0.0115,          # percentage return
    "hold_bars": 46,
    "reason": "trailing_stop",  # exit reason
    "capital": 12500.0,         # capital allocated to this trade
}
```

## Key Differences: Stage 1 Backtest vs Portfolio Sim

| Aspect | Stage 1 (backtest.py) | Stage 2 (portfolio.py) |
|--------|----------------------|----------------------|
| Scope | Single pair | All pairs simultaneously |
| Equity | Independent per pair | Shared across all pairs |
| JIT | Numba-accelerated | Pure Python loop |
| Sizing | Fixed 25% of equity | Inverse-vol + haircuts |
| Layer 6 | Not applied | Correlation gate active |
| Cluster | Not applied | Cluster throttle active |
| Heat exit | Not applied | Portfolio heat exit active |
| Purpose | Per-pair param optimization | Global portfolio optimization |
