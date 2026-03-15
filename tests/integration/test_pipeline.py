"""Integration tests for MQE optimization pipeline.

End-to-end tests: synthetic data -> Stage 1 -> Stage 2 -> evaluation -> save.
Uses synthetic random-walk OHLCV data (no API calls).
"""

import numpy as np
import optuna
import pytest
from unittest.mock import patch

from mqe.optimize import run_pipeline
from tests.conftest import make_1h_ohlcv_pd, resample_to_multi_tf


def _make_mock_data(symbols, n_bars=5000, base_seed=42):
    """Build mock pair_data dict with different seeds per pair."""
    mock_data = {}
    for i, sym in enumerate(symbols):
        df_1h = make_1h_ohlcv_pd(n_bars=n_bars, seed=base_seed + i)
        mock_data[sym] = resample_to_multi_tf(df_1h)
    return mock_data


@pytest.mark.slow
@pytest.mark.integration
class TestPipeline:
    """End-to-end pipeline integration tests."""

    SYMBOLS = ["BTC/USDT", "ETH/USDT"]
    S1_TRIALS = 10
    S2_TRIALS = 3

    def test_pipeline_end_to_end(self, tmp_path):
        """S1 -> S2 -> evaluation -> save pipeline runs and produces correct result structure."""
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        mock_data = _make_mock_data(self.SYMBOLS)

        with patch("mqe.optimize.fetch_all_data", return_value=mock_data):
            result = run_pipeline(
                symbols=self.SYMBOLS,
                stage1_trials=self.S1_TRIALS,
                stage2_trials=self.S2_TRIALS,
                output_dir=tmp_path,
            )

        # Top-level keys
        assert "stage1_results" in result
        assert "stage2_results" in result

        # Stage 1: each symbol present with strategy params
        for sym in self.SYMBOLS:
            assert sym in result["stage1_results"]
            s1 = result["stage1_results"][sym]
            assert s1["symbol"] == sym
            assert s1.get("n_trials_completed", 0) > 0

        # Stage 2: portfolio params and objectives
        s2 = result["stage2_results"]
        assert "portfolio_params" in s2
        assert "objectives" in s2
        assert s2.get("pareto_front_size", 0) > 0

        portfolio_expected_keys = {"max_concurrent", "cluster_max", "portfolio_heat", "corr_gate_threshold"}
        assert set(s2["portfolio_params"].keys()) == portfolio_expected_keys

        objectives_expected_keys = {"portfolio_calmar", "worst_pair_calmar", "neg_overfit_penalty"}
        assert set(s2["objectives"].keys()) == objectives_expected_keys

    def test_pipeline_output_files(self, tmp_path):
        """Pipeline saves expected JSON output files to disk."""
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        mock_data = _make_mock_data(self.SYMBOLS)

        with patch("mqe.optimize.fetch_all_data", return_value=mock_data):
            run_pipeline(
                symbols=self.SYMBOLS,
                stage1_trials=self.S1_TRIALS,
                stage2_trials=self.S2_TRIALS,
                output_dir=tmp_path,
            )

        # Stage 1 per-pair results
        assert (tmp_path / "stage1").exists()
        assert (tmp_path / "stage1" / "BTC_USDT.json").exists()
        assert (tmp_path / "stage1" / "ETH_USDT.json").exists()

        # Stage 2 and combined results
        assert (tmp_path / "stage2_result.json").exists()
        assert (tmp_path / "pipeline_result.json").exists()

    def test_pipeline_analysis_structure(self, tmp_path):
        """Pipeline analysis (via analyze_run) produces correct per-pair and portfolio verdicts."""
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        mock_data = _make_mock_data(self.SYMBOLS)

        with patch("mqe.optimize.fetch_all_data", return_value=mock_data):
            result = run_pipeline(
                symbols=self.SYMBOLS,
                stage1_trials=self.S1_TRIALS,
                stage2_trials=self.S2_TRIALS,
                output_dir=tmp_path,
            )

        # Run analysis on the pipeline result
        from mqe.analyze import analyze_run

        analysis = analyze_run(result)

        assert "per_pair" in analysis
        assert "portfolio" in analysis
        assert len(analysis["per_pair"]) == len(self.SYMBOLS)

        # Per-pair structure
        for pair_analysis in analysis["per_pair"]:
            assert "symbol" in pair_analysis
            assert "verdict" in pair_analysis
            assert pair_analysis["verdict"] in ("PASS", "WARN", "FAIL")

        # Portfolio structure
        assert "verdict" in analysis["portfolio"]
        assert analysis["portfolio"]["verdict"] in ("PASS", "WARN", "FAIL")
