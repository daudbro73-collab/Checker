import pytest
from config import get_settings
from services.address_validation import validate_address, detect_input_kind
from services.chain import ChainService

settings = get_settings()

VALID_BSC_ADDR = "0x8894e0a0c962cb723c1976a4421c95949be2d4e3"  # Binance hot wallet
INVALID_BSC_ADDR = "0x123notvalid"


def test_bsc_in_allowed_chains():
    assert "BSC" in settings.ALLOWED_CHAINS


def test_bsc_address_validation():
    ok, val = validate_address("BSC", VALID_BSC_ADDR)
    assert ok is True
    assert val == VALID_BSC_ADDR

    ok_bad, msg = validate_address("BSC", INVALID_BSC_ADDR)
    assert ok_bad is False
    assert "Invalid BSC address format" in msg


def test_bscscan_url_detection():
    url = f"https://bscscan.com/address/{VALID_BSC_ADDR}"
    detected = detect_input_kind(url)
    assert detected["kind"] == "address"
    assert detected["chain"] == "BSC"
    assert detected["value"] == VALID_BSC_ADDR


def test_bsc_chain_service_config():
    assert "BSC" in ChainService.RPC_URLS
    assert "BSC" in ChainService.BLOCKSCOUT
    assert "BSC" in ChainService.WEB_EXPLORERS
    assert ChainService.RPC_URLS["BSC"] == "https://rpc.ankr.com/bsc"
    assert ChainService.BLOCKSCOUT["BSC"] == "https://bsc.blockscout.com/api/v2"
