"""
MQE Discord Notifications
===========================
Simple Discord webhook notifications for pipeline events.
Adapted from QRE notify.py.

Channels:
  #qre-runs  -- pipeline start, complete, analysis results
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from mqe.config import DISCORD_WEBHOOK_RUNS

logger = logging.getLogger("mqe.notify")


def discord_notify(msg: str, webhook_url: str, timeout: int = 8) -> bool:
    """Send message to Discord webhook.

    Args:
        msg: Message content (plain text or code block).
        webhook_url: Discord webhook URL.
        timeout: Request timeout in seconds.

    Returns:
        True on success, False on failure or empty webhook URL.
    """
    if not webhook_url:
        logger.debug("discord_notify: no webhook URL, skipping")
        return False
    try:
        response = requests.post(
            webhook_url,
            json={"content": msg},
            timeout=timeout,
        )
        ok = response.status_code < 300
        if not ok:
            logger.warning(
                "Discord notify failed: status=%d", response.status_code
            )
        return ok
    except Exception as e:
        logger.warning("Discord notify failed: %s", e)
        return False


def format_start_message(
    symbols: list,
    n_trials_s1: int,
    n_trials_s2: int,
    n_splits: int,
    run_tag: Optional[str] = None,
) -> str:
    """Format pipeline start notification.

    Args:
        symbols: List of symbols being optimized.
        n_trials_s1: Number of Stage 1 trials per pair.
        n_trials_s2: Number of Stage 2 trials.
        n_splits: Number of AWF splits.
        run_tag: Optional run tag.

    Returns:
        Formatted Discord message string.
    """
    tag_line = f"Tag:      {run_tag}\n" if run_tag else ""
    symbols_str = ", ".join(symbols)
    return (
        f"```\n"
        f"MQE OPTIMIZATION STARTED\n"
        f"{'=' * 30}\n"
        f"Pairs:    {symbols_str}\n"
        f"{tag_line}"
        f"Mode:     Multi-pair AWF\n"
        f"Stage 1:  {n_trials_s1:,} trials/pair\n"
        f"Stage 2:  {n_trials_s2:,} trials\n"
        f"Splits:   {n_splits}\n"
        f"```"
    )


def format_complete_message(analysis: Dict[str, Any]) -> str:
    """Format pipeline completion notification.

    Args:
        analysis: Full analysis dict from analyze_run().

    Returns:
        Formatted Discord message string.
    """
    per_pair = analysis.get("per_pair", [])
    portfolio = analysis.get("portfolio", {})
    portfolio_verdict = portfolio.get("verdict", "?")
    portfolio_calmar = portfolio.get("portfolio_calmar", 0)

    lines = []
    lines.append("```")
    lines.append("MQE OPTIMIZATION COMPLETED")
    lines.append("=" * 30)

    for pair in per_pair:
        symbol = pair.get("symbol", "?")
        verdict = pair.get("verdict", "?")
        summary = pair.get("metrics_summary", {})
        sharpe = summary.get("sharpe", 0)
        trades = summary.get("trades_per_year", 0)
        tag = "[ok]" if verdict == "PASS" else "[!!]" if verdict == "WARN" else "[XX]"
        lines.append(f"  {tag} {symbol:<12} S={sharpe:.2f} T={trades:.0f}/yr")

    lines.append("-" * 30)
    lines.append(f"PORTFOLIO:  {portfolio_verdict}  Calmar={portfolio_calmar:.2f}")
    lines.append("```")

    return "\n".join(lines)


def notify_start(**kwargs: Any) -> bool:
    """Send start notification to Discord."""
    msg = format_start_message(**kwargs)
    return discord_notify(msg, DISCORD_WEBHOOK_RUNS)


def notify_complete(analysis: Dict[str, Any]) -> bool:
    """Send completion notification to Discord."""
    msg = format_complete_message(analysis)
    return discord_notify(msg, DISCORD_WEBHOOK_RUNS)
