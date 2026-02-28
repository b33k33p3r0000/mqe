"""Unit tests for MQE config."""

from mqe.config import (
    SYMBOLS,
    SLIPPAGE_MAP,
    PAIR_PROFILES,
    CLUSTER_DEFINITIONS,
    CLUSTER_MAX_CONCURRENT,
    TIER_SEARCH_SPACE,
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
        assert len(SYMBOLS) == 15
        assert SYMBOLS[0] == "BTC/USDT"
        assert SYMBOLS[-1] == "INJ/USDT"

    def test_all_symbols_have_slippage(self):
        for sym in SYMBOLS:
            assert sym in SLIPPAGE_MAP, f"Missing slippage for {sym}"

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

    def test_cluster_members_are_valid_symbols(self):
        """Every symbol listed in CLUSTER_DEFINITIONS must be in SYMBOLS."""
        for cluster, members in CLUSTER_DEFINITIONS.items():
            for sym in members:
                assert sym in SYMBOLS, (
                    f"{sym} in cluster '{cluster}' but not in SYMBOLS"
                )


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


class TestTierSearchSpace:
    def test_all_profile_tiers_have_search_space(self):
        """Every tier in PAIR_PROFILES has a matching TIER_SEARCH_SPACE entry."""
        tiers = {p["tier"] for p in PAIR_PROFILES.values()}
        for tier in tiers:
            assert tier in TIER_SEARCH_SPACE, f"Missing search space for tier {tier}"

    def test_search_space_has_all_params(self):
        """Each tier has all 12 tunable param ranges."""
        expected_keys = {
            "allow_flip", "macd_fast", "macd_slow", "macd_signal",
            "rsi_period", "rsi_lower", "rsi_upper", "rsi_lookback",
            "adx_threshold", "trail_mult", "hard_stop_mult", "max_hold_bars",
        }
        for tier, space in TIER_SEARCH_SPACE.items():
            assert set(space.keys()) == expected_keys, f"Tier {tier} missing keys"

    def test_ranges_are_valid_tuples(self):
        """Each range is a (low, high) tuple where low <= high."""
        for tier, space in TIER_SEARCH_SPACE.items():
            for key, (lo, hi) in space.items():
                assert lo <= hi, f"Tier {tier} {key}: {lo} > {hi}"

    def test_tier_s_allows_flip(self):
        """Tier S has allow_flip (0,1) = optimizable."""
        assert TIER_SEARCH_SPACE["S"]["allow_flip"] == (0, 1)

    def test_non_s_tiers_fix_flip(self):
        """Non-S tiers have allow_flip (0,0) = fixed off."""
        for tier, space in TIER_SEARCH_SPACE.items():
            if tier != "S":
                assert space["allow_flip"] == (0, 0), f"Tier {tier} allow_flip not fixed"

    def test_lower_tiers_narrower_macd(self):
        """Lower tiers have narrower MACD ranges."""
        s_fast_hi = TIER_SEARCH_SPACE["S"]["macd_fast"][1]
        b_fast_hi = TIER_SEARCH_SPACE["B"]["macd_fast"][1]
        assert b_fast_hi < s_fast_hi

    def test_lower_tiers_shorter_hold(self):
        """Lower tiers have shorter max hold."""
        s_hold_hi = TIER_SEARCH_SPACE["S"]["max_hold_bars"][1]
        b_hold_hi = TIER_SEARCH_SPACE["B"]["max_hold_bars"][1]
        assert b_hold_hi < s_hold_hi
