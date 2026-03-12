"""
GARCH(1,1) Conditional Volatility
==================================
MLE-fitted GARCH for forward-looking volatility estimates.

σ²_t = ω + α·r²_{t-1} + β·σ²_{t-1}

Rolling window MLE fitting via `arch` package.
Returns vol_ratio (long_term / conditional) for sizing, plus raw arrays.
"""
from __future__ import annotations

import logging
from typing import Tuple

import numpy as np
import pandas as pd

from mqe.config import (
    GARCH_REFIT_INTERVAL,
    GARCH_VOL_RATIO_MAX,
    GARCH_VOL_RATIO_MIN,
    GARCH_WINDOW,
)

logger = logging.getLogger("mqe.garch")


def garch_conditional_vol(
    close: pd.Series,
    window: int = GARCH_WINDOW,
    refit_interval: int = GARCH_REFIT_INTERVAL,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute GARCH(1,1) conditional volatility with rolling MLE fitting.

    Args:
        close: 1H close price series.
        window: Rolling MLE fit window in bars (default 720 = 30 days).
        refit_interval: Re-fit every N bars (default 168 = 1 week).

    Returns:
        vol_ratio: long_term_vol / conditional_vol, clipped. >1 = calm, <1 = spike.
        conditional_vol: Raw σ_t array (annualized).
        long_term_vol: Unconditional vol array (annualized).
    """
    n = len(close)
    vol_ratio = np.ones(n, dtype=np.float64)
    conditional_vol = np.zeros(n, dtype=np.float64)
    long_term_vol = np.zeros(n, dtype=np.float64)

    if n < window:
        logger.warning("Data shorter than GARCH window (%d < %d), returning neutral", n, window)
        return vol_ratio, conditional_vol, long_term_vol

    # Log returns (1H)
    log_returns = np.log(close / close.shift(1)).dropna().values
    # log_returns[i] corresponds to close index i+1

    from arch import arch_model

    # Current fit params
    omega, alpha, beta = 0.0, 0.0, 0.0
    lt_var = 0.0
    last_fit_bar = -refit_interval  # force fit on first eligible bar

    for bar in range(window, n):
        lr_idx = bar - 1  # log_returns index (offset by 1)

        # Re-fit GARCH if interval reached
        if bar - last_fit_bar >= refit_interval:
            fit_start = max(0, lr_idx - window + 1)
            fit_end = lr_idx + 1
            fit_data = log_returns[fit_start:fit_end] * 100  # arch expects pct

            if len(fit_data) < 100:
                continue

            try:
                model = arch_model(fit_data, vol="Garch", p=1, q=1, mean="Zero", rescale=False)
                result = model.fit(disp="off", show_warning=False)
                omega = result.params.get("omega", 0.0)
                alpha = result.params.get("alpha[1]", 0.0)
                beta = result.params.get("beta[1]", 0.0)
                persistence = alpha + beta
                if 0 < persistence < 1 and omega > 0:
                    lt_var = omega / (1.0 - persistence)
                else:
                    lt_var = np.var(fit_data)
                last_fit_bar = bar
            except Exception:
                logger.debug("GARCH fit failed at bar %d, keeping previous params", bar)

        # Compute conditional variance using GARCH recursion
        if omega > 0 and bar > window:
            prev_return_pct = log_returns[lr_idx] * 100
            prev_cond_var = conditional_vol[bar - 1] ** 2 if conditional_vol[bar - 1] > 0 else lt_var
            cond_var = omega + alpha * prev_return_pct ** 2 + beta * prev_cond_var
        elif lt_var > 0:
            cond_var = lt_var
        else:
            continue

        cond_std = np.sqrt(max(cond_var, 1e-10))
        lt_std = np.sqrt(max(lt_var, 1e-10))

        conditional_vol[bar] = cond_std
        long_term_vol[bar] = lt_std

        if cond_std > 0:
            ratio = lt_std / cond_std
            vol_ratio[bar] = np.clip(ratio, GARCH_VOL_RATIO_MIN, GARCH_VOL_RATIO_MAX)

    return vol_ratio, conditional_vol, long_term_vol
