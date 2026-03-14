"""
MQE Configuration
=================
Centralized config for Multi-pair Quant Engine.
Multi-pair MACD/RSI funnel optimizer for crypto perpetual futures.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ─── SYMBOLS & TIMEFRAMES ───────────────────────────────────────────────────

SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT",
    "XRP/USDT", "BNB/USDT", "LINK/USDT",
    "SUI/USDT", "ADA/USDT", "APT/USDT",
    "NEAR/USDT", "ARB/USDT", "OP/USDT",
    "INJ/USDT", "DOGE/USDT", "FIL/USDT",
]
TREND_TFS = ["4h", "8h", "1d"]
BASE_TF = "1h"

TF_MS: dict[str, int] = {
    "1h": 3_600_000,
    "4h": 14_400_000,
    "8h": 28_800_000,
    "1d": 86_400_000,
}

# ─── TRADING COSTS ──────────────────────────────────────────────────────────

FEE = float(os.environ.get("FEE", "0.0006"))  # 6 bps (Binance VIP0 taker=5 bps + 1 bps buffer)

SLIPPAGE_MAP: dict[str, float] = {
    "BTC/USDT": 0.0006,
    "ETH/USDT": 0.0009,
    "SOL/USDT": 0.0015,
    "XRP/USDT": 0.0015,
    "BNB/USDT": 0.0012,
    "LINK/USDT": 0.0018,
    "SUI/USDT": 0.0022,
    "ADA/USDT": 0.0020,
    "NEAR/USDT": 0.0025,
    "APT/USDT": 0.0025,
    "ARB/USDT": 0.0030,
    "OP/USDT": 0.0030,
    "INJ/USDT": 0.0035,
    "DOGE/USDT": 0.0015,
    "FIL/USDT": 0.0025,
}
DEFAULT_SLIPPAGE = float(os.environ.get("SLIPPAGE", "0.0015"))


def get_slippage(symbol: str) -> float:
    return SLIPPAGE_MAP.get(symbol, DEFAULT_SLIPPAGE)


# ─── PAIR PROFILES (from research) ──────────────────────────────────────────

PAIR_PROFILES: dict[str, dict] = {
    "BTC/USDT": {
        "tier": "S",
        "cluster": "blue_chip",
        "btc_corr": 1.0,
        "ann_vol": 0.47,
        "atr_1h_pct": 0.004,
        "slippage_bps": 6,
        "oi_mc_ratio": 0.023,
        "volume_24h_min": 8e9,
    },
    "ETH/USDT": {
        "tier": "S",
        "cluster": "smart_contract_l1",
        "btc_corr": 0.76,
        "ann_vol": 0.77,
        "atr_1h_pct": 0.006,
        "slippage_bps": 9,
        "oi_mc_ratio": 0.038,
        "volume_24h_min": 4e9,
    },
    "SOL/USDT": {
        "tier": "A+",
        "cluster": "smart_contract_l1",
        "btc_corr": 0.75,
        "ann_vol": 0.84,
        "atr_1h_pct": 0.009,
        "slippage_bps": 15,
        "oi_mc_ratio": 0.134,
        "volume_24h_min": 1.5e9,
    },
    "XRP/USDT": {
        "tier": "A",
        "cluster": "narrative",
        "btc_corr": 0.70,
        "ann_vol": 0.85,
        "atr_1h_pct": 0.008,
        "slippage_bps": 15,
        "oi_mc_ratio": 0.05,
        "volume_24h_min": 0.5e9,
    },
    "BNB/USDT": {
        "tier": "A",
        "cluster": "exchange",
        "btc_corr": 0.84,
        "ann_vol": 0.60,
        "atr_1h_pct": 0.005,
        "slippage_bps": 12,
        "oi_mc_ratio": 0.03,
        "volume_24h_min": 0.3e9,
    },
    "LINK/USDT": {
        "tier": "A",
        "cluster": "narrative",
        "btc_corr": 0.78,
        "ann_vol": 0.90,
        "atr_1h_pct": 0.010,
        "slippage_bps": 18,
        "oi_mc_ratio": 0.06,
        "volume_24h_min": 0.2e9,
    },
    "SUI/USDT": {
        "tier": "A-",
        "cluster": "smart_contract_l1",
        "btc_corr": 0.69,
        "ann_vol": 1.00,
        "atr_1h_pct": 0.012,
        "slippage_bps": 22,
        "oi_mc_ratio": 0.08,
        "volume_24h_min": 0.15e9,
    },
    "ADA/USDT": {
        "tier": "B+",
        "cluster": "smart_contract_l1",
        "btc_corr": 0.80,
        "ann_vol": 0.85,
        "atr_1h_pct": 0.009,
        "slippage_bps": 20,
        "oi_mc_ratio": 0.04,
        "volume_24h_min": 0.15e9,
    },
    "NEAR/USDT": {
        "tier": "B",
        "cluster": "smart_contract_l1",
        "btc_corr": 0.73,
        "ann_vol": 0.95,
        "atr_1h_pct": 0.011,
        "slippage_bps": 25,
        "oi_mc_ratio": 0.07,
        "volume_24h_min": 0.1e9,
    },
    "APT/USDT": {
        "tier": "B",
        "cluster": "smart_contract_l1",
        "btc_corr": 0.73,
        "ann_vol": 0.95,
        "atr_1h_pct": 0.012,
        "slippage_bps": 25,
        "oi_mc_ratio": 0.08,
        "volume_24h_min": 0.08e9,
    },
    "ARB/USDT": {
        "tier": "B-",
        "cluster": "l2",
        "btc_corr": 0.76,
        "ann_vol": 1.00,
        "atr_1h_pct": 0.013,
        "slippage_bps": 30,
        "oi_mc_ratio": 0.09,
        "volume_24h_min": 0.06e9,
    },
    "OP/USDT": {
        "tier": "B-",
        "cluster": "l2",
        "btc_corr": 0.76,
        "ann_vol": 1.00,
        "atr_1h_pct": 0.013,
        "slippage_bps": 30,
        "oi_mc_ratio": 0.09,
        "volume_24h_min": 0.06e9,
    },
    "INJ/USDT": {
        "tier": "B-",
        "cluster": "narrative",
        "btc_corr": 0.69,
        "ann_vol": 1.10,
        "atr_1h_pct": 0.015,
        "slippage_bps": 35,
        "oi_mc_ratio": 0.10,
        "volume_24h_min": 0.05e9,
    },
    "DOGE/USDT": {
        "tier": "B+",
        "cluster": "meme",
        "btc_corr": 0.65,
        "ann_vol": 0.95,
        "atr_1h_pct": 0.011,
        "slippage_bps": 15,
        "oi_mc_ratio": 0.04,
        "volume_24h_min": 0.5e9,
    },
    "FIL/USDT": {
        "tier": "B",
        "cluster": "storage",
        "btc_corr": 0.65,
        "ann_vol": 0.95,
        "atr_1h_pct": 0.012,
        "slippage_bps": 25,
        "oi_mc_ratio": 0.07,
        "volume_24h_min": 0.08e9,
    },
}


def get_cluster(symbol: str) -> str:
    if symbol in PAIR_PROFILES:
        return PAIR_PROFILES[symbol]["cluster"]
    return "unknown"


# ─── CLUSTER DEFINITIONS ────────────────────────────────────────────────────

CLUSTER_DEFINITIONS: dict[str, list[str]] = {
    "blue_chip": ["BTC/USDT"],
    "smart_contract_l1": ["ETH/USDT", "SOL/USDT", "ADA/USDT",
                          "NEAR/USDT", "APT/USDT", "SUI/USDT"],
    "l2": ["ARB/USDT", "OP/USDT"],
    "exchange": ["BNB/USDT"],
    "narrative": ["XRP/USDT", "LINK/USDT", "INJ/USDT"],
    "meme": ["DOGE/USDT"],
    "storage": ["FIL/USDT"],
}

CLUSTER_MAX_CONCURRENT: dict[str, int] = {
    "blue_chip": 2,
    "smart_contract_l1": 2,
    "l2": 1,
    "exchange": 1,
    "narrative": 2,
    "meme": 1,
    "storage": 1,
}

# ─── PER-TIER SEARCH SPACE ─────────────────────────────────────────────────

TIER_SEARCH_SPACE: dict[str, dict[str, tuple]] = {
    "S": {
        "vol_sensitivity": (0.3, 2.5),
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 20.0),
        "macd_slow": (10, 45),
        "macd_signal": (3, 15),
        "rsi_period": (3, 30),
        "rsi_lower": (20, 40),
        "rsi_upper": (60, 80),
        "rsi_lookback": (1, 4),
        "adx_threshold": (15.0, 30.0),
        "trail_mult": (2.0, 4.0),
        "hard_stop_mult": (1.5, 4.0),
        "max_hold_bars": (48, 168),
    },
    "A+": {
        "vol_sensitivity": (0.3, 2.5),
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 18.0),
        "macd_slow": (10, 42),
        "macd_signal": (3, 15),
        "rsi_period": (3, 28),
        "rsi_lower": (22, 38),
        "rsi_upper": (62, 78),
        "rsi_lookback": (1, 4),
        "adx_threshold": (15.0, 30.0),
        "trail_mult": (2.0, 4.0),
        "hard_stop_mult": (1.5, 3.5),
        "max_hold_bars": (36, 144),
    },
    "A": {
        "vol_sensitivity": (0.5, 2.0),
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 18.0),
        "macd_slow": (10, 40),
        "macd_signal": (3, 15),
        "rsi_period": (3, 28),
        "rsi_lower": (22, 38),
        "rsi_upper": (62, 78),
        "rsi_lookback": (1, 4),
        "adx_threshold": (15.0, 30.0),
        "trail_mult": (2.0, 3.8),
        "hard_stop_mult": (1.5, 3.0),
        "max_hold_bars": (36, 144),
    },
    "A-": {
        "vol_sensitivity": (0.5, 2.0),
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 15.0),
        "macd_slow": (12, 38),
        "macd_signal": (3, 13),
        "rsi_period": (3, 25),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (18.0, 30.0),
        "trail_mult": (1.5, 3.0),
        "hard_stop_mult": (1.5, 2.5),
        "max_hold_bars": (24, 120),
    },
    "B+": {
        "vol_sensitivity": (0.5, 1.5),
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 15.0),
        "macd_slow": (12, 38),
        "macd_signal": (3, 13),
        "rsi_period": (3, 25),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (18.0, 30.0),
        "trail_mult": (1.5, 2.8),
        "hard_stop_mult": (1.5, 2.5),
        "max_hold_bars": (24, 120),
    },
    "B": {
        "vol_sensitivity": (0.5, 1.5),
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 12.0),
        "macd_slow": (14, 35),
        "macd_signal": (3, 12),
        "rsi_period": (3, 22),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (20.0, 30.0),
        "trail_mult": (1.5, 2.8),
        "hard_stop_mult": (1.5, 2.5),
        "max_hold_bars": (24, 96),
    },
    "B-": {
        "vol_sensitivity": (0.5, 1.5),
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 12.0),
        "macd_slow": (14, 35),
        "macd_signal": (3, 12),
        "rsi_period": (3, 22),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (20.0, 30.0),
        "trail_mult": (1.5, 2.5),
        "hard_stop_mult": (1.5, 2.0),
        "max_hold_bars": (24, 96),
    },
}

# ─── OI/MC DANGER ZONE ──────────────────────────────────────────────────────

OI_MC_DANGER_THRESHOLD = 0.06
OI_MC_DANGER_PENALTY = 0.70  # 30% size reduction

# ─── TRADE COUNT CONSTRAINTS ────────────────────────────────────────────────

MIN_TRADES_YEAR_HARD = 60
MIN_TRADES_TEST_HARD = 5

# ─── OPTIMIZATION ───────────────────────────────────────────────────────────

SHARPE_SUSPECT_THRESHOLD = 3.0
SHARPE_DECAY_RATE = 0.3
MIN_DRAWDOWN_FLOOR = 0.05
TARGET_TRADES_YEAR = 100
PURGE_GAP_BARS = 50
DEFAULT_TRIALS_STAGE2 = 10_000
MIN_STARTUP_TRIALS = 50
STARTUP_TRIALS_RATIO = 0.20
TPE_N_EI_CANDIDATES = 24
TPE_CONSIDER_ENDPOINTS = True
ENABLE_PRUNING = True
MONTE_CARLO_SIMULATIONS = 1000
MONTE_CARLO_MIN_TRADES = 20

# ─── DATA-ADAPTIVE TRIALS ──────────────────────────────────────────────────

TRIALS_LONG_THRESHOLD_HOURS = 39420   # >= 4.5yr → full trials
TRIALS_MEDIUM_THRESHOLD_HOURS = 21900  # >= 2.5yr → medium trials
TRIALS_LONG = 50_000
TRIALS_MEDIUM = 30_000
TRIALS_SHORT = 20_000

# ─── ANCHORED WALK-FORWARD ──────────────────────────────────────────────────

ANCHORED_WF_MIN_DATA_HOURS = 4000
ANCHORED_WF_SHORT_THRESHOLD_HOURS = 13140

ANCHORED_WF_SPLITS = [
    {"train_end": 0.60, "test_end": 0.70},
    {"train_end": 0.70, "test_end": 0.80},
    {"train_end": 0.80, "test_end": 0.90},
]
ANCHORED_WF_SPLITS_SHORT = [
    {"train_end": 0.70, "test_end": 0.85},
    {"train_end": 0.85, "test_end": 1.00},
]

ANCHORED_WF_LONG_THRESHOLD_HOURS = 26280  # >= 3yr → 5 splits

ANCHORED_WF_SPLITS_LONG = [
    {"train_end": 0.50, "test_end": 0.60},
    {"train_end": 0.60, "test_end": 0.70},
    {"train_end": 0.70, "test_end": 0.80},
    {"train_end": 0.80, "test_end": 0.90},
    {"train_end": 0.90, "test_end": 1.00},
]

# ─── WALK-FORWARD EVALUATION ──────────────────────────────────────────────

WF_EVAL_CEILING_LONG = 0.70       # S1 trains on first 70% (>= 3yr data)
WF_EVAL_CEILING_MEDIUM = 0.75     # 75% (1.5-3yr data)
WF_EVAL_CEILING_SHORT = 0.80      # 80% (< 1.5yr data)
WF_EVAL_N_WINDOWS_LONG = 3        # 3 eval windows for long data
WF_EVAL_N_WINDOWS_MEDIUM = 3      # 3 for medium
WF_EVAL_N_WINDOWS_SHORT = 1       # 1 for short (single holdout)

# Enhanced tiering thresholds
TIER_DEGRADATION_A = 0.5          # min S1/OOS ratio for A tier
TIER_DEGRADATION_B = 0.3          # min S1/OOS ratio for B tier
TIER_DEGRADATION_C = 0.10         # min S1/OOS ratio for C tier
TIER_CONSISTENCY_A = 1.5          # max Sharpe std for A tier
TIER_WORST_WINDOW_A = 0.5         # min worst OOS window Sharpe for A tier
TIER_WORST_WINDOW_B = -0.2        # min worst OOS window Sharpe for B tier
TIER_WORST_WINDOW_C = -1.0        # min worst OOS window Sharpe for C tier
TIER_CALMAR_FLOOR = 0.5           # min eval Calmar to stay above C tier

# ─── DATA FETCHING ──────────────────────────────────────────────────────────

OHLCV_LIMIT_PER_CALL = 1500
SAFETY_MAX_ROWS = 200000
MAX_API_RETRIES = 5

# ─── BACKTESTING ────────────────────────────────────────────────────────────

MIN_WARMUP_BARS = 200
STARTING_EQUITY = 100_000.0
BACKTEST_POSITION_PCT = 0.20  # Stage 1 per-pair default (portfolio uses inv-vol sizing [5-20%])

# ─── EXIT SYSTEM ────────────────────────────────────────────────────────────

MIN_HOLD_BARS = 2
ATR_PERIOD = 14
TRAILING_ACTIVATION_MULT = 1.5  # activate trailing after 1.5×ATR profit
LONG_ONLY = False

# ─── PORTFOLIO CONTROLS (defaults — overridden by Stage 2 Optuna) ────────

DEFAULT_MAX_CONCURRENT = 5
DEFAULT_CLUSTER_MAX = 2
DEFAULT_PORTFOLIO_HEAT = 0.05
DEFAULT_SIZING_METHOD = "inv_vol"
CORRELATION_GATE_THRESHOLD = 0.75
CORRELATION_GATE_MAX_OPEN = 3
SIGNAL_STRENGTH_GATED = 1.5
CORRELATION_HAIRCUT_FACTOR = 0.90  # 10% size reduction per correlated open pair
POSITION_MIN_PCT = 0.05
POSITION_MAX_PCT = 0.20

# ─── TIER SYSTEM ───────────────────────────────────────────────────────────

TIER_THRESHOLDS = {"A": 1.5, "B": 0.5, "C": 0.0}  # eval Sharpe (equity) boundaries
TIER_MULTIPLIERS = {"A": 1.0, "B": 0.6, "C": 0.25, "X": 0.0}  # sizing + ranking multiplier

# ─── DISCORD ────────────────────────────────────────────────────────────────

DISCORD_WEBHOOK_RUNS = os.environ.get("DISCORD_WEBHOOK_RUNS", "")

# ─── GARCH ─────────────────────────────────────────────────────────────
GARCH_WINDOW = 720              # rolling MLE fit window (30 days of 1H)
GARCH_REFIT_INTERVAL = 168      # re-fit every 7 days
GARCH_VOL_RATIO_MIN = 0.5       # min vol_ratio (max position boost = 2×)
GARCH_VOL_RATIO_MAX = 2.0       # max vol_ratio (max position cut = 50%)
GARCH_POSITION_MIN = 0.05       # absolute floor for adjusted position_pct
GARCH_POSITION_MAX = 0.30       # absolute ceiling for adjusted position_pct
GARCH_ADAPTIVE_STOPS = bool(os.environ.get("GARCH_ADAPTIVE_STOPS", ""))
GARCH_STOP_FACTOR_MIN = 0.7     # min stop width multiplier
GARCH_STOP_FACTOR_MAX = 1.5     # max stop width multiplier
GARCH_REGIME_FILTER = bool(os.environ.get("GARCH_REGIME_FILTER", ""))
GARCH_REGIME_THRESHOLD = 2.5    # conditional_vol / long_term_vol threshold

# ─── PBO ───────────────────────────────────────────────────────────────
PBO_N_PARAM_SETS = 100          # independent random param sets for CSCV
PBO_N_SUBSETS = 8               # CSCV data subsets (C(8,4) = 70 combos)
PBO_TIER_X_THRESHOLD = 0.50     # PBO > 50% → tier X
PBO_DEMOTE_THRESHOLD = 0.30     # PBO 30-50% → demote 1 tier
