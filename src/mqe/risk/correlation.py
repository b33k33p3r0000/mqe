"""Rolling Correlation & Cluster logic for MQE portfolio risk management."""

from __future__ import annotations

import pandas as pd

from mqe.config import CORRELATION_GATE_THRESHOLD


def compute_rolling_correlation_matrix(
    returns_dict: dict[str, pd.Series],
    window: int = 720,  # 30 days × 24 hours
) -> pd.DataFrame:
    """
    Compute rolling correlation matrix from return series.

    Args:
        returns_dict: {symbol: pd.Series of hourly log returns}
        window: Rolling window in bars (default 720 = 30 days of 1H bars)

    Returns:
        pd.DataFrame correlation matrix (latest rolling window)
    """
    df = pd.DataFrame(returns_dict)
    # Use the last `window` bars for a simple correlation matrix.
    # min_periods allows partial windows when data is shorter.
    min_periods = window // 2
    tail = df.iloc[-window:]
    if len(tail) < min_periods:
        # Not enough data — return NaN matrix
        return pd.DataFrame(
            index=df.columns, columns=df.columns, dtype=float
        )
    return tail.corr()


def compute_pairwise_correlation(
    returns_dict: dict[str, pd.Series],
    window: int = 720,
) -> dict[str, dict[str, float]]:
    """
    Compute pairwise correlation dict from return series.

    Returns:
        Nested dict: {symbol_a: {symbol_b: corr_value}}
    """
    df = pd.DataFrame(returns_dict)
    corr = df.iloc[-window:].corr()
    result: dict[str, dict[str, float]] = {}
    for sym_a in corr.columns:
        result[sym_a] = {}
        for sym_b in corr.columns:
            if sym_a != sym_b:
                result[sym_a][sym_b] = float(corr.loc[sym_a, sym_b])
    return result


def get_correlated_pairs(
    symbol: str,
    open_pairs: list[str],
    corr_dict: dict[str, dict[str, float]],
    threshold: float = CORRELATION_GATE_THRESHOLD,
) -> int:
    """
    Count how many open pairs are highly correlated with the given symbol.

    Args:
        symbol: The symbol we want to open
        open_pairs: Currently open position symbols
        corr_dict: Pairwise correlation from compute_pairwise_correlation
        threshold: Correlation threshold (default 0.75)

    Returns:
        Count of open pairs with correlation > threshold
    """
    if symbol not in corr_dict:
        return 0
    count = 0
    for open_sym in open_pairs:
        if open_sym in corr_dict[symbol]:
            if abs(corr_dict[symbol][open_sym]) > threshold:
                count += 1
    return count
