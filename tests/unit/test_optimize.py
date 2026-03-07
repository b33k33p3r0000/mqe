"""Unit tests for MQE optimize pipeline helpers."""

from unittest.mock import patch

from mqe.optimize import assign_tiers, compute_parallelism


class TestWFEvalFunction:
    def test_run_wf_evaluation_callable(self):
        """WF eval function exists and is callable."""
        from mqe.optimize import run_wf_evaluation
        assert callable(run_wf_evaluation)

    def test_compute_wf_ceiling_callable(self):
        """compute_wf_ceiling function exists and returns tuple."""
        from mqe.optimize import compute_wf_ceiling
        ceiling, n_windows = compute_wf_ceiling(50000)
        assert isinstance(ceiling, float)
        assert isinstance(n_windows, int)
        assert 0.0 < ceiling <= 1.0
        assert n_windows >= 1


class TestComputeParallelism:
    """Tests for adaptive parallelism calculation."""

    @patch("mqe.optimize.os.cpu_count", return_value=10)
    def test_3_pairs_10_cores(self, _mock):
        """3 pairs, 10 cores: each pair gets 3 trial threads."""
        workers, jobs = compute_parallelism(n_pairs=3)
        assert workers == 3
        assert jobs == 3
        assert workers * jobs <= 10

    @patch("mqe.optimize.os.cpu_count", return_value=10)
    def test_15_pairs_10_cores(self, _mock):
        """15 pairs, 10 cores: 4 concurrent pairs, 2 jobs each, rest queued."""
        workers, jobs = compute_parallelism(n_pairs=15)
        # usable = 9, max_workers = min(15, 9//2) = 4, n_jobs = 9//4 = 2
        assert workers == 4
        assert jobs == 2

    @patch("mqe.optimize.os.cpu_count", return_value=16)
    def test_3_pairs_16_cores(self, _mock):
        """3 pairs, 16 cores: each pair gets 3 trial threads (capped)."""
        workers, jobs = compute_parallelism(n_pairs=3)
        assert workers == 3
        assert jobs == 3

    @patch("mqe.optimize.os.cpu_count", return_value=12)
    def test_15_pairs_12_cores(self, _mock):
        """15 pairs, 12 cores: 5 concurrent pairs, 2 jobs each."""
        workers, jobs = compute_parallelism(n_pairs=15)
        # usable = 11, max_workers = min(15, 11//2) = 5, n_jobs = 11//5 = 2
        assert workers == 5
        assert jobs == 2

    def test_explicit_overrides(self):
        """Explicit max_workers and n_jobs override auto-calculation."""
        workers, jobs = compute_parallelism(
            n_pairs=3, max_workers=2, n_jobs=4,
        )
        assert workers == 2
        assert jobs == 4

    @patch("mqe.optimize.os.cpu_count", return_value=10)
    def test_explicit_workers_auto_jobs(self, _mock):
        """Explicit max_workers, auto n_jobs."""
        workers, jobs = compute_parallelism(n_pairs=3, max_workers=3)
        assert workers == 3
        assert jobs == 3

    @patch("mqe.optimize.os.cpu_count", return_value=4)
    def test_1_pair_4_cores(self, _mock):
        """1 pair, 4 cores: gets 3 trial threads."""
        workers, jobs = compute_parallelism(n_pairs=1)
        assert workers == 1
        assert jobs == 3

    @patch("mqe.optimize.os.cpu_count", return_value=None)
    def test_cpu_count_none_fallback(self, _mock):
        """cpu_count returns None (e.g., Docker): falls back to 4."""
        workers, jobs = compute_parallelism(n_pairs=2)
        assert workers >= 1
        assert jobs >= 1

    @patch("mqe.optimize.os.cpu_count", return_value=8)
    def test_queuing_15_pairs_8_cores(self, _mock):
        """15 pairs on 8 cores: only 3 active, 12 queued, each gets 2 jobs."""
        workers, jobs = compute_parallelism(n_pairs=15)
        # usable = 7, max_workers = min(15, 7//2) = 3, n_jobs = 7//3 = 2
        assert workers == 3
        assert jobs == 2
        assert workers * jobs <= 8

    @patch("mqe.optimize.os.cpu_count", return_value=30)
    def test_cluster_30_cores(self, _mock):
        """3x Mac Mini (30 cores): 3 pairs get 3 jobs each (capped)."""
        workers, jobs = compute_parallelism(n_pairs=3)
        assert workers == 3
        assert jobs == 3

    @patch("mqe.optimize.os.cpu_count", return_value=30)
    def test_cluster_15_pairs_30_cores(self, _mock):
        """3x Mac Mini (30 cores), 15 pairs: 14 active, 2 jobs each."""
        workers, jobs = compute_parallelism(n_pairs=15)
        # usable = 29, max_workers = min(15, 29//2) = 14, n_jobs = 29//14 = 2
        assert workers == 14
        assert jobs == 2


class TestAssignTiers:
    """Tests for auto quality tiering based on eval Sharpe."""

    def test_assign_tiers_basic(self):
        per_pair_metrics = {
            "BTC/USDT": {"sharpe_ratio_equity_based": 1.8},
            "ETH/USDT": {"sharpe_ratio_equity_based": 1.0},
            "SOL/USDT": {"sharpe_ratio_equity_based": 0.3},
            "ARB/USDT": {"sharpe_ratio_equity_based": -0.5},
        }
        tiers = assign_tiers(per_pair_metrics)
        assert tiers["BTC/USDT"]["tier"] == "A"
        assert tiers["BTC/USDT"]["multiplier"] == 1.0
        assert tiers["ETH/USDT"]["tier"] == "B"
        assert tiers["ETH/USDT"]["multiplier"] == 0.6
        assert tiers["SOL/USDT"]["tier"] == "C"
        assert tiers["SOL/USDT"]["multiplier"] == 0.25
        assert tiers["ARB/USDT"]["tier"] == "X"
        assert tiers["ARB/USDT"]["multiplier"] == 0.0

    def test_assign_tiers_boundary_a(self):
        metrics = {"SYM": {"sharpe_ratio_equity_based": 1.5}}
        tiers = assign_tiers(metrics)
        assert tiers["SYM"]["tier"] == "A"

    def test_assign_tiers_boundary_b(self):
        metrics = {"SYM": {"sharpe_ratio_equity_based": 0.5}}
        tiers = assign_tiers(metrics)
        assert tiers["SYM"]["tier"] == "B"

    def test_assign_tiers_boundary_c(self):
        metrics = {"SYM": {"sharpe_ratio_equity_based": 0.0}}
        tiers = assign_tiers(metrics)
        assert tiers["SYM"]["tier"] == "C"

    def test_assign_tiers_negative_is_x(self):
        metrics = {"SYM": {"sharpe_ratio_equity_based": -0.01}}
        tiers = assign_tiers(metrics)
        assert tiers["SYM"]["tier"] == "X"
        assert tiers["SYM"]["multiplier"] == 0.0
