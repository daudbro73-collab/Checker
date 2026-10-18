import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings
from services.address_validation import validate_address, detect_input_kind, detect_chain
from services.ton_address import parse_and_validate_ton_address, crc16_ton
from services.ton_service import detect_address_poisoning, _SPAM_KEYWORDS, USDT_TON_MASTER_BOUNCEABLE, USDT_TON_MASTER_RAW
from services.risk_engine import calculate_risk_score

settings = get_settings()

VALID_BOUNCEABLE = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
VALID_RAW = "0:b113a994b5024a16719f69139328eb759596c38a25f59028b146fecdc3621dfe"
VALID_FOUNDATION = "EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N"


def test_ton_in_allowed_chains():
    assert "TON" in settings.ALLOWED_CHAINS


def test_ton_crc16():
    data = b"\x11\x00" + bytes(32)
    crc = crc16_ton(data)
    assert isinstance(crc, int)
    assert 0 <= crc <= 0xffff


def test_ton_address_validation_bounceable():
    ok, err, parsed = parse_and_validate_ton_address(VALID_BOUNCEABLE)
    assert ok is True
    assert err is None
    assert parsed is not None
    assert parsed["bounceable"] == VALID_BOUNCEABLE
    assert parsed["raw"] == VALID_RAW
    assert parsed["workchain"] == 0

    val_ok, val_addr = validate_address("TON", VALID_BOUNCEABLE)
    assert val_ok is True
    assert val_addr == VALID_BOUNCEABLE


def test_ton_address_validation_raw():
    ok, err, parsed = parse_and_validate_ton_address(VALID_RAW)
    assert ok is True
    assert err is None
    assert parsed["bounceable"] == VALID_BOUNCEABLE
    assert parsed["raw"] == VALID_RAW

    val_ok, val_addr = validate_address("TON", VALID_RAW)
    assert val_ok is True
    # validate_address canonicalizes to bounceable format
    assert val_addr == VALID_BOUNCEABLE


def test_ton_address_invalid_cases():
    # Invalid length
    ok, err, _ = parse_and_validate_ton_address("EQTooShort")
    assert ok is False
    assert "Invalid TON address" in err

    # Corrupted checksum: flip last character
    corrupted = VALID_BOUNCEABLE[:-1] + ("A" if VALID_BOUNCEABLE[-1] != "A" else "B")
    ok, err, _ = parse_and_validate_ton_address(corrupted)
    assert ok is False
    assert "Invalid TON address CRC16 checksum" in err

    val_ok, msg = validate_address("TON", corrupted)
    assert val_ok is False
    assert "CRC16" in msg


def test_ton_url_detection():
    url1 = f"https://tonviewer.com/{VALID_BOUNCEABLE}"
    d1 = detect_input_kind(url1)
    assert d1["kind"] == "address"
    assert d1["chain"] == "TON"
    assert d1["value"] == VALID_BOUNCEABLE

    url2 = f"https://tonscan.org/address/{VALID_BOUNCEABLE}"
    d2 = detect_input_kind(url2)
    assert d2["kind"] == "address"
    assert d2["chain"] == "TON"
    assert d2["value"] == VALID_BOUNCEABLE

    url3 = f"https://tonapi.io/account/{VALID_RAW}"
    d3 = detect_input_kind(url3)
    assert d3["kind"] == "address"
    assert d3["chain"] == "TON"
    assert d3["value"] == VALID_RAW


def test_detect_chain_ton():
    assert detect_chain(VALID_BOUNCEABLE) == "TON"
    assert detect_chain(VALID_FOUNDATION) == "TON"
    assert detect_chain(VALID_RAW) == "TON"


def test_detect_address_poisoning():
    legit_contact = "EQA111111111111111111111111111111111111111119999"
    poison_sender = "EQA1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx9999"
    other_sender  = "EQB2yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy8888"

    incoming_txs = [
        # Poisoning dust tx (< 0.05 TON)
        {"from": poison_sender, "value": "0.001 TON", "hash": "tx_poison"},
        # Normal transfer from unrelated sender
        {"from": other_sender, "value": "10.5 TON", "hash": "tx_normal"},
        # Normal transfer from poison sender (high value -> not dust attack)
        {"from": poison_sender, "value": "20.0 TON", "hash": "tx_high_val"},
    ]

    alerts = detect_address_poisoning(
        target_addr="EQTargetWallet1111111111111111111111111111111111",
        incoming_txs=incoming_txs,
        all_counterparties=[legit_contact, other_sender],
    )

    assert len(alerts) == 1
    assert alerts[0]["fake_sender"] == poison_sender
    assert alerts[0]["target_contact"] == legit_contact
    assert alerts[0]["tx_hash"] == "tx_poison"


def test_memo_spam_keywords():
    spam_memo1 = "Claim your free 50 TON airdrop at t.me/claim_gift_bot"
    spam_memo2 = "Exclusive presale whitelist reward bonus"
    clean_memo = "Payment for design consultation #108"

    assert bool(_SPAM_KEYWORDS.search(spam_memo1)) is True
    assert bool(_SPAM_KEYWORDS.search(spam_memo2)) is True
    assert bool(_SPAM_KEYWORDS.search(clean_memo)) is False


def test_ton_risk_engine_factors():
    # 1. TON Network Scam Label
    score_scam, factors_scam, level_scam, meta_scam = calculate_risk_score(
        sanctions_data={"is_sanctioned": False},
        chain_data={"is_scam": True, "tx_count": 5, "balance": 10},
        address=VALID_BOUNCEABLE,
    )
    assert score_scam >= 95
    assert level_scam == "CRITICAL"
    assert any("TON Network Scam Label" in f["desc"] for f in factors_scam)

    # 2. Address Poisoning Attack detected
    score_p, factors_p, level_p, meta_p = calculate_risk_score(
        sanctions_data={"is_sanctioned": False},
        chain_data={
            "address_poisoning_attacks": [{
                "fake_sender": "EQA1...9999",
                "target_contact": "EQA1...9999",
                "dust_amount": 0.001,
            }],
            "tx_count": 10,
            "balance": 50,
            "tx_list": [],
        },
        address=VALID_BOUNCEABLE,
    )
    assert any("Address Poisoning Attack" in f["desc"] for f in factors_p)
    assert meta_p.get("poisoning_attacks_count") == 1
