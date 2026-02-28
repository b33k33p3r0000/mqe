"""
Data Fetching
=============
Multi-pair OHLCV data fetching from exchange API via ccxt.
Always fresh data, no disk cache.

Key difference from QRE: load_multi_pair_data() fetches all pairs at once
and always includes BTC/USDT (needed for regime filter).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import pandas as pd

from mqe.config import (
    BASE_TF,
    MAX_API_RETRIES,
    OHLCV_LIMIT_PER_CALL,
    SAFETY_MAX_ROWS,
    TF_MS,
    TREND_TFS,
)

logger = logging.getLogger("mqe.data")

BTC_SYMBOL = "BTC/USDT"


def utcnow_ms() -> int:
    """Return current UTC time as millisecond timestamp."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def fetch_ohlcv_paginated(
    exchange, symbol: str, tf: str, since_ms: int, until_ms: int,
) -> pd.DataFrame:
    """
    Fetch OHLCV data from exchange in paginated batches.

    Args:
        exchange: ccxt exchange instance
        symbol: Trading pair (e.g. "BTC/USDT")
        tf: Timeframe string (e.g. "1h", "4h")
        since_ms: Start timestamp in milliseconds
        until_ms: End timestamp in milliseconds

    Returns:
        DataFrame with OHLCV columns, DatetimeIndex (UTC)
    """
    all_rows: list[list] = []
    tf_ms = TF_MS[tf]
    cursor = since_ms
    retry_count = 0

    logger.info(
        "Fetching %s %s from %s",
        symbol, tf,
        datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc),
    )

    while True:
        try:
            batch = exchange.fetch_ohlcv(
                symbol, timeframe=tf, since=cursor, limit=OHLCV_LIMIT_PER_CALL,
            )
            retry_count = 0

        except Exception as e:
            retry_count += 1
            logger.warning(
                "Fetch error %s %s (attempt %d/%d): %s",
                symbol, tf, retry_count, MAX_API_RETRIES, e,
            )

            if retry_count >= MAX_API_RETRIES:
                logger.error("Max retries reached for %s %s", symbol, tf)
                break

            time.sleep(exchange.rateLimit / 1000.0 + 1.0)
            continue

        if not batch:
            break

        all_rows.extend(batch)
        last_ts = batch[-1][0]

        if last_ts >= until_ms - tf_ms:
            break

        next_cursor = last_ts + tf_ms
        if next_cursor <= cursor:
            next_cursor = cursor + tf_ms
        cursor = next_cursor

        time.sleep(exchange.rateLimit / 1000.0)

        if len(all_rows) > SAFETY_MAX_ROWS:
            logger.warning("Safety limit reached for %s %s", symbol, tf)
            break

    if not all_rows:
        return pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )

    df = pd.DataFrame(
        all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)

    logger.info("Fetched %d rows for %s %s", len(df), symbol, tf)

    return df


def load_all_data(
    exchange, symbol: str, hours_1h: int,
) -> dict[str, pd.DataFrame]:
    """
    Fetch fresh data for one symbol: base TF + all trend TFs.

    Args:
        exchange: ccxt exchange instance
        symbol: Trading pair
        hours_1h: How many hours of 1h data to fetch

    Returns:
        Dict {timeframe: DataFrame} with keys "1h", "4h", "8h", "1d"
    """
    now_ms = utcnow_ms()
    since_1h = now_ms - hours_1h * TF_MS["1h"]

    data: dict[str, pd.DataFrame] = {}

    # Base timeframe
    data[BASE_TF] = fetch_ohlcv_paginated(exchange, symbol, BASE_TF, since_1h, now_ms)

    # Higher timeframes for trend filter
    for tf in TREND_TFS:
        data[tf] = fetch_ohlcv_paginated(exchange, symbol, tf, since_1h, now_ms)

    return data


def load_multi_pair_data(
    exchange, symbols: list[str], hours: int,
) -> Dict[str, dict[str, pd.DataFrame]]:
    """
    Fetch OHLCV data for multiple pairs. Always includes BTC/USDT
    (needed for regime filter even if not in symbol list).

    Args:
        exchange: ccxt exchange instance
        symbols: List of trading pairs (e.g. ["ETH/USDT", "SOL/USDT"])
        hours: How many hours of 1h data to fetch

    Returns:
        Dict {symbol: {timeframe: DataFrame}}
        BTC/USDT is always present in the result.
    """
    # Ensure BTC is in the fetch list (needed for regime filter)
    fetch_symbols = list(symbols)
    if BTC_SYMBOL not in fetch_symbols:
        fetch_symbols.append(BTC_SYMBOL)

    result: Dict[str, dict[str, pd.DataFrame]] = {}

    for sym in fetch_symbols:
        logger.info("Loading data for %s (%d hours)", sym, hours)
        result[sym] = load_all_data(exchange, sym, hours)

    return result
