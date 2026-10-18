"""TON address validation, checksum verification, and canonicalization.
Supports:
- User-friendly Bounceable: EQ...
- User-friendly Non-bounceable: UQ...
- Raw hex format: 0:<64 hex chars> or -1:<64 hex chars>
"""
import base64
import re
from typing import Tuple, Optional, Dict

_RAW_TON_RE = re.compile(r"^(-?1|0):[a-fA-F0-9]{64}$")
_B64_TON_RE = re.compile(r"^[a-zA-Z0-9_-]{48}$")


def crc16_ton(data: bytes) -> int:
    """CRC16-CCITT implementation used by TON blockchain."""
    crc = 0
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xffff
            else:
                crc = (crc << 1) & 0xffff
    return crc


def parse_and_validate_ton_address(addr_str: str) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
    """
    Validates a TON address and returns:
    (is_valid, error_msg, {
        'raw': '0:hex...',
        'bounceable': 'EQ...',
        'non_bounceable': 'UQ...',
        'workchain': 0
    })
    """
    addr_str = (addr_str or "").strip()
    if not addr_str:
        return False, "Address is required", None

    # Case 1: Raw format: 0:<hex>
    if _RAW_TON_RE.match(addr_str):
        parts = addr_str.split(":", 1)
        wc = int(parts[0])
        account_id_hex = parts[1].lower()
        account_id_bytes = bytes.fromhex(account_id_hex)
        wc_byte = wc if wc >= 0 else (wc + 256)

        # Build bounceable (0x11)
        data_b = bytes([0x11, wc_byte]) + account_id_bytes
        crc_b = crc16_ton(data_b).to_bytes(2, "big")
        bounceable = base64.urlsafe_b64encode(data_b + crc_b).decode("ascii")

        # Build non-bounceable (0x51)
        data_u = bytes([0x51, wc_byte]) + account_id_bytes
        crc_u = crc16_ton(data_u).to_bytes(2, "big")
        non_bounceable = base64.urlsafe_b64encode(data_u + crc_u).decode("ascii")

        return True, None, {
            "raw": f"{wc}:{account_id_hex}",
            "bounceable": bounceable,
            "non_bounceable": non_bounceable,
            "workchain": wc,
        }

    # Case 2: User-friendly Base64url format
    if _B64_TON_RE.match(addr_str):
        try:
            # Pad base64 if needed
            padded = addr_str + "=" * ((4 - len(addr_str) % 4) % 4)
            raw_bytes = base64.urlsafe_b64decode(padded)
            if len(raw_bytes) != 36:
                return False, "Invalid TON address byte length (expected 36 bytes)", None

            data_part = raw_bytes[:34]
            stored_crc = int.from_bytes(raw_bytes[34:36], "big")
            calc_crc = crc16_ton(data_part)
            if stored_crc != calc_crc:
                return False, "Invalid TON address CRC16 checksum", None

            flags = data_part[0]
            wc_byte = data_part[1]
            wc = wc_byte if wc_byte < 128 else (wc_byte - 256)
            account_id_hex = data_part[2:34].hex().lower()
            raw_addr = f"{wc}:{account_id_hex}"

            # Compute canonical bounceable & non-bounceable
            account_id_bytes = data_part[2:34]
            data_b = bytes([0x11, wc_byte]) + account_id_bytes
            crc_b = crc16_ton(data_b).to_bytes(2, "big")
            bounceable = base64.urlsafe_b64encode(data_b + crc_b).decode("ascii")

            data_u = bytes([0x51, wc_byte]) + account_id_bytes
            crc_u = crc16_ton(data_u).to_bytes(2, "big")
            non_bounceable = base64.urlsafe_b64encode(data_u + crc_u).decode("ascii")

            return True, None, {
                "raw": raw_addr,
                "bounceable": bounceable,
                "non_bounceable": non_bounceable,
                "workchain": wc,
            }
        except Exception as e:
            return False, f"Failed to parse TON base64 address: {e}", None

    return False, "Invalid TON address format (expected EQ..., UQ..., or 0:hex)", None


def canonical_ton_address(addr_str: str) -> Optional[str]:
    """Returns canonical bounceable 'EQ...' address or raw if failed."""
    ok, _, info = parse_and_validate_ton_address(addr_str)
    if ok and info:
        return info["bounceable"]
    return addr_str
