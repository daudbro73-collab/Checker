"""Golden regression tests for risk engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.risk_engine import calculate_risk_score


def test_direct_sanction_is_critical():
    score, factors, level, meta = calculate_risk_score(
        {"is_sanctioned": True, "source": "OFAC", "category": "Sanctions", "reason": "SDN"},
        {"tx_list": [], "tx_count": 0, "balance": 0},
        address="0xabc",
    )
    assert score >= 95
    assert level == "CRITICAL"
    assert factors[0]["signal_type"] == "sanctions"


def test_tether_style_hit_critical():
    score, factors, level, meta = calculate_risk_score(
        {"is_sanctioned": True, "source": "Tether", "category": "Frozen", "reason": "blacklist"},
        {},
        address="Txxx",
    )
    assert score == 95
    assert level == "CRITICAL"


def test_clean_new_wallet_stays_safe_or_caution():
    score, factors, level, meta = calculate_risk_score(
        {"is_sanctioned": False},
        {"tx_count": 0, "balance": 0, "tx_list": []},
        address="0xclean",
    )
    assert level in ("SAFE", "CAUTION")
    assert score < 40
    assert meta.get("behavioural_cap_applied") is True


def test_behavioural_only_capped_at_caution():
    # High velocity + thin history + high volume patterns without external signals
    now = __import__("time").time()
    txs = [
        {"from": "0xa", "to": "0xclean", "value": "1000", "timestamp": now - i}
        for i in range(15)
    ]
    score, factors, level, meta = calculate_risk_score(
        {"is_sanctioned": False},
        {"tx_count": 3, "balance": 500, "tx_list": txs},
        address="0xclean",
    )
    assert level == "CAUTION" or level == "SAFE"
    assert level != "WARNING"
    assert level != "CRITICAL"
    assert score < 40


def test_dust_filtered_from_exposure():
    now = __import__("time").time()
    address = "0xvictim"
    txs = [
        {"from": "0xbad", "to": address, "value": "1", "timestamp": now - 100},  # dust
        {"from": "0xok", "to": address, "value": "5000", "timestamp": now - 200},
    ]
    chain = {
        "tx_count": 2,
        "balance": 100,
        "tx_list": txs,
        "counterparty_sanctions": {
            "direct_hits": 1,
            "distinct_sanctioned": 1,
            "categories": ["Sanctions"],
            "exposure_events": [
                {"address": "0xbad", "value": 1, "timestamp": now - 100, "direction": "in", "category": "Sanctions", "source": "OFAC"},
            ],
        },
    }
    score, factors, level, meta = calculate_risk_score(
        {"is_sanctioned": False}, chain, address=address
    )
    assert meta["dust_filtered"] >= 1
    assert meta["exposure_pct_in_90d"] == 0.0


def test_exposure_raises_with_meaningful_volume():
    now = __import__("time").time()
    address = "0xvictim"
    txs = [
        {"from": "0xbad", "to": address, "value": "400", "timestamp": now - 100},
        {"from": "0xok", "to": address, "value": "600", "timestamp": now - 200},
    ]
    chain = {
        "tx_count": 2,
        "balance": 100,
        "tx_list": txs,
        "counterparty_sanctions": {
            "direct_hits": 1,
            "distinct_sanctioned": 1,
            "categories": ["Sanctions"],
            "exposure_events": [
                {"address": "0xbad", "value": 400, "timestamp": now - 100, "direction": "in", "category": "Sanctions", "source": "OFAC"},
            ],
        },
    }
    score, factors, level, meta = calculate_risk_score(
        {"is_sanctioned": False}, chain, address=address
    )
    assert meta["exposure_pct_in_90d"] > 30
    assert meta["has_external_signal"] is True
    assert score >= 25


def test_address_validation():
    from services.address_validation import validate_address
    assert validate_address("ETH", "0x53b6936513e738f44fb50d2b9476730c0ab3bfc1")[0]
    assert not validate_address("ETH", "not-an-address")[0]
    assert validate_address("TRON", "TJ8c14Nj9j7xAB4dbGeiX9h8unkKHxuWwb")[0]
    assert validate_address("BTC", "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")[0]
    assert not validate_address("AVAX", "0x53b6936513e738f44fb50d2b9476730c0ab3bfc1")[0]
