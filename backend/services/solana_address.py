"""Solana address validation and Base58 decoding.
Solana addresses are 32-byte Ed25519 public keys encoded in Base58 (32-44 characters).
"""
import re
from typing import Tuple, Optional

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_MAP = {c: i for i, c in enumerate(_B58_ALPHABET)}
_SOL_CHAR_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def b58decode(s: str) -> Optional[bytes]:
    """Decode a Base58 string into raw bytes."""
    if not s:
        return None
    num = 0
    for char in s:
        if char not in _B58_MAP:
            return None
        num = num * 58 + _B58_MAP[char]

    # Count leading '1's which represent zero bytes
    leading_zeros = 0
    for char in s:
        if char == "1":
            leading_zeros += 1
        else:
            break

    # Convert integer to bytes
    res = bytearray()
    while num > 0:
        res.append(num & 0xFF)
        num >>= 8
    res.reverse()

    return bytes(leading_zeros) + bytes(res)


def b58encode(b: bytes) -> str:
    """Encode bytes into a Base58 string."""
    if not b:
        return ""
    num = int.from_bytes(b, "big")
    chars = []
    while num > 0:
        num, rem = divmod(num, 58)
        chars.append(_B58_ALPHABET[rem])
    chars.reverse()

    # Leading zeros
    leading_ones = 0
    for byte in b:
        if byte == 0:
            leading_ones += 1
        else:
            break

    return ("1" * leading_ones) + "".join(chars)


def validate_solana_address(addr_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validates a Solana address.
    Checks:
    1. Length is between 32 and 44 Base58 characters.
    2. Uses valid Base58 alphabet (no 0, O, I, l).
    3. Decodes to exactly 32 bytes (Ed25519 public key).
    """
    addr_str = (addr_str or "").strip()
    if not addr_str:
        return False, "Address is required"

    if not _SOL_CHAR_RE.match(addr_str):
        if len(addr_str) < 32 or len(addr_str) > 44:
            return False, f"Invalid Solana address length: {len(addr_str)} chars (expected 32-44)"
        return False, "Invalid Base58 characters in Solana address (cannot contain 0, O, I, or l)"

    raw_bytes = b58decode(addr_str)
    if raw_bytes is None:
        return False, "Failed to decode Base58 Solana address"

    if len(raw_bytes) != 32:
        return False, f"Invalid Solana address payload: {len(raw_bytes)} bytes (expected 32 bytes)"

    return True, None
