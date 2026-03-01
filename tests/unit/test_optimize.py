"""Unit tests for MQE optimize pipeline helpers."""

from unittest.mock import patch

from mqe.optimize import compute_parallelism


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
        """3 pairs, 16 cores: each pair gets 5 trial threads."""
        workers, jobs = compute_parallelism(n_pairs=3)
        assert workers == 3
        assert jobs == 5

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
        """3x Mac Mini (30 cores): 3 pairs get 9 jobs each."""
        workers, jobs = compute_parallelism(n_pairs=3)
        assert workers == 3
        assert jobs == 9

    @patch("mqe.optimize.os.cpu_count", return_value=30)
    def test_cluster_15_pairs_30_cores(self, _mock):
        """3x Mac Mini (30 cores), 15 pairs: 14 active, 2 jobs each."""
        workers, jobs = compute_parallelism(n_pairs=15)
        # usable = 29, max_workers = min(15, 29//2) = 14, n_jobs = 29//14 = 2
        assert workers == 14
        assert jobs == 2
