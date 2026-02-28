"""Integration test for MQE optimization pipeline."""

import pytest
from unittest.mock import patch, MagicMock

from mqe.optimize import run_pipeline
from tests.conftest import make_1h_ohlcv_pd, resample_to_multi_tf


@pytest.mark.integration
class TestPipeline:
    def test_pipeline_runs_end_to_end(self, tmp_path):
        """Small-scale pipeline: 2 pairs, 10 trials S1, 5 trials S2."""
        n = 5000
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)

        # Mock data fetching to use synthetic data
        mock_data = {"BTC/USDT": data, "ETH/USDT": data}

        with patch("mqe.optimize.fetch_all_data", return_value=mock_data):
            result = run_pipeline(
                symbols=["BTC/USDT", "ETH/USDT"],
                stage1_trials=10,
                stage2_trials=5,
                output_dir=tmp_path,
            )

        assert "stage1_results" in result
        assert "stage2_results" in result
        assert "BTC/USDT" in result["stage1_results"]
        assert "ETH/USDT" in result["stage1_results"]

    def test_pipeline_saves_results(self, tmp_path):
        """Verify pipeline saves JSON output files."""
        n = 5000
        df = make_1h_ohlcv_pd(n_bars=n, seed=42)
        data = resample_to_multi_tf(df)
        mock_data = {"BTC/USDT": data, "ETH/USDT": data}

        with patch("mqe.optimize.fetch_all_data", return_value=mock_data):
            run_pipeline(
                symbols=["BTC/USDT", "ETH/USDT"],
                stage1_trials=10,
                stage2_trials=5,
                output_dir=tmp_path,
            )

        # Check output files exist
        assert (tmp_path / "stage1").exists()
        assert (tmp_path / "stage1" / "BTC_USDT.json").exists()
        assert (tmp_path / "stage1" / "ETH_USDT.json").exists()
        assert (tmp_path / "stage2_result.json").exists()
        assert (tmp_path / "pipeline_result.json").exists()
