"""Unit tests for MQE config."""

from mqe.config import (
    SYMBOLS,
    PAIR_PROFILES,
    CLUSTER_DEFINITIONS,
    CLUSTER_MAX_CONCURRENT,
    BASE_TF,
    TREND_TFS,
    FEE,
    OI_MC_DANGER_THRESHOLD,
    OI_MC_DANGER_PENALTY,
    get_slippage,
    get_cluster,
)


class TestSymbols:
    def test_default_symbols(self):
        assert "BTC/USDT" in SYMBOLS
        assert "ETH/USDT" in SYMBOLS
        assert "SOL/USDT" in SYMBOLS

    def test_all_symbols_have_profiles(self):
        for sym in SYMBOLS:
            assert sym in PAIR_PROFILES, f"Missing profile for {sym}"


class TestPairProfiles:
    def test_required_keys(self):
        required = {"tier", "cluster", "btc_corr", "ann_vol", "atr_1h_pct",
                     "slippage_bps", "oi_mc_ratio", "volume_24h_min"}
        for sym, profile in PAIR_PROFILES.items():
            for key in required:
                assert key in profile, f"Missing {key} in {sym} profile"

    def test_btc_corr_is_one(self):
        assert PAIR_PROFILES["BTC/USDT"]["btc_corr"] == 1.0

    def test_sol_in_danger_zone(self):
        assert PAIR_PROFILES["SOL/USDT"]["oi_mc_ratio"] > OI_MC_DANGER_THRESHOLD


class TestClusterDefinitions:
    def test_all_symbols_have_cluster(self):
        for sym in SYMBOLS:
            cluster = get_cluster(sym)
            assert cluster in CLUSTER_DEFINITIONS, f"Unknown cluster {cluster} for {sym}"

    def test_cluster_max_concurrent(self):
        for cluster in CLUSTER_DEFINITIONS:
            assert cluster in CLUSTER_MAX_CONCURRENT


class TestHelperFunctions:
    def test_get_slippage(self):
        assert get_slippage("BTC/USDT") > 0
        assert get_slippage("UNKNOWN/USDT") > 0  # falls back to default

    def test_fee_positive(self):
        assert FEE > 0

    def test_base_tf(self):
        assert BASE_TF == "1h"

    def test_trend_tfs(self):
        assert "4h" in TREND_TFS
