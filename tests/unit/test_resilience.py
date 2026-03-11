# tests/unit/test_resilience.py
"""Tests for agent/resilience.py — Resilience Score computation."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add agent/ to path so we can import resilience
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))
import resilience


@pytest.fixture
def good_run(tmp_path):
    """A healthy run with good metrics across all dimensions."""
    results_dir = tmp_path / "results" / "20260310_120000"
    eval_dir = results_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT",
                     "BNB/USDT", "LINK/USDT", "SUI/USDT", "DOT/USDT",
                     "ADA/USDT", "NEAR/USDT", "LTC/USDT", "APT/USDT",
                     "ARB/USDT", "OP/USDT", "INJ/USDT"],
        "tier_assignments": {
            "BTC/USDT": {"tier": "A", "multiplier": 1.0},
            "ETH/USDT": {"tier": "A", "multiplier": 1.0},
            "SOL/USDT": {"tier": "A", "multiplier": 1.0},
            "XRP/USDT": {"tier": "B", "multiplier": 0.6},
            "BNB/USDT": {"tier": "B", "multiplier": 0.6},
            "LINK/USDT": {"tier": "A", "multiplier": 1.0},
            "SUI/USDT": {"tier": "B", "multiplier": 0.6},
            "DOT/USDT": {"tier": "C", "multiplier": 0.25},
            "ADA/USDT": {"tier": "A", "multiplier": 1.0},
            "NEAR/USDT": {"tier": "B", "multiplier": 0.6},
            "LTC/USDT": {"tier": "C", "multiplier": 0.25},
            "APT/USDT": {"tier": "X", "multiplier": 0.0},
            "ARB/USDT": {"tier": "X", "multiplier": 0.0},
            "OP/USDT": {"tier": "X", "multiplier": 0.0},
            "INJ/USDT": {"tier": "B", "multiplier": 0.6},
        },
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 1.18, "s1_sharpe": 2.98},
            "ETH/USDT": {"degradation_ratio": 1.05, "s1_sharpe": 2.50},
            "SOL/USDT": {"degradation_ratio": 0.95, "s1_sharpe": 3.10},
            "XRP/USDT": {"degradation_ratio": 1.30, "s1_sharpe": 1.80},
            "BNB/USDT": {"degradation_ratio": 1.52, "s1_sharpe": 1.20},
            "LINK/USDT": {"degradation_ratio": 1.10, "s1_sharpe": 2.00},
            "SUI/USDT": {"degradation_ratio": 0.80, "s1_sharpe": 2.50},
            "DOT/USDT": {"degradation_ratio": 1.40, "s1_sharpe": 1.50},
            "ADA/USDT": {"degradation_ratio": 1.00, "s1_sharpe": 2.20},
            "NEAR/USDT": {"degradation_ratio": 1.25, "s1_sharpe": 1.90},
            "LTC/USDT": {"degradation_ratio": 1.60, "s1_sharpe": 1.10},
            "APT/USDT": {"degradation_ratio": 2.50, "s1_sharpe": 0.80},
            "ARB/USDT": {"degradation_ratio": 3.10, "s1_sharpe": 0.50},
            "OP/USDT": {"degradation_ratio": 4.00, "s1_sharpe": 0.30},
            "INJ/USDT": {"degradation_ratio": 1.35, "s1_sharpe": 1.70},
        },
    }

    portfolio_metrics = {
        "calmar_ratio": 6.30,
        "portfolio_max_drawdown": 0.044,
        "max_drawdown": -4.63,
        "sortino_ratio": 4.50,
        "profitable_months_ratio": 0.78,
        "monthly_returns": [1308.47, -192.99, 2500.0, 800.0, -500.0,
                            1200.0, 300.0, -100.0, 1500.0, 600.0,
                            -300.0, 900.0, 1100.0, -50.0, 700.0,
                            400.0, -200.0, 1000.0],
        "sharpe_ratio_equity_based": 2.65,
        "trades": 4387,
        "equity": 182910.21,
    }

    per_pair_metrics = {}
    for sym in pipeline["symbols"]:
        tier = pipeline["tier_assignments"][sym]["tier"]
        sharpe = 2.5 if tier in ("A", "B") else (0.8 if tier == "C" else -0.5)
        per_pair_metrics[sym] = {
            "sharpe_ratio_equity_based": sharpe,
            "calmar_ratio": 4.0 if tier != "X" else -1.0,
        }

    (results_dir / "pipeline_result.json").write_text(json.dumps(pipeline))
    (eval_dir / "portfolio_metrics.json").write_text(json.dumps(portfolio_metrics))
    (eval_dir / "per_pair_metrics.json").write_text(json.dumps(per_pair_metrics))

    return results_dir


@pytest.fixture
def bad_run(tmp_path):
    """A run that triggers Hard FAIL (negative Calmar)."""
    results_dir = tmp_path / "results" / "20260310_130000"
    eval_dir = results_dir / "evaluation"
    eval_dir.mkdir(parents=True)

    pipeline = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "tier_assignments": {
            "BTC/USDT": {"tier": "A", "multiplier": 1.0},
            "ETH/USDT": {"tier": "X", "multiplier": 0.0},
        },
        "wf_eval_metrics": {
            "BTC/USDT": {"degradation_ratio": 1.0, "s1_sharpe": 1.0},
            "ETH/USDT": {"degradation_ratio": 6.0, "s1_sharpe": 0.1},
        },
    }

    portfolio_metrics = {
        "calmar_ratio": -0.5,
        "portfolio_max_drawdown": 0.25,
        "max_drawdown": -25.0,
        "sortino_ratio": -1.2,
        "profitable_months_ratio": 0.30,
        "monthly_returns": [-500.0, -200.0, 100.0, -800.0, -300.0,
                            50.0, -400.0, -100.0, -600.0, 200.0],
        "sharpe_ratio_equity_based": -0.8,
        "trades": 50,
        "equity": 75000.0,
    }

    per_pair_metrics = {
        "BTC/USDT": {"sharpe_ratio_equity_based": 0.5, "calmar_ratio": 0.3},
        "ETH/USDT": {"sharpe_ratio_equity_based": -2.0, "calmar_ratio": -3.0},
    }

    (results_dir / "pipeline_result.json").write_text(json.dumps(pipeline))
    (eval_dir / "portfolio_metrics.json").write_text(json.dumps(portfolio_metrics))
    (eval_dir / "per_pair_metrics.json").write_text(json.dumps(per_pair_metrics))

    return results_dir


class TestDimensionScores:
    """Test individual dimension scoring functions."""

    def test_calmar_score_good(self):
        assert resilience.score_calmar(6.30) > 80

    def test_calmar_score_at_max(self):
        assert resilience.score_calmar(8.0) == 100.0

    def test_calmar_score_at_min(self):
        assert resilience.score_calmar(0.5) == 0.0

    def test_calmar_score_hard_fail(self):
        score, hard_fail = resilience.score_calmar(-0.5, return_hard_fail=True)
        assert hard_fail is True

    def test_calmar_score_log_scale(self):
        # Log scale: score at 4.0 should be > 50 (not exactly 50 as linear would give)
        score = resilience.score_calmar(4.0)
        assert 60 < score < 95

    def test_drawdown_score_good(self):
        # DD of 4.4% (fraction 0.044) — better than -5% threshold
        assert resilience.score_drawdown(0.044) == 100.0

    def test_drawdown_score_at_worst(self):
        assert resilience.score_drawdown(0.15) == 0.0

    def test_drawdown_score_hard_fail(self):
        score, hard_fail = resilience.score_drawdown(0.25, return_hard_fail=True)
        assert hard_fail is True

    def test_drawdown_score_midpoint(self):
        # 10% DD (fraction 0.10) — midpoint between 5% and 15%
        score = resilience.score_drawdown(0.10)
        assert 45 < score < 55

    def test_wf_degradation_score_perfect(self):
        # Median ratio 1.0 → perfect
        assert resilience.score_wf_degradation(1.0) == 100.0

    def test_wf_degradation_score_capped_below_one(self):
        # Ratio < 1.0 → capped to 1.0 → score 100
        assert resilience.score_wf_degradation(0.8) == 100.0

    def test_wf_degradation_score_at_worst(self):
        assert resilience.score_wf_degradation(3.0) == 0.0

    def test_wf_degradation_hard_fail(self):
        score, hard_fail = resilience.score_wf_degradation(5.5, return_hard_fail=True)
        assert hard_fail is True

    def test_pair_survival_score_good(self):
        assert resilience.score_pair_survival(14) == 100.0

    def test_pair_survival_score_at_max(self):
        assert resilience.score_pair_survival(12) == 100.0

    def test_pair_survival_score_at_min(self):
        assert resilience.score_pair_survival(5) == 0.0

    def test_pair_survival_hard_fail(self):
        score, hard_fail = resilience.score_pair_survival(2, return_hard_fail=True)
        assert hard_fail is True

    def test_monthly_consistency_score_good(self):
        score = resilience.score_monthly_consistency(0.78, 500.0)
        assert 50 < score <= 100

    def test_monthly_consistency_hard_fail(self):
        score, hard_fail = resilience.score_monthly_consistency(
            0.35, 1000.0, return_hard_fail=True
        )
        assert hard_fail is True

    def test_sortino_score_good(self):
        assert resilience.score_sortino(4.5) == 100.0

    def test_sortino_score_at_min(self):
        assert resilience.score_sortino(0.5) == 0.0

    def test_sortino_hard_fail(self):
        score, hard_fail = resilience.score_sortino(-0.5, return_hard_fail=True)
        assert hard_fail is True


class TestCompositeScore:
    """Test full Resilience Score computation from result files."""

    def test_good_run_score(self, good_run):
        result = resilience.compute_score(good_run)
        assert not result["data_incomplete"]
        assert not result["hard_fail"]
        assert result["score"] > 50
        assert len(result["dimensions"]) == 6

    def test_bad_run_hard_fail(self, bad_run):
        result = resilience.compute_score(bad_run)
        assert result["hard_fail"] is True
        assert result["score"] == 0.0
        assert len(result["hard_fail_reasons"]) > 0

    def test_missing_files_returns_incomplete(self, tmp_path):
        result = resilience.compute_score(tmp_path / "nonexistent")
        assert result["data_incomplete"] is True
        assert result["score"] == 0.0

    def test_weights_sum_to_one(self):
        total = sum(resilience.WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6

    def test_score_is_within_bounds(self, good_run):
        """Score should be between 0 and 100."""
        result = resilience.compute_score(good_run)
        assert 0.0 <= result["score"] <= 100.0

    def test_surviving_pairs_count(self, good_run):
        result = resilience.compute_score(good_run)
        # good_run has 3 X-tier pairs, 12 non-X with positive sharpe
        surv = result["dimensions"]["pair_survival"]["raw"]
        assert surv == 12

    def test_wf_degradation_excludes_x_tier(self, good_run):
        result = resilience.compute_score(good_run)
        # X-tier pairs (APT, ARB, OP) should be excluded from median
        wf_raw = result["dimensions"]["wf_degradation"]["raw"]
        # Median of non-X pairs only
        assert wf_raw > 0


class TestHelpers:
    """Test helper functions."""

    def test_compute_monthly_std(self):
        returns = [100.0, -50.0, 200.0, -100.0, 150.0]
        std = resilience.compute_monthly_std(returns)
        assert std > 0

    def test_compute_monthly_std_empty(self):
        assert resilience.compute_monthly_std([]) == 0.0

    def test_compute_wf_degradation_median_excludes_x(self):
        pipeline = {
            "tier_assignments": {
                "A": {"tier": "A"},
                "B": {"tier": "B"},
                "X": {"tier": "X"},
            },
            "wf_eval_metrics": {
                "A": {"degradation_ratio": 1.0},
                "B": {"degradation_ratio": 2.0},
                "X": {"degradation_ratio": 10.0},
            },
        }
        median = resilience.compute_wf_degradation_median(pipeline)
        assert median == 1.5  # Median of [1.0, 2.0], X excluded

    def test_count_surviving_pairs(self):
        pipeline = {
            "tier_assignments": {
                "A": {"tier": "A"},
                "B": {"tier": "X"},
            },
        }
        per_pair = {
            "A": {"sharpe_ratio_equity_based": 2.0},
            "B": {"sharpe_ratio_equity_based": 1.0},
        }
        count = resilience.count_surviving_pairs(pipeline, per_pair)
        assert count == 1  # Only A survives (B is X-tier)


class TestCLI:
    """Test CLI entry points."""

    def test_init_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(resilience, "AGENT_DIR", tmp_path)
        resilience.cmd_init_state()
        state = json.loads((tmp_path / "state.json").read_text())
        assert state["iteration"] == 0
        assert state["level"] == "L1"
        assert state["phase"] == "deciding"

    def test_write_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(resilience, "AGENT_DIR", tmp_path)
        (tmp_path / "state.json").write_text('{"iteration": 0}')
        resilience.cmd_write_state("iteration", "5")
        state = json.loads((tmp_path / "state.json").read_text())
        assert state["iteration"] == 5

    def test_compute_score_cli(self, good_run, capsys):
        resilience.cmd_compute_score(str(good_run))
        output = json.loads(capsys.readouterr().out)
        assert "score" in output
        assert output["score"] > 0
