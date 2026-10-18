import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings
from services.address_validation import validate_address, detect_input_kind, detect_chain
from services.solana_address import validate_solana_address, b58decode, b58encode
from services.solana_service import SolanaService, _SPAM_KEYWORDS, USDT_SOL_MINT, USDC_SOL_MINT
from services.risk_engine import calculate_risk_score

settings = get_settings()

VALID_SOL_1 = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"  # Jupiter
VALID_SOL_2 = "5tzFkiKscMRHK5ZXrebCSqnScYFrK4H56QWqmt3kW1ZQ"  # Binance hot wallet
VALID_USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


def test_solana_in_allowed_chains():
    assert "SOL" in settings.ALLOWED_CHAINS


def test_base58_encoding_decoding():
    raw = bytes([0, 1, 2, 3, 255, 254])
    encoded = b58encode(raw)
    decoded = b58decode(encoded)
    assert decoded == raw

    # 32-byte Ed25519 key round-trip
    key32 = bytes(range(32))
    enc32 = b58encode(key32)
    dec32 = b58decode(enc32)
    assert dec32 == key32


def test_solana_address_validation_valid():
    for addr in (VALID_SOL_1, VALID_SOL_2, VALID_USDT_MINT):
        ok, err = validate_solana_address(addr)
        assert ok is True, f"Failed for {addr}: {err}"

        val_ok, val_addr = validate_address("SOL", addr)
        assert val_ok is True
        assert val_addr == addr


def test_solana_address_validation_invalid():
    # Bad characters: contains '0', 'O', 'I', or 'l'
    bad_chars = "0" + VALID_SOL_1[1:]
    ok, err = validate_solana_address(bad_chars)
    assert ok is False
    assert "Invalid Base58 characters" in err

    # Too short
    ok, err = validate_solana_address("ShortPubkey")
    assert ok is False
    assert "length" in err.lower()

    # Bitcoin P2PKH address (valid Base58, but 25 bytes payload instead of 32 bytes)
    btc_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    ok, err = validate_solana_address(btc_addr)
    assert ok is False
    assert "25 bytes" in err

    val_ok, msg = validate_address("SOL", btc_addr)
    assert val_ok is False


def test_solana_url_detection():
    url1 = f"https://solscan.io/account/{VALID_SOL_1}"
    d1 = detect_input_kind(url1)
    assert d1["kind"] == "address"
    assert d1["chain"] == "SOL"
    assert d1["value"] == VALID_SOL_1

    url2 = f"https://solana.fm/address/{VALID_SOL_2}"
    d2 = detect_input_kind(url2)
    assert d2["kind"] == "address"
    assert d2["chain"] == "SOL"
    assert d2["value"] == VALID_SOL_2

    url3 = f"https://explorer.solana.com/address/{VALID_SOL_1}"
    d3 = detect_input_kind(url3)
    assert d3["kind"] == "address"
    assert d3["chain"] == "SOL"
    assert d3["value"] == VALID_SOL_1


def test_detect_chain_solana():
    assert detect_chain(VALID_SOL_1) == "SOL"
    assert detect_chain(VALID_SOL_2) == "SOL"
    assert detect_chain(VALID_USDT_MINT) == "SOL"


def test_solana_memo_spam_keywords():
    spam_memo1 = "Claim your free 500 SOL airdrop at https://claim-solana-gift.xyz"
    spam_memo2 = "Visit t.me/solana_drainer_bot for whitelist presale"
    clean_memo = "Order #992 payment"

    assert bool(_SPAM_KEYWORDS.search(spam_memo1)) is True
    assert bool(_SPAM_KEYWORDS.search(spam_memo2)) is True
    assert bool(_SPAM_KEYWORDS.search(clean_memo)) is False


def test_solana_fake_tokens_penalized():
    fake_spl_mint = "FakeMint111111111111111111111111111111111111"
    chain_data = {
        "chain": "SOL",
        "fake_tokens": [{
            "symbol": "USDT",
            "impersonating": "USDT",
            "contract": fake_spl_mint,
            "balance": 10000.0,
        }],
        "tx_list": [],
    }

    score, factors, level, meta = calculate_risk_score(
        sanctions_data={"is_sanctioned": False},
        chain_data=chain_data,
        address=VALID_SOL_1,
    )

    assert score >= 95
    assert level == "CRITICAL"
    assert meta.get("has_fake_assets") is True
    assert any("Fake Asset Detected" in f["desc"] for f in factors)
