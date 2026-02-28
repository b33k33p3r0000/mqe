"""Unit tests for MQE I/O utilities."""

import json
from pathlib import Path

import pytest

from mqe.io import save_json, load_json, save_trades_csv


class TestSaveJson:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "sub" / "test.json"
        save_json(path, {"key": "value"})
        assert path.exists()

    def test_round_trip(self, tmp_path):
        path = tmp_path / "test.json"
        data = {"foo": 1, "bar": [1, 2, 3]}
        save_json(path, data)
        loaded = load_json(path)
        assert loaded == data


class TestSaveTradesCsv:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "trades.csv"
        trades = [{"entry_ts": "2025-01-01", "pnl_abs": 100.0, "symbol": "BTC/USDT"}]
        save_trades_csv(path, trades)
        assert path.exists()

    def test_empty_trades(self, tmp_path):
        path = tmp_path / "trades.csv"
        save_trades_csv(path, [])
        assert path.exists()
