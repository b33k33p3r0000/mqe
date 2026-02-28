"""
Full Pipeline Smoke Test
========================
End-to-end integration test: synthetic data -> Stage 1 -> Stage 2 -> analysis -> save.

Uses synthetic random-walk OHLCV data (no API calls).
Verifies each pipeline stage produces correct output structure.
"""

import numpy as np
import optuna
import pytest

from tests.conftest import make_1h_ohlcv_pd, resample_to_multi_tf


@pytest.mark.slow
@pytest.mark.integration
def test_full_pipeline_smoke(tmp_path):
    """End-to-end smoke test: synthetic data -> Stage 1 -> Stage 2 -> analysis -> save."""
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    symbols = ["BTC/USDT", "ETH/USDT"]

    # ── 1. Generate synthetic data for 2 pairs ──
    # Need >= ANCHORED_WF_MIN_DATA_HOURS (4000) bars for AWF splits.
    # Use 5000 bars with different seeds for different price behavior.
    pair_data = {}
    for i, sym in enumerate(symbols):
        df_1h = make_1h_ohlcv_pd(n_bars=5000, seed=42 + i)
        pair_data[sym] = resample_to_multi_tf(df_1h)

    # Verify data structure before proceeding
    for sym in symbols:
        assert "1h" in pair_data[sym]
        assert "4h" in pair_data[sym]
        assert "8h" in pair_data[sym]
        assert "1d" in pair_data[sym]
        assert len(pair_data[sym]["1h"]) == 5000

    # ── 2. Stage 1: optimize each pair ──
    from mqe.stage1 import run_stage1_pair

    stage1_results = {}
    for sym in symbols:
        result = run_stage1_pair(sym, pair_data[sym], n_trials=50, seed=42)
        stage1_results[sym] = result

    # Verify Stage 1 output: all 14 strategy params present
    strategy_param_keys = {
        "macd_fast", "macd_slow", "macd_signal",
        "rsi_period", "rsi_lower", "rsi_upper", "rsi_lookback",
        "trend_tf", "trend_strict", "allow_flip",
        "adx_threshold", "trail_mult", "hard_stop_mult", "max_hold_bars",
    }
    for sym, res in stage1_results.items():
        for key in strategy_param_keys:
            assert key in res, f"Missing strategy param '{key}' for {sym}"
        assert res.get("n_trials_completed", 0) > 0, f"No completed trials for {sym}"
        assert res["symbol"] == sym

    # ── 3. Re-compute signals with best params ──
    from mqe.optimize import _extract_strategy_params, precompute_all_signals

    pair_params = {sym: _extract_strategy_params(res) for sym, res in stage1_results.items()}

    # Verify _extract_strategy_params returns exactly the 14 strategy params
    for sym, params in pair_params.items():
        assert set(params.keys()) == strategy_param_keys, (
            f"Unexpected param keys for {sym}: {set(params.keys()) - strategy_param_keys}"
        )

    btc_params = pair_params.get("BTC/USDT")
    pair_signals = precompute_all_signals(pair_data, pair_params, btc_params)

    # Verify signals: 4-tuple per pair, correct dtypes and lengths
    for sym in symbols:
        assert sym in pair_signals, f"Missing signals for {sym}"
        buy, sell, atr_arr, strength = pair_signals[sym]
        assert len(buy) == 5000, f"Signal length mismatch for {sym}"
        assert len(sell) == 5000
        assert len(atr_arr) == 5000
        assert len(strength) == 5000
        assert buy.dtype == np.bool_
        assert sell.dtype == np.bool_
        assert atr_arr.dtype == np.float64
        assert strength.dtype == np.float64

    # ── 4. Stage 2: portfolio optimization ──
    from mqe.stage2 import run_stage2

    s2_result = run_stage2(pair_data, pair_signals, pair_params, n_trials=10, seed=42)

    # Verify Stage 2 output structure
    assert "portfolio_params" in s2_result
    assert "objectives" in s2_result
    assert "n_trials" in s2_result
    assert "pareto_front_size" in s2_result
    assert s2_result["n_trials"] == 10
    assert s2_result["pareto_front_size"] > 0

    # Verify portfolio params contain expected keys
    portfolio_expected_keys = {"max_concurrent", "cluster_max", "portfolio_heat", "corr_gate_threshold"}
    assert set(s2_result["portfolio_params"].keys()) == portfolio_expected_keys

    # Verify objectives contain expected keys
    objectives_expected_keys = {"portfolio_calmar", "worst_pair_calmar", "neg_overfit_penalty"}
    assert set(s2_result["objectives"].keys()) == objectives_expected_keys

    # ── 5. Save and reload results ──
    from mqe.io import load_json, save_json

    pipeline_result = {
        "symbols": symbols,
        "stage1_results": stage1_results,
        "stage2_results": s2_result,
    }
    save_json(tmp_path / "pipeline.json", pipeline_result)

    loaded = load_json(tmp_path / "pipeline.json")
    assert loaded["symbols"] == symbols
    assert "BTC/USDT" in loaded["stage1_results"]
    assert "ETH/USDT" in loaded["stage1_results"]
    assert "portfolio_params" in loaded["stage2_results"]

    # ── 6. Analysis ──
    from mqe.analyze import analyze_run

    analysis = analyze_run({
        "stage1_results": stage1_results,
        "stage2_results": s2_result,
    })

    assert "per_pair" in analysis
    assert "portfolio" in analysis
    assert len(analysis["per_pair"]) == len(symbols)

    # Verify per-pair analysis structure
    for pair_analysis in analysis["per_pair"]:
        assert "symbol" in pair_analysis
        assert "verdict" in pair_analysis
        assert pair_analysis["verdict"] in ("PASS", "WARN", "FAIL")
        assert "warnings" in pair_analysis
        assert "failures" in pair_analysis
        assert "metrics_summary" in pair_analysis

    # Verify portfolio analysis structure
    portfolio_analysis = analysis["portfolio"]
    assert "verdict" in portfolio_analysis
    assert portfolio_analysis["verdict"] in ("PASS", "WARN", "FAIL")
    assert "portfolio_calmar" in portfolio_analysis
    assert "worst_pair_calmar" in portfolio_analysis
    assert "portfolio_params" in portfolio_analysis
