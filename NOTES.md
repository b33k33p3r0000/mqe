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

## 2026-03-07 — Adaptive trials fix + run.sh cleanup

**Problem:** S1 trials byly 35k pro BTC/ETH/SOL i přesto, že dataset má 5-8yr dat. Root cause: `--hours` default 8760 (1yr) → `compute_trials()` dostala ~8.7k barů → SHORT tier.

**Fix:**
- `config.py`: Thresholds přeladěny — `TRIALS_LONG_THRESHOLD` 43800→39420 (4.5yr), `MEDIUM` 26000→21900 (2.5yr)
- `optimize.py`: Default `--hours` 8760→26280 (~3yr) aby odpovídal run.sh
- `run.sh`: Odstraněn `--s1-trials` z CLI, presetů, banneru. S1 trials plně automatické přes `compute_trials()`.

**Tiers:** <2.5yr = 35k, >=2.5yr = 50k, >=4.5yr = 65k trials per pair.

---

## 2026-03-11 — HTML Report

### Uděláno
- **html_report.py** (1756 řádků): Self-contained interactive HTML report s Plotly charts, Tokyonight dark theme
- **18 sekcí**: Hero metrics, portfolio equity curve, concurrent positions, per-pair table, per-pair equity curves, tier assignments, WF evaluation, S1 params table, S1 bullet chart, S1 top trials, S1 optimization history, S2 params card, Pareto front scatter, S2 optimization history, PnL contribution, correlation heatmap, monthly returns, trade analysis
- **Pipeline data exports**: S1 top trials + history (stage1.py), S2 Pareto front + history (stage2.py), correlation matrix (optimize.py)
- **Pipeline integration**: `run_final_evaluation()` exposes raw PortfolioResult data, HTML report voláno z obou `run_pipeline()` i `resume_pipeline()`
- **173 testů**, all passing

### Výstup
`results/{TIMESTAMP}/report.html` — generuje se automaticky na konci každého runu.

---

## 2026-03-12 — /analyze 20260310_191420 — Post-Analysis Improvements

**Verdict:** LOW — 20-pair run odhalil 3 systémové problémy: S2 objective gaming (heat 9.6% → inflated Calmar 14.77), inflated pair universe (7/20 failed WF), nedostatečná WF validace (2 okna).

**Implementované změny (Batch 1-3):**
- [x] B1: S2 portfolio_heat range 0.03-0.10 → 0.15-0.50 (anti-gaming floor)
- [x] B1: Pareto selection — normalized weighted score (0.6 calmar + 0.4 worst_pair) místo max calmar
- [x] B1: Tier C degradation floor 0.10 (DOT-type páry s 1.7% retention excluded)
- [x] B1: Odstraněna dead code overfit penalty (portfolio_heat < 0.035)
- [x] B2: Universe 20 → 15 párů (odstraněny LTC, ATOM, UNI, AVAX, DOT)
- [x] B3: WF_EVAL_N_WINDOWS_MEDIUM 2 → 3

**Deferred:**
- B4: Exit system improvements — separate session

Full analysis: `docs/analyze/2026-03-12-mqe-20pair-20260310_191420.md`
Design spec: `docs/plans/2026-03-12-mqe-post-analysis-improvements.md`

---

## 2026-03-12 — Agent removal

### Co se stalo
Improvement Agent (autonomní loop: analyze → change → validate → full run → promote/rollback) odstraněn po opakovaných selháních:
- Iter 1: Blocked na write permissions (settings.json neexistoval v době spuštění)
- Iter 2: Validation run crash po tighten macd_fast bounds
- Iter 3: Agent se zastavil — scoring saturoval na 98.5/100, 5/6 dimenzí na 100

### Root cause
Resilience Score thresholds byly příliš měkké — baseline run okamžitě zamaxoval většinu dimenzí. Scoring byl přepsán (Calmar 8→30, DD 5%→1.5%, +2 nové dimenze), ale agent měl příliš mnoho pohyblivých částí (git branches, state management, crash recovery) a každý fix odkryl další problém.

### Rozhodnutí
Agent smazán. Pro iterativní vylepšování strategie se používá `/analyze` skill — přímočařejší, bez overheadu orchestrace.
