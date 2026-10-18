"""Token & Asset Validity Service.
Detects Fake USDT / Clone tokens, Honeypots, and malicious mint authorities.
"""
from typing import List, Dict, Any, Optional
import httpx
import logging

logger = logging.getLogger("aml.token_security")

# Official verified token contracts by chain
GENUINE_TOKENS: Dict[str, Dict[str, str]] = {
    "BSC": {
        "USDT": "0x55d398326f99059ff775485246999027b3197955",
        "BSC-USD": "0x55d398326f99059ff775485246999027b3197955",
        "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
        "BUSD": "0xe9e7cea3dedca5984780bafc599bd69add087d56",
        "DAI": "0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3",
        "BTCB": "0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c",
        "ETH": "0x2170ed0880ac9a755fd29b2688956bd959f933f8",
    },
    "ETH": {
        "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f",
        "WBTC": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
    }
}

# Major protected symbols that scammers clone
PROTECTED_SYMBOLS = {"USDT", "BSC-USD", "TETHER", "USDC", "BUSD", "DAI"}


def evaluate_token_balances(chain: str, token_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Inspect all tokens held by a wallet to verify asset validity."""
    chain_norm = (chain or "").upper()
    genuine_map = GENUINE_TOKENS.get(chain_norm, {})

    fake_tokens = []
    verified_tokens = []
    unknown_tokens = []

    for item in token_items or []:
        token_info = item.get("token") or {}
        if not isinstance(token_info, dict):
            continue

        symbol = (token_info.get("symbol") or "").strip().upper()
        name = (token_info.get("name") or "").strip().upper()
        addr = (token_info.get("address") or "").strip().lower()
        decimals = int(token_info.get("decimals") or 18)
        raw_val = item.get("value") or 0
        try:
            balance = float(raw_val) / (10 ** decimals)
        except Exception:
            balance = 0.0

        if not addr:
            continue

        # Check if symbol or name claims to be a protected stablecoin
        claims_usdt = "USDT" in symbol or "TETHER" in name or "BSC-USD" in symbol
        claims_usdc = "USDC" in symbol
        claims_busd = "BUSD" in symbol
        claims_dai = "DAI" in symbol

        target_claim = None
        if claims_usdt:
            target_claim = "USDT"
        elif claims_usdc:
            target_claim = "USDC"
        elif claims_busd:
            target_claim = "BUSD"
        elif claims_dai:
            target_claim = "DAI"

        if target_claim:
            official_addr = genuine_map.get(target_claim, "").lower()
            if official_addr and addr == official_addr:
                verified_tokens.append({
                    "symbol": symbol,
                    "name": token_info.get("name"),
                    "contract": addr,
                    "balance": balance,
                    "status": "GENUINE",
                })
            else:
                # Impersonation detected!
                fake_tokens.append({
                    "symbol": symbol,
                    "name": token_info.get("name"),
                    "contract": addr,
                    "balance": balance,
                    "impersonating": target_claim,
                    "risk": "CRITICAL",
                    "reason": (
                        f"Поддельный токен ({symbol}): адрес контракта не принадлежит официальному эмитенту {target_claim}. "
                        "Баланс не имеет реальной ликвидности (Scam/Honeypot/Fake Deposit)."
                    ),
                })
        else:
            unknown_tokens.append({
                "symbol": symbol,
                "name": token_info.get("name"),
                "contract": addr,
                "balance": balance,
            })

    has_fake = len(fake_tokens) > 0
    return {
        "has_fake_assets": has_fake,
        "fake_tokens": fake_tokens,
        "verified_tokens": verified_tokens,
        "all_tokens_count": len(token_items or []),
        "asset_status": "COMPROMISED" if has_fake else "VERIFIED" if verified_tokens else "STANDARD",
        "headline": (
            f"ВНИМАНИЕ: обнаружено {len(fake_tokens)} поддельных токенов (Fake Asset Scam)"
            if has_fake else "Все ключевые стейблкоины оригинальны и проверены"
        ),
    }


async def check_goplus_token_security(chain: str, contract_address: str) -> Optional[Dict[str, Any]]:
    """Query GoPlus Token Security API for smart contract risks (honeypot, mint, tax)."""
    chain_map = {"ETH": "1", "BSC": "56"}
    chain_id = chain_map.get((chain or "").upper())
    if not chain_id or not contract_address:
        return None

    url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={contract_address.lower()}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code != 200:
                return None
            data = resp.json().get("result", {}) or {}
            addr_data = data.get(contract_address.lower()) or {}
            if not addr_data:
                return None

            is_honeypot = str(addr_data.get("is_honeypot", "0")) == "1"
            is_mintable = str(addr_data.get("is_mintable", "0")) == "1"
            buy_tax = float(addr_data.get("buy_tax", 0) or 0)
            sell_tax = float(addr_data.get("sell_tax", 0) or 0)
            cannot_sell_all = str(addr_data.get("cannot_sell_all", "0")) == "1"

            risks = []
            if is_honeypot:
                risks.append("Honeypot (невозможно продать)")
            if is_mintable:
                risks.append("Открытый минт (эмитент может печатать токены)")
            if sell_tax > 0.15:
                risks.append(f"Грабительская комиссия на продажу ({sell_tax * 100:.0f}%)")
            if cannot_sell_all:
                risks.append("Ограничение на продажу всего объема")

            return {
                "is_honeypot": is_honeypot,
                "is_mintable": is_mintable,
                "buy_tax": buy_tax,
                "sell_tax": sell_tax,
                "risks": risks,
                "safe": len(risks) == 0,
            }
    except Exception as e:
        logger.debug("GoPlus token security check failed for %s: %s", contract_address, e)
        return None
