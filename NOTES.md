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

---

## 2026-03-04 — CMA-ES Sampler + Monitor Metrics + Critical Fixes

### Uděláno
- **CMA-ES sampler**: Přechod z TPE na CMA-ES s TPE warmupem — rychlejší konvergence v 14-param continuous search space
- **Active pruning**: `trial.report()` + `should_prune()` po každém AWF splitu, reduction_factor=2 (prune 50% slabých trialů)
- **MIN_TRADES_YEAR_HARD**: 30 → 60 (filtr low-sample párů)
- **Soft trade ramp odstraněn**: TARGET_TRADES_YEAR zrušen — pouze hard constraint
- **Monitor metriky**: Runs tabulka rozšířena o WinR%, Sortino, Worst Calmar, Max Concurrent, Hold bars, Profitable Months%. Live tabulka: Trades, PnL%
- **Progress interval**: 500 → 100 trialů (responsivnější live dashboard)
- **n_jobs cap**: Max 3 per pair pro lepší thread utilization
- **Dependency**: cmaes>=0.12.0

### Critical Fixes (3272fb6)
- **C1**: RSI vrací 100 (ne NaN) když avg_loss je nula
- **C2**: end_idx=0 se už netratuje jako None v time-based Sharpe
- **C3**: `generate_markdown_report` guard proti eval_result=None

### Current state
- 267 tests, all passing

---

## 2026-03-01 — Code Review Fixes (C1, W1-W13, I4)

### Uděláno
- **C1**: FEE 0.075% → 0.06% (Binance VIP0 taker + buffer, starý outdated)
- **I4**: STARTING_EQUITY 50k → 100k, POSITION_PCT 25% → 20% (research: max 20% per pair, inv-vol sizing [5-20%])
- **W1-W2**: BacktestResult equity=0→STARTING_EQUITY, portfolio candidate filtering fix (premature break)
- **W3-W4**: metrics.py performance — `.iloc` → pre-extracted `.values`, Python reindex loop → `pd.reindex()`
- **W5-W13**: stage2 `callable`→`Callable`, io.py error handling + shared `fmt()`, monitor verdict delegace na analyze.py, falsy float checks, sizing hardcoded→config konstanty, notify kanál fix, deduplikace `_load_json`/`_fmt`
- **W10**: Nová konstanta `CORRELATION_HAIRCUT_FACTOR = 0.90` v config.py

### Current state
- 267 tests, all passing

---

## 2026-03-07 — /analyze 20260306_213212

**Verdict:** MEDIUM — Post-analysis improvements (WF eval tiering, 4-objective NSGA-II) fungovaly mechanicky správně, ale celkový portfolio výsledek je horší než před úpravami (Sharpe 3.98 vs 4.27, PnL +260% vs +330%).

**Key findings:**
- 4-objective NSGA-II degradoval worst_pair_calmar 0.97 → 0.063 bez kompenzace (degradation penalty de facto nulový ~0.002)
- ARB false inclusion: WF eval ho propustil jako B-tier, ale full-eval ukazuje Sharpe -0.14 a PnL -5.3%
- cluster_max 3→2 zvýšil blokování trades z 21% na 33% bez proporcionálního DD zlepšení

**Decided actions:**
- [x] S1: Revert na 3-objective NSGA-II — odstranění degradation objective (f947299)
- [x] R1: Post-eval gate — páry s full-eval Sharpe < 0 degradovány na tier X před S2 (f947299)
- [x] R2: Zvýšení DEFAULT_TRIALS_STAGE2 z 5,000 na 10,000 (f947299)

**Deferred:**
- R3: cluster_max range 1-4 — vyžaduje nový run pro ověření
- S2: Dynamický B-tier threshold — nízká priorita, post-eval gate řeší akutní problém
- S3: Weighted Pareto front selection — exploratory, vyžaduje research
