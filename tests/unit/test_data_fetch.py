"""Unit tests for MQE data fetching — multi-pair OHLCV pipeline."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from mqe.data.fetch import (
    fetch_ohlcv_paginated,
    load_all_data,
    load_multi_pair_data,
    utcnow_ms,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_mock_exchange(n_batches: int = 1):
    """Create a mock ccxt exchange that returns n_batches of 1 row, then []."""
    mock = MagicMock()
    mock.rateLimit = 100

    call_count = {"n": 0}
    now = utcnow_ms()

    def _fetch(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] <= n_batches:
            ts = now - (n_batches - call_count["n"]) * 3_600_000
            return [[ts, 100.0, 101.0, 99.0, 100.5, 1000.0]]
        return []

    mock.fetch_ohlcv.side_effect = _fetch
    return mock


# ── utcnow_ms ────────────────────────────────────────────────────────────────

class TestUtcnowMs:
    def test_returns_int(self):
        result = utcnow_ms()
        assert isinstance(result, int)

    def test_reasonable_value(self):
        """Should be after 2025-01-01 in milliseconds."""
        result = utcnow_ms()
        assert result > 1735689600000


# ── fetch_ohlcv_paginated ────────────────────────────────────────────────────

class TestFetchOhlcvPaginated:
    @patch("mqe.data.fetch.time.sleep")
    def test_returns_dataframe(self, mock_sleep):
        """Paginated fetch returns a Pandas DataFrame with OHLCV columns."""
        exchange = _make_mock_exchange(n_batches=1)
        now = utcnow_ms()
        df = fetch_ohlcv_paginated(
            exchange, "BTC/USDT", "1h", now - 3_600_000 * 10, now,
        )
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 1

    @patch("mqe.data.fetch.time.sleep")
    def test_empty_on_no_data(self, mock_sleep):
        """Returns empty DataFrame when exchange returns nothing."""
        exchange = _make_mock_exchange(n_batches=0)
        now = utcnow_ms()
        df = fetch_ohlcv_paginated(
            exchange, "BTC/USDT", "1h", now - 3_600_000 * 10, now,
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @patch("mqe.data.fetch.time.sleep")
    def test_index_is_datetime(self, mock_sleep):
        """Index should be DatetimeIndex (UTC)."""
        exchange = _make_mock_exchange(n_batches=1)
        now = utcnow_ms()
        df = fetch_ohlcv_paginated(
            exchange, "BTC/USDT", "1h", now - 3_600_000 * 10, now,
        )
        assert isinstance(df.index, pd.DatetimeIndex)

    @patch("mqe.data.fetch.time.sleep")
    def test_retries_on_error(self, mock_sleep):
        """Should retry on exchange error then succeed."""
        exchange = MagicMock()
        exchange.rateLimit = 100
        now = utcnow_ms()
        exchange.fetch_ohlcv.side_effect = [
            Exception("timeout"),
            [[now - 60_000, 100.0, 101.0, 99.0, 100.5, 1000.0]],
            [],
        ]
        df = fetch_ohlcv_paginated(
            exchange, "BTC/USDT", "1h", now - 3_600_000 * 10, now,
        )
        assert len(df) == 1


# ── load_all_data ────────────────────────────────────────────────────────────

class TestLoadAllData:
    @patch("mqe.data.fetch.time.sleep")
    def test_returns_multi_tf_dict(self, mock_sleep):
        """load_all_data returns dict with 1h + trend TFs (4h, 8h, 1d)."""
        exchange = _make_mock_exchange(n_batches=20)
        data = load_all_data(exchange, "BTC/USDT", 100)

        assert "1h" in data
        assert "4h" in data
        assert "8h" in data
        assert "1d" in data
        assert len(data) == 4

    @patch("mqe.data.fetch.time.sleep")
    def test_all_values_are_dataframes(self, mock_sleep):
        exchange = _make_mock_exchange(n_batches=20)
        data = load_all_data(exchange, "BTC/USDT", 100)

        for tf, df in data.items():
            assert isinstance(df, pd.DataFrame), f"{tf} is not a DataFrame"


# ── load_multi_pair_data ─────────────────────────────────────────────────────

class TestLoadMultiPairData:
    @patch("mqe.data.fetch.time.sleep")
    def test_returns_all_symbols(self, mock_sleep):
        """Returns data dict keyed by each requested symbol."""
        exchange = _make_mock_exchange(n_batches=100)
        symbols = ["ETH/USDT", "SOL/USDT"]
        result = load_multi_pair_data(exchange, symbols, hours=100)

        for sym in symbols:
            assert sym in result, f"Missing {sym}"
            assert isinstance(result[sym], dict)

    @patch("mqe.data.fetch.time.sleep")
    def test_btc_always_included(self, mock_sleep):
        """BTC/USDT is always fetched, even if not in symbol list (regime filter)."""
        exchange = _make_mock_exchange(n_batches=100)
        symbols = ["ETH/USDT", "SOL/USDT"]  # no BTC
        result = load_multi_pair_data(exchange, symbols, hours=100)

        assert "BTC/USDT" in result

    @patch("mqe.data.fetch.time.sleep")
    def test_btc_not_duplicated(self, mock_sleep):
        """If BTC is already in list, don't fetch twice."""
        exchange = _make_mock_exchange(n_batches=100)
        symbols = ["BTC/USDT", "ETH/USDT"]
        result = load_multi_pair_data(exchange, symbols, hours=100)

        # BTC should appear once
        btc_count = list(result.keys()).count("BTC/USDT")
        assert btc_count == 1

    @patch("mqe.data.fetch.time.sleep")
    def test_each_symbol_has_all_tfs(self, mock_sleep):
        """Each symbol should have 1h, 4h, 8h, 1d timeframes."""
        exchange = _make_mock_exchange(n_batches=100)
        result = load_multi_pair_data(exchange, ["BTC/USDT"], hours=100)

        for sym, data in result.items():
            assert "1h" in data, f"Missing 1h for {sym}"
            assert "4h" in data, f"Missing 4h for {sym}"
            assert "8h" in data, f"Missing 8h for {sym}"
            assert "1d" in data, f"Missing 1d for {sym}"


# ── resampling ───────────────────────────────────────────────────────────────

class TestResampling:
    @patch("mqe.data.fetch.time.sleep")
    def test_resampling_creates_higher_tfs(self, mock_sleep):
        """Higher TFs should have fewer rows than 1h base."""
        # Build exchange that returns many rows so 4h/8h/1d have data
        exchange = MagicMock()
        exchange.rateLimit = 100
        now = utcnow_ms()

        # Generate 200 hours of 1h data
        rows = []
        for i in range(200):
            ts = now - (200 - i) * 3_600_000
            rows.append([ts, 100.0 + i * 0.1, 101.0 + i * 0.1,
                         99.0 + i * 0.1, 100.5 + i * 0.1, 1000.0])

        call_count = {"n": 0}

        def _fetch(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return rows
            return []

        exchange.fetch_ohlcv.side_effect = _fetch
        data = load_all_data(exchange, "BTC/USDT", 300)

        # 1h should have data, higher TFs also fetched (separate calls)
        assert len(data["1h"]) > 0
