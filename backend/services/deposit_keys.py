"""
HD deposit address generator — stub now, enable later with DEPOSIT_AUTO_GENERATE=true.

Why stub:
  - Private keys must NOT live in the app process without vault/HSM.
  - You start with 1 manual address; later enable mnemonic → auto-create standby.

When enabled (future):
  TRON: BIP44 m/44'/195'/0'/0/{index}
  ETH:  BIP44 m/44'/60'/0'/0/{index}

Returns public address only; signing/sweep stays external or in a locked signer.
"""
from __future__ import annotations

from typing import Optional

from config import get_settings

settings = get_settings()


class DepositKeyError(Exception):
    pass


def can_auto_generate() -> bool:
    return bool(settings.DEPOSIT_AUTO_GENERATE and settings.DEPOSIT_HD_MNEMONIC.strip())


def generate_next_address(chain: str, next_index: int) -> Optional[dict]:
    """
    Derive next deposit address from HD mnemonic.
    Returns {"address": "...", "index": N, "chain": "..."} or raises if not configured.

    Currently: raises DepositKeyError — install tronpy/eth-account + set mnemonic to enable.
    """
    chain = (chain or "TRON").upper()
    if not can_auto_generate():
        raise DepositKeyError(
            "Auto-generate off. Set DEPOSIT_AUTO_GENERATE=true and DEPOSIT_HD_MNEMONIC, "
            "or add addresses manually to DEPOSIT_POOL_*."
        )

    mnemonic = settings.DEPOSIT_HD_MNEMONIC.strip()
    if chain == "TRON":
        return _derive_tron(mnemonic, next_index)
    if chain == "ETH":
        return _derive_eth(mnemonic, next_index)
    raise DepositKeyError(f"Unsupported chain for HD: {chain}")


def _derive_tron(mnemonic: str, index: int) -> dict:
    """BIP44 Tron — implement when enabling auto-generate."""
    try:
        from tronpy.keys import PrivateKey  # type: ignore
        from mnemonic import Mnemonic  # type: ignore
        from bip32 import BIP32  # type: ignore
    except ImportError as e:
        raise DepositKeyError(
            "Install packages for HD: pip install tronpy mnemonic bip32"
        ) from e

    seed = Mnemonic("english").to_seed(mnemonic)
    bip32 = BIP32.from_seed(seed)
    # m/44'/195'/0'/0/{index}
    path = f"m/44'/195'/0'/0/{index}"
    child = bip32.get_privkey_from_path(path)
    pk = PrivateKey(child)
    address = pk.public_key.to_base58check_address()
    return {"address": address, "index": index, "chain": "TRON", "path": path}


def _derive_eth(mnemonic: str, index: int) -> dict:
    try:
        from eth_account import Account  # type: ignore
    except ImportError as e:
        raise DepositKeyError("Install eth-account for ETH HD") from e

    Account.enable_unaudited_hdwallet_features()
    path = f"m/44'/60'/0'/0/{index}"
    acct = Account.from_mnemonic(mnemonic, account_path=path)
    return {"address": acct.address, "index": index, "chain": "ETH", "path": path}
