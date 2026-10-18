import pytest
from services.token_security import evaluate_token_balances
from services.known_entities import lookup_known_entity
from services.risk_engine import calculate_risk_score
from services.graph import _node_truth

REAL_BSC_USDT = "0x55d398326f99059ff775485246999027b3197955"
FAKE_BSC_USDT = "0xdeadbeef11112222333344445555666677778888"
STARGATE_BRIDGE = "0x4a364f8c717ca67422e138d603945111b27a7712"
BINANCE_HOT = "0x8894e0a0c962cb723c1976a4421c95949be2d4e3"


def test_genuine_usdt_evaluated_clean():
    tokens = [
        {
            "token": {
                "symbol": "USDT",
                "name": "Tether USD",
                "address": REAL_BSC_USDT,
                "decimals": "18",
            },
            "value": "1000000000000000000000",  # 1000 USDT
        }
    ]
    res = evaluate_token_balances("BSC", tokens)
    assert res["has_fake_assets"] is False
    assert len(res["verified_tokens"]) == 1
    assert len(res["fake_tokens"]) == 0
    assert res["asset_status"] == "VERIFIED"


def test_fake_usdt_detected_as_critical_scam():
    tokens = [
        {
            "token": {
                "symbol": "USDT",
                "name": "Tether USD",
                "address": FAKE_BSC_USDT,  # Fake clone!
                "decimals": "18",
            },
            "value": "50000000000000000000000",  # 50,000 Fake USDT
        }
    ]
    res = evaluate_token_balances("BSC", tokens)
    assert res["has_fake_assets"] is True
    assert len(res["fake_tokens"]) == 1
    assert res["fake_tokens"][0]["impersonating"] == "USDT"
    assert res["fake_tokens"][0]["risk"] == "CRITICAL"
    assert res["asset_status"] == "COMPROMISED"


def test_risk_engine_penalizes_fake_tokens():
    chain_data = {
        "fake_tokens": [
            {
                "symbol": "USDT",
                "impersonating": "USDT",
                "contract": FAKE_BSC_USDT,
                "balance": 50000.0,
            }
        ],
        "tx_list": [],
    }
    score, factors, level, meta = calculate_risk_score({}, chain_data, "0x1234567890123456789012345678901234567890")
    assert score >= 95
    assert level == "CRITICAL"
    assert meta["has_fake_assets"] is True
    assert any("Fake Asset Detected" in f["desc"] for f in factors)


def test_known_entities_identification():
    # Stargate Bridge
    bridge = lookup_known_entity(STARGATE_BRIDGE)
    assert bridge is not None
    assert bridge["category"] == "bridge"
    assert bridge["is_bridge"] is True

    # Binance Hot Wallet
    cex = lookup_known_entity(BINANCE_HOT)
    assert cex is not None
    assert cex["category"] == "cex"
    assert "Binance" in cex["name"]


def test_attribution_coverage_and_bridge_alert():
    user_wallet = "0xaaaa111122223333444455556666777788889999"
    # User received 100 BNB from Stargate Bridge and 100 BNB from unknown address
    chain_data = {
        "fake_tokens": [],
        "tx_list": [
            {
                "from": STARGATE_BRIDGE,
                "to": user_wallet,
                "value": "100.0",
                "timestamp": 1700000000,
            },
            {
                "from": "0xbbbb222233334444555566667777888899990000",
                "to": user_wallet,
                "value": "100.0",
                "timestamp": 1700000000,
            },
        ],
    }
    score, factors, level, meta = calculate_risk_score({}, chain_data, user_wallet)
    # Total volume = 200, attributed = 100 (from bridge) -> 50.0% coverage
    assert meta["attribution_coverage_pct"] == 50.0
    assert meta["attributed_volume"] == 100.0
    assert meta["unattributed_volume"] == 100.0
    assert "Stargate Finance Router" in meta["bridges_detected"]
    # Check bridge alert factor
    assert any("Cross-Chain Bridge" in f["desc"] for f in factors)


def test_graph_node_truth_includes_bridge_and_cex():
    truth_bridge = _node_truth(STARGATE_BRIDGE, {})
    assert truth_bridge["is_bridge"] is True
    assert "Stargate" in truth_bridge["entity"]

    truth_cex = _node_truth(BINANCE_HOT, {})
    assert truth_cex["is_cex"] is True
    assert "Binance" in truth_cex["entity"]
