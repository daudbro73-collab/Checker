"""Live risk signals: GoPlus + Tether on-chain blacklist."""
import json
from typing import Any

import httpx

from services.redis_client import cache_get, cache_set

USDT_ETH = "0xdac17f958d2ee523a2206206994597c13d831ec7"
USDT_BSC = "0x55d398326f99059ff775485246999027b3197955"
USDT_TRON = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# Minimal ABI-encoded isBlackListed(address) selector = 0xfe575a87
IS_BLACKLISTED_SELECTOR = "0xfe575a87"


async def fetch_live_signals(chain: str, address: str) -> dict[str, Any]:
    chain = (chain or "").upper()
    cache_key = f"live:{chain}:{address.lower()}"
    cached = cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass

    result = {
        "goplus": None,
        "tether_blacklisted": False,
        "sources": [],
    }

    goplus = await _goplus_check(chain, address)
    if goplus is not None:
        result["goplus"] = goplus
        result["sources"].append({"name": "GoPlus", "freshness": "live"})

    if chain in ("ETH", "TRON"):
        bl = await _tether_blacklisted(chain, address)
        result["tether_blacklisted"] = bool(bl)
        result["sources"].append({"name": "Tether isBlackListed", "freshness": "live"})

    cache_set(cache_key, json.dumps(result), ttl_seconds=86400)
    return result


async def _goplus_check(chain: str, address: str):
    chain_ids = {"ETH": "1", "BSC": "56", "POLYGON": "137"}
    # GoPlus supports EVM primarily; TRON via separate endpoint if available
    if chain == "TRON":
        url = f"https://api.gopluslabs.io/api/v1/address_security/{address}?chain_id=tron"
    elif chain in chain_ids:
        url = f"https://api.gopluslabs.io/api/v1/address_security/{address}?chain_id={chain_ids[chain]}"
    else:
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=6.0)
            if resp.status_code != 200:
                return None
            data = resp.json()
            result = data.get("result") or {}
            if isinstance(result, dict) and address.lower() in {k.lower() for k in result.keys()}:
                # Some responses nest by address
                for k, v in result.items():
                    if k.lower() == address.lower() and isinstance(v, dict):
                        return v
            if isinstance(result, dict):
                return result
    except Exception:
        return None
    return None


async def _tether_blacklisted(chain: str, address: str) -> bool:
    try:
        if chain == "ETH":
            return await _eth_is_blacklisted(address)
        if chain == "BSC":
            return await _bsc_is_blacklisted(address)
        if chain == "TRON":
            return await _tron_is_blacklisted(address)
    except Exception:
        return False
    return False


async def _eth_is_blacklisted(address: str) -> bool:
    # eth_call isBlackListed(address)
    addr = address.lower().replace("0x", "").zfill(64)
    data = IS_BLACKLISTED_SELECTOR + addr
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": USDT_ETH, "data": data}, "latest"],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://rpc.ankr.com/eth", json=payload, timeout=6.0)
        if resp.status_code != 200:
            return False
        result = (resp.json() or {}).get("result", "0x")
        if not result or result == "0x":
            return False
        return int(result, 16) != 0


async def _bsc_is_blacklisted(address: str) -> bool:
    # eth_call isBlackListed(address) on BSC-USD (Binance-Peg USDT)
    addr = address.lower().replace("0x", "").zfill(64)
    data = IS_BLACKLISTED_SELECTOR + addr
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": USDT_BSC, "data": data}, "latest"],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://rpc.ankr.com/bsc", json=payload, timeout=6.0)
        if resp.status_code != 200:
            return False
        result = (resp.json() or {}).get("result", "0x")
        if not result or result == "0x":
            return False
        return int(result, 16) != 0


async def _tron_is_blacklisted(address: str) -> bool:
    # TronGrid wallet/triggerconstantcontract
    url = "https://api.trongrid.io/wallet/triggerconstantcontract"
    body = {
        "owner_address": address,
        "contract_address": USDT_TRON,
        "function_selector": "isBlackListed(address)",
        "parameter": "",
        "visible": True,
    }
    # Encode address parameter via TronGrid helper is flaky; try events/account API fallback
    # Alternative: Trongrid /v1/accounts does not expose blacklist.
    # Use solidty-style via fullnode with hex owner.
    try:
        async with httpx.AsyncClient() as client:
            # Convert base58 address using trongrid getaccount — if frozen USDT often 0
            # Try contract constant call with visible addresses
            resp = await client.post(url, json={
                "owner_address": address,
                "contract_address": USDT_TRON,
                "function_selector": "isBlackListed(address)",
                "parameter": _tron_address_param_placeholder(address),
                "visible": True,
            }, timeout=6.0)
            if resp.status_code != 200:
                return False
            data = resp.json()
            # constant_result is hex list
            cr = data.get("constant_result") or []
            if not cr:
                return False
            return int(cr[0], 16) != 0
    except Exception:
        return False


def _tron_address_param_placeholder(address: str) -> str:
    """
    Конвертация TRON Base58Check-адреса (T...) → hex-параметр для ABI-вызова.

    Алгоритм:
      1. Base58-декодируем → 25 байт: [0x41][20 байт адреса][4 байта checksum]
      2. Берём 20 байт адреса (байты 1-20), дополняем нулями до 32 байт (64 hex)

    Если адрес уже в hex-формате (41...), используем напрямую.
    При ошибке возвращаем "" — вызов вернёт False (fail-safe).
    """
    _B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    if not address:
        return ""

    # Уже hex-формат: "41" + 40 hex chars = 42 chars
    if address.startswith("41") and len(address) == 42:
        return address[2:].zfill(64)

    # Base58Check формат: начинается с "T", длина 34
    if address.startswith("T") and len(address) == 34:
        try:
            n = 0
            for char in address:
                if char not in _B58_ALPHABET:
                    return ""
                n = n * 58 + _B58_ALPHABET.index(char)
            # 25 байт: 1 (prefix 0x41) + 20 (address) + 4 (checksum)
            raw = n.to_bytes(25, "big")
            # Байты 1..20 — сам адрес (без prefix и checksum)
            addr_bytes = raw[1:21]
            return addr_bytes.hex().zfill(64)
        except Exception:
            return ""

    return ""
