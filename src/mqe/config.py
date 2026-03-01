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
    "SUI/USDT", "DOT/USDT", "ADA/USDT",
    "NEAR/USDT", "LTC/USDT", "APT/USDT",
    "ARB/USDT", "OP/USDT", "INJ/USDT",
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
    "DOT/USDT": 0.0020,
    "ADA/USDT": 0.0020,
    "NEAR/USDT": 0.0025,
    "LTC/USDT": 0.0015,
    "APT/USDT": 0.0025,
    "ARB/USDT": 0.0030,
    "OP/USDT": 0.0030,
    "INJ/USDT": 0.0035,
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
    "DOT/USDT": {
        "tier": "B+",
        "cluster": "smart_contract_l1",
        "btc_corr": 0.75,
        "ann_vol": 0.85,
        "atr_1h_pct": 0.009,
        "slippage_bps": 20,
        "oi_mc_ratio": 0.04,
        "volume_24h_min": 0.12e9,
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
    "LTC/USDT": {
        "tier": "B",
        "cluster": "blue_chip",
        "btc_corr": 0.84,
        "ann_vol": 0.65,
        "atr_1h_pct": 0.007,
        "slippage_bps": 15,
        "oi_mc_ratio": 0.03,
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
}


def get_cluster(symbol: str) -> str:
    if symbol in PAIR_PROFILES:
        return PAIR_PROFILES[symbol]["cluster"]
    return "unknown"


# ─── CLUSTER DEFINITIONS ────────────────────────────────────────────────────

CLUSTER_DEFINITIONS: dict[str, list[str]] = {
    "blue_chip": ["BTC/USDT", "LTC/USDT"],
    "smart_contract_l1": ["ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT",
                          "NEAR/USDT", "APT/USDT", "SUI/USDT"],
    "l2": ["ARB/USDT", "OP/USDT"],
    "exchange": ["BNB/USDT"],
    "narrative": ["XRP/USDT", "LINK/USDT", "INJ/USDT"],
}

CLUSTER_MAX_CONCURRENT: dict[str, int] = {
    "blue_chip": 2,
    "smart_contract_l1": 2,
    "l2": 1,
    "exchange": 1,
    "narrative": 2,
}

# ─── PER-TIER SEARCH SPACE ─────────────────────────────────────────────────

TIER_SEARCH_SPACE: dict[str, dict[str, tuple]] = {
    "S": {
        "allow_flip": (0, 1),
        "macd_fast": (1.0, 20.0),
        "macd_slow": (10, 45),
        "macd_signal": (3, 15),
        "rsi_period": (3, 30),
        "rsi_lower": (20, 40),
        "rsi_upper": (60, 80),
        "rsi_lookback": (1, 4),
        "adx_threshold": (15.0, 30.0),
        "trail_mult": (2.0, 4.0),
        "hard_stop_mult": (1.5, 3.0),
        "max_hold_bars": (48, 168),
    },
    "A+": {
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
        "hard_stop_mult": (1.5, 2.8),
        "max_hold_bars": (36, 144),
    },
    "A": {
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
        "hard_stop_mult": (1.5, 2.8),
        "max_hold_bars": (36, 144),
    },
    "A-": {
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 15.0),
        "macd_slow": (12, 38),
        "macd_signal": (3, 13),
        "rsi_period": (3, 25),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (18.0, 30.0),
        "trail_mult": (2.0, 3.5),
        "hard_stop_mult": (1.5, 2.5),
        "max_hold_bars": (24, 120),
    },
    "B+": {
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 15.0),
        "macd_slow": (12, 38),
        "macd_signal": (3, 13),
        "rsi_period": (3, 25),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (18.0, 30.0),
        "trail_mult": (2.0, 3.5),
        "hard_stop_mult": (1.5, 2.5),
        "max_hold_bars": (24, 120),
    },
    "B": {
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 12.0),
        "macd_slow": (14, 35),
        "macd_signal": (3, 12),
        "rsi_period": (3, 22),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (20.0, 30.0),
        "trail_mult": (2.0, 3.5),
        "hard_stop_mult": (1.5, 2.5),
        "max_hold_bars": (24, 96),
    },
    "B-": {
        "allow_flip": (0, 0),
        "macd_fast": (1.0, 12.0),
        "macd_slow": (14, 35),
        "macd_signal": (3, 12),
        "rsi_period": (3, 22),
        "rsi_lower": (25, 35),
        "rsi_upper": (65, 75),
        "rsi_lookback": (1, 4),
        "adx_threshold": (20.0, 30.0),
        "trail_mult": (2.0, 3.0),
        "hard_stop_mult": (1.5, 2.5),
        "max_hold_bars": (24, 96),
    },
}

# ─── OI/MC DANGER ZONE ──────────────────────────────────────────────────────

OI_MC_DANGER_THRESHOLD = 0.06
OI_MC_DANGER_PENALTY = 0.70  # 30% size reduction

# ─── TRADE COUNT CONSTRAINTS ────────────────────────────────────────────────

MIN_TRADES_YEAR_HARD = 30
MIN_TRADES_TEST_HARD = 5

# ─── OPTIMIZATION ───────────────────────────────────────────────────────────

SHARPE_SUSPECT_THRESHOLD = 3.0
SHARPE_DECAY_RATE = 0.3
MIN_DRAWDOWN_FLOOR = 0.05
TARGET_TRADES_YEAR = 100
PURGE_GAP_BARS = 50
DEFAULT_TRIALS_STAGE1 = 10000
DEFAULT_TRIALS_STAGE2 = 5000
MIN_STARTUP_TRIALS = 50
STARTUP_TRIALS_RATIO = 0.20
TPE_N_EI_CANDIDATES = 24
TPE_CONSIDER_ENDPOINTS = True
ENABLE_PRUNING = True
MONTE_CARLO_SIMULATIONS = 1000
MONTE_CARLO_MIN_TRADES = 20

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

# ─── DISCORD ────────────────────────────────────────────────────────────────

DISCORD_WEBHOOK_RUNS = os.environ.get("DISCORD_WEBHOOK_RUNS", "")
