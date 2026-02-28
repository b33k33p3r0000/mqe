# MQE Session Notes

## 2026-02-28 — Initial Implementation

### What was done
Full MQE (Multi-pair Quant Engine) implementation from scratch — 18 TDD tasks, 165 tests passing.

**Implementace:**
- Scaffolding + config (symbols, pair profiles, clusters, costs)
- Indicators: MACD, RSI, ATR, ADX (Numba-ready numpy)
- 6-layer entry funnel (strategy.py): MACD crossover + RSI lookback + HTF trend + BTC regime + ADX + correlation gate
- 5-level exit system (backtest.py): hard stop + trailing stop + time exit + opposing signal + force close — Numba JIT
- Portfolio simulator: shared equity, cluster throttle, correlation gate, portfolio heat
- Risk modules: inverse-vol sizing, rolling correlation, BTC regime filter
- Stage 1 optimizer: per-pair TPE with AWF splits, log-Calmar objective
- Stage 2 optimizer: NSGA-II multi-objective (portfolio Calmar, worst-pair Calmar, overfit penalty)
- Pipeline orchestrator: parallel Stage 1 via ProcessPoolExecutor, sequential Stage 2
- Analysis, reporting, Discord notifications
- run.sh CLI with 5 presets (test/quick/main/full/custom)
- Integration test: full pipeline smoke test

**Code review fixes (C1, I1-I5):**
- C1: Flaky test fix (increased n_trials, check completed trials)
- I1: Added entry_ts/exit_ts to portfolio trades
- I2: Standardized typing to lowercase generics across all src files
- I3: Removed duplicate Poetry deps from pyproject.toml
- I4: Integrated inverse-vol sizing into portfolio simulator
- I5: Vectorized regime.py for-loop

### Key decisions
- MQE je nezavisle na QRE — sdili principy (AWF, log-Calmar objective), ale vlastni codebase
- 3 default pary: BTC/USDT, ETH/USDT, SOL/USDT (S/S/A+ tier)
- Per-pair 14 Optuna params, Stage 2 global 4 params
- Numba JIT pro per-pair backtest, Python loop pro portfolio sim
- `uv` jako package manager

### Current state
- 165 tests, all passing
- Pushed to GitHub: b33k33p3r0000/mqe (private)
- Ready for first real optimization run
