#!/usr/bin/env python3
"""Resilience Score computation for MQE Improvement Agent.

Reads MQE pipeline results and computes a composite 0-100 score
across 6 dimensions: Calmar, Drawdown, WF Degradation, Pair Survival,
Monthly Consistency, and Sortino.

Usage:
    python3 agent/resilience.py compute-score <results_dir>
    python3 agent/resilience.py init-state
    python3 agent/resilience.py write-state <field> <value>
"""
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# ── Weights ──────────────────────────────────────────────────────────

WEIGHTS = {
    "portfolio_calmar": 0.25,
    "max_drawdown": 0.20,
    "wf_degradation": 0.20,
    "pair_survival": 0.15,
    "monthly_consistency": 0.10,
    "sortino": 0.10,
}


# ── Dimension Scoring ────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _linear(value: float, worst: float, best: float) -> float:
    """Linear interpolation: worst→0, best→100."""
    if best == worst:
        return 100.0 if value >= best else 0.0
    return _clamp(100.0 * (value - worst) / (best - worst))


def score_calmar(
    calmar: float, return_hard_fail: bool = False
) -> Union[float, Tuple[float, bool]]:
    """Portfolio Calmar score (log scale). Range 0.5-8.0, Hard FAIL if < 0."""
    hard_fail = calmar < 0
    if hard_fail:
        return (0.0, True) if return_hard_fail else 0.0
    # Log scale: log(calmar)/log(8.0) mapped from 0.5 to 8.0
    if calmar <= 0.5:
        score = 0.0
    elif calmar >= 8.0:
        score = 100.0
    else:
        log_min = math.log(0.5)
        log_max = math.log(8.0)
        score = _clamp(100.0 * (math.log(calmar) - log_min) / (log_max - log_min))
    return (score, False) if return_hard_fail else score


def score_drawdown(
    dd_fraction: float, return_hard_fail: bool = False
) -> Union[float, Tuple[float, bool]]:
    """Max Drawdown score. dd_fraction is positive (e.g. 0.044 = 4.4%).
    Best: <= 0.05 (5%), Worst: 0.15 (15%), Hard FAIL: > 0.20 (20%)."""
    hard_fail = dd_fraction > 0.20
    if hard_fail:
        return (0.0, True) if return_hard_fail else 0.0
    # Lower DD is better: 0.05→100, 0.15→0
    score = _linear(dd_fraction, worst=0.15, best=0.05)
    return (score, False) if return_hard_fail else score


def score_wf_degradation(
    median_ratio: float, return_hard_fail: bool = False
) -> Union[float, Tuple[float, bool]]:
    """WF Degradation score. Ratio near 1.0 is perfect.
    Values < 1.0 capped to 1.0. Best: <= 1.2, Worst: >= 3.0, Hard FAIL: > 5.0."""
    hard_fail = median_ratio > 5.0
    if hard_fail:
        return (0.0, True) if return_hard_fail else 0.0
    # Cap below 1.0 (OOS better than S1 is fine)
    ratio = max(median_ratio, 1.0)
    score = _linear(ratio, worst=3.0, best=1.2)
    return (score, False) if return_hard_fail else score


def score_pair_survival(
    n_surviving: int, return_hard_fail: bool = False
) -> Union[float, Tuple[float, bool]]:
    """Pair Survival score. Best: >= 12, Worst: <= 5, Hard FAIL: < 3."""
    hard_fail = n_surviving < 3
    if hard_fail:
        return (0.0, True) if return_hard_fail else 0.0
    score = _linear(float(n_surviving), worst=5.0, best=12.0)
    return (score, False) if return_hard_fail else score


def score_monthly_consistency(
    profitable_ratio: float,
    monthly_std: float,
    return_hard_fail: bool = False,
) -> Union[float, Tuple[float, bool]]:
    """Monthly Consistency score. Composite of profitable_months_ratio (70%)
    and normalized monthly return std (30%).
    Hard FAIL: profitable_ratio < 0.40."""
    hard_fail = profitable_ratio < 0.40
    if hard_fail:
        return (0.0, True) if return_hard_fail else 0.0
    # Sub-score 1: profitable months ratio (50% → 0, 80% → 100)
    ratio_score = _linear(profitable_ratio, worst=0.50, best=0.80)
    # Sub-score 2: monthly std (lower is better). Map 0-10000 to 1.0-0.0
    # Using dollar std — 10000 is "very volatile", 0 is "perfectly smooth"
    std_normalized = _clamp(1.0 - monthly_std / 10000.0, 0.0, 1.0)
    std_score = std_normalized * 100.0
    score = ratio_score * 0.7 + std_score * 0.3
    return (_clamp(score), False) if return_hard_fail else _clamp(score)


def score_sortino(
    sortino: float, return_hard_fail: bool = False
) -> Union[float, Tuple[float, bool]]:
    """Sortino Ratio score. Best: >= 4.0, Worst: <= 0.5, Hard FAIL: < 0."""
    hard_fail = sortino < 0
    if hard_fail:
        return (0.0, True) if return_hard_fail else 0.0
    score = _linear(sortino, worst=0.5, best=4.0)
    return (score, False) if return_hard_fail else score


# ── Data Loading ─────────────────────────────────────────────────────

def load_results(results_dir: Path) -> Optional[Dict[str, Any]]:
    """Load all required files from a results directory.
    Returns None if critical files are missing."""
    pipeline_path = results_dir / "pipeline_result.json"
    portfolio_path = results_dir / "evaluation" / "portfolio_metrics.json"
    per_pair_path = results_dir / "evaluation" / "per_pair_metrics.json"

    for p in [pipeline_path, portfolio_path]:
        if not p.exists():
            return None

    try:
        pipeline = json.loads(pipeline_path.read_text())
        portfolio = json.loads(portfolio_path.read_text())
        per_pair = json.loads(per_pair_path.read_text()) if per_pair_path.exists() else {}
        return {
            "pipeline": pipeline,
            "portfolio": portfolio,
            "per_pair": per_pair,
        }
    except (json.JSONDecodeError, OSError):
        return None


# ── Composite Score ──────────────────────────────────────────────────

def compute_wf_degradation_median(
    pipeline: Dict[str, Any],
) -> Optional[float]:
    """Compute median degradation_ratio across non-X-tier pairs."""
    tier_assignments = pipeline.get("tier_assignments", {})
    wf_metrics = pipeline.get("wf_eval_metrics", {})

    ratios = []
    for symbol, tier_info in tier_assignments.items():
        if tier_info.get("tier") == "X":
            continue
        wf = wf_metrics.get(symbol, {})
        ratio = wf.get("degradation_ratio")
        if ratio is not None:
            ratios.append(ratio)

    if not ratios:
        return None
    ratios.sort()
    n = len(ratios)
    if n % 2 == 1:
        return ratios[n // 2]
    return (ratios[n // 2 - 1] + ratios[n // 2]) / 2.0


def count_surviving_pairs(
    pipeline: Dict[str, Any], per_pair: Dict[str, Any]
) -> int:
    """Count pairs with tier != X AND per-pair sharpe > 0."""
    tier_assignments = pipeline.get("tier_assignments", {})
    count = 0
    for symbol, tier_info in tier_assignments.items():
        if tier_info.get("tier") == "X":
            continue
        pair_metrics = per_pair.get(symbol, {})
        sharpe = pair_metrics.get("sharpe_ratio_equity_based", 0.0)
        if sharpe > 0:
            count += 1
    return count


def compute_monthly_std(monthly_returns: List[float]) -> float:
    """Compute standard deviation of monthly returns."""
    if not monthly_returns or len(monthly_returns) < 2:
        return 0.0
    mean = sum(monthly_returns) / len(monthly_returns)
    variance = sum((r - mean) ** 2 for r in monthly_returns) / (len(monthly_returns) - 1)
    return variance ** 0.5


def compute_score(results_dir: Path) -> Dict[str, Any]:
    """Compute full Resilience Score from a results directory.

    Returns:
        {
            "score": float (0-100),
            "dimensions": {name: {"score": float, "raw": float, "hard_fail": bool}},
            "hard_fail": bool,
            "hard_fail_reasons": [str],
            "data_incomplete": bool,
        }
    """
    data = load_results(results_dir)
    if data is None:
        return {
            "score": 0.0,
            "dimensions": {},
            "hard_fail": False,
            "hard_fail_reasons": [],
            "data_incomplete": True,
        }

    pipeline = data["pipeline"]
    portfolio = data["portfolio"]
    per_pair = data["per_pair"]

    hard_fail_reasons: List[str] = []

    # 1. Portfolio Calmar
    calmar_raw = portfolio.get("calmar_ratio", 0.0)
    calmar_score, calmar_hf = score_calmar(calmar_raw, return_hard_fail=True)
    if calmar_hf:
        hard_fail_reasons.append(f"Calmar < 0 ({calmar_raw:.2f})")

    # 2. Max Drawdown (portfolio_max_drawdown is fraction, positive)
    dd_raw = portfolio.get("portfolio_max_drawdown", 1.0)
    dd_score, dd_hf = score_drawdown(dd_raw, return_hard_fail=True)
    if dd_hf:
        hard_fail_reasons.append(f"DD > 20% ({dd_raw*100:.1f}%)")

    # 3. WF Degradation
    wf_median = compute_wf_degradation_median(pipeline)
    if wf_median is None:
        wf_median = 1.0  # Default to perfect if no data
    wf_score, wf_hf = score_wf_degradation(wf_median, return_hard_fail=True)
    if wf_hf:
        hard_fail_reasons.append(f"WF degradation > 5.0 ({wf_median:.2f})")

    # 4. Pair Survival
    n_surviving = count_surviving_pairs(pipeline, per_pair)
    surv_score, surv_hf = score_pair_survival(n_surviving, return_hard_fail=True)
    if surv_hf:
        hard_fail_reasons.append(f"< 3 surviving pairs ({n_surviving})")

    # 5. Monthly Consistency
    profitable_ratio = portfolio.get("profitable_months_ratio", 0.0)
    monthly_returns = portfolio.get("monthly_returns", [])
    monthly_std = compute_monthly_std(monthly_returns)
    consist_score, consist_hf = score_monthly_consistency(
        profitable_ratio, monthly_std, return_hard_fail=True
    )
    if consist_hf:
        hard_fail_reasons.append(
            f"Profitable months < 40% ({profitable_ratio*100:.0f}%)"
        )

    # 6. Sortino
    sortino_raw = portfolio.get("sortino_ratio", 0.0)
    sortino_score, sortino_hf = score_sortino(sortino_raw, return_hard_fail=True)
    if sortino_hf:
        hard_fail_reasons.append(f"Sortino < 0 ({sortino_raw:.2f})")

    # Build dimensions dict
    dimensions = {
        "portfolio_calmar": {"score": calmar_score, "raw": calmar_raw, "hard_fail": calmar_hf},
        "max_drawdown": {"score": dd_score, "raw": dd_raw, "hard_fail": dd_hf},
        "wf_degradation": {"score": wf_score, "raw": wf_median, "hard_fail": wf_hf},
        "pair_survival": {"score": surv_score, "raw": n_surviving, "hard_fail": surv_hf},
        "monthly_consistency": {"score": consist_score, "raw": profitable_ratio, "hard_fail": consist_hf},
        "sortino": {"score": sortino_score, "raw": sortino_raw, "hard_fail": sortino_hf},
    }

    has_hard_fail = len(hard_fail_reasons) > 0

    if has_hard_fail:
        composite = 0.0
    else:
        composite = sum(
            dimensions[dim]["score"] * weight
            for dim, weight in WEIGHTS.items()
        )

    return {
        "score": round(composite, 1),
        "dimensions": dimensions,
        "hard_fail": has_hard_fail,
        "hard_fail_reasons": hard_fail_reasons,
        "data_incomplete": False,
    }


# ── State Management (CLI helpers for agent.sh) ─────────────────────

AGENT_DIR = Path(__file__).resolve().parent


def cmd_init_state() -> None:
    """Create initial state.json."""
    import time

    state = {
        "iteration": 0,
        "level": "L1",
        "best_score": 0.0,
        "best_run": "",
        "start_time": time.time(),
        "phase": "deciding",
        "current_branch": "agent/best",
        "consecutive_no_improvement": 0,
        "total_promotes": 0,
        "total_rollbacks": 0,
        "consecutive_crashes": 0,
    }
    state_path = AGENT_DIR / "state.json"
    state_path.write_text(json.dumps(state, indent=2))
    print(json.dumps(state))


def cmd_write_state(field: str, value: str) -> None:
    """Update a single field in state.json."""
    state_path = AGENT_DIR / "state.json"
    state = json.loads(state_path.read_text())
    # Auto-detect type
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed = value
    state[field] = parsed
    state_path.write_text(json.dumps(state, indent=2))


def cmd_read_state() -> None:
    """Print state.json to stdout."""
    state_path = AGENT_DIR / "state.json"
    if state_path.exists():
        print(state_path.read_text())
    else:
        print("{}")


def cmd_compute_score(results_dir: str) -> None:
    """Compute and print Resilience Score for a results directory."""
    result = compute_score(Path(results_dir))
    print(json.dumps(result, indent=2))


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: resilience.py <command> [args]")
        print("Commands: compute-score, init-state, write-state, read-state")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "compute-score":
        if len(sys.argv) < 3:
            print("Usage: resilience.py compute-score <results_dir>")
            sys.exit(1)
        cmd_compute_score(sys.argv[2])
    elif cmd == "init-state":
        cmd_init_state()
    elif cmd == "write-state":
        if len(sys.argv) < 4:
            print("Usage: resilience.py write-state <field> <value>")
            sys.exit(1)
        cmd_write_state(sys.argv[2], sys.argv[3])
    elif cmd == "read-state":
        cmd_read_state()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
