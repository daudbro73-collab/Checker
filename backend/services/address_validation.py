"""Per-chain address validation + auto-detect."""
import re
from typing import Optional, Tuple
from services.ton_address import parse_and_validate_ton_address
from services.solana_address import validate_solana_address


_ETH_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_BTC_RE = re.compile(r"^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}$")
_TRON_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
_TX_ETH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
_TX_TRON_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def detect_chain(address: str) -> Optional[str]:
    address = (address or "").strip()
    if not address:
        return None
    if _ETH_RE.match(address):
        return "ETH"
    if _TRON_RE.match(address):
        return "TRON"
    if _BTC_RE.match(address):
        return "BTC"
    ok, _, _ = parse_and_validate_ton_address(address)
    if ok:
        return "TON"
    ok_sol, _ = validate_solana_address(address)
    if ok_sol:
        return "SOL"
    return None


def detect_input_kind(text: str) -> dict:
    """Parse pasted text: wallet address vs tx hash vs unknown."""
    text = (text or "").strip()
    # Explorer URL crumbs
    lower = text.lower()
    for marker, chain in (
        ("tronscan.org", "TRON"),
        ("etherscan.io", "ETH"),
        ("bscscan.com", "BSC"),
        ("tonviewer.com", "TON"),
        ("tonscan.org", "TON"),
        ("tonapi.io", "TON"),
        ("solscan.io", "SOL"),
        ("solana.fm", "SOL"),
        ("explorer.solana.com", "SOL"),
        ("mempool.space", "BTC"),
        ("blockchain.com/btc", "BTC"),
    ):
        if marker in lower:
            # try extract last path segment
            part = text.rstrip("/").split("/")[-1]
            if detect_chain(part):
                return {"kind": "address", "chain": chain if chain in ("BSC", "TON", "SOL") else detect_chain(part), "value": part}
            if _TX_ETH_RE.match(part) or _TX_TRON_RE.match(part):
                return {"kind": "txid", "chain": chain, "value": part}

    chain = detect_chain(text)
    if chain:
        return {"kind": "address", "chain": chain, "value": text}
    if _TX_ETH_RE.match(text):
        return {"kind": "txid", "chain": "ETH", "value": text}
    if _TX_TRON_RE.match(text) and not text.startswith("0x"):
        return {"kind": "txid", "chain": "TRON", "value": text}
    return {"kind": "unknown", "chain": None, "value": text}


def validate_address(chain: str, address: str) -> Tuple[bool, str]:
    chain = (chain or "").upper()
    address = (address or "").strip()
    if not address:
        return False, "Address is required"

    if chain in ("ETH", "BSC"):
        if not _ETH_RE.match(address):
            return False, f"Invalid {chain} address format"
        return True, address

    if chain == "TRON":
        if not _TRON_RE.match(address):
            return False, "Invalid TRON address format"
        return True, address

    if chain == "BTC":
        # Bech32 is case-insensitive; normalize to lowercase for bc1*
        if address.lower().startswith("bc1"):
            address = address.lower()
        if not _BTC_RE.match(address):
            return False, "Invalid BTC address format"
        return True, address

    if chain == "TON":
        ok, err, info = parse_and_validate_ton_address(address)
        if not ok or not info:
            return False, err or "Invalid TON address format"
        return True, info["bounceable"]

    if chain == "SOL":
        ok, err = validate_solana_address(address)
        if not ok:
            return False, err or "Invalid Solana address format"
        return True, address

    return False, f"Unsupported chain: {chain}"
