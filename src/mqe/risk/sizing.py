"""
MQE Position Sizing — Inverse-volatility with correlation haircut.

Sizing formula:
  1. Base weight = 1 / atr_1h_pct (inverse volatility)
  2. Normalize across all active symbols to sum to 1.0
  3. Apply correlation haircut: reduce if correlated pairs already open
  4. Apply OI/MC danger penalty: 30% reduction if OI/MC > 6%
  5. Clip to [POSITION_MIN_PCT, POSITION_MAX_PCT] of equity
"""

from __future__ import annotations


from mqe.config import (
    CORRELATION_GATE_THRESHOLD,
    CORRELATION_HAIRCUT_FACTOR,
    OI_MC_DANGER_PENALTY,
    OI_MC_DANGER_THRESHOLD,
    PAIR_PROFILES,
    POSITION_MAX_PCT,
    POSITION_MIN_PCT,
)


def compute_position_size(
    symbol: str,
    open_pairs: list[str],
    equity: float,
    atr_dict: dict[str, float],
    corr_dict: dict[str, dict[str, float]],
) -> float:
    """
    Compute position size for a symbol.

    Args:
        symbol: Trading pair to size
        open_pairs: Currently open position symbols
        equity: Current portfolio equity
        atr_dict: {symbol: atr_1h_pct} for all active symbols
        corr_dict: Pairwise correlation {sym_a: {sym_b: corr}}

    Returns:
        Position size in absolute value (clipped to min/max pct of equity)
    """
    if symbol not in atr_dict or atr_dict[symbol] <= 0:
        return equity * POSITION_MIN_PCT

    # Step 1: Inverse-vol base weight
    inv_vol = 1.0 / atr_dict[symbol]

    # Step 2: Normalize (if other symbols available)
    total_inv_vol = sum(1.0 / v for v in atr_dict.values() if v > 0)
    if total_inv_vol > 0:
        weight = inv_vol / total_inv_vol
    else:
        weight = 1.0 / max(len(atr_dict), 1)

    # Step 3: Correlation haircut — reduce by 10% per highly correlated open pair
    if symbol in corr_dict:
        for open_sym in open_pairs:
            if open_sym in corr_dict[symbol]:
                if abs(corr_dict[symbol][open_sym]) > CORRELATION_GATE_THRESHOLD:
                    weight *= CORRELATION_HAIRCUT_FACTOR

    # Step 4: OI/MC danger penalty
    profile = PAIR_PROFILES.get(symbol, {})
    oi_mc = profile.get("oi_mc_ratio", 0.0)
    if oi_mc > OI_MC_DANGER_THRESHOLD:
        weight *= OI_MC_DANGER_PENALTY

    # Step 5: Convert to absolute size, clip
    size = equity * weight
    min_size = equity * POSITION_MIN_PCT
    max_size = equity * POSITION_MAX_PCT
    return max(min_size, min(size, max_size))
