"""Screen crypto senders before crediting balance or approving treasury sweep."""
from __future__ import annotations

import json
from typing import Any

from services.live_signals import fetch_live_signals
from services.sanctions import check_sanctions

# pass | review | reject
REJECT = "reject"
REVIEW = "review"
PASS = "pass"


async def screen_address(address: str, chain: str) -> dict[str, Any]:
    """
    Quick treasury-grade screen on payment sender.
    REJECT: sanctions or Tether blacklist (hard stop).
    REVIEW: soft signals (GoPlus flags) — block credit until manual review.
    PASS: clean enough to credit / sweep.
    """
    addr = (address or "").strip()
    chain = (chain or "TRON").upper()
    reasons: list[str] = []

    if not addr or addr.lower() in ("unknown", "none"):
        return {"status": REJECT, "reasons": ["missing_sender"], "detail": {}}

    sanctions = check_sanctions(addr)
    if sanctions.get("is_sanctioned"):
        reasons.append(f"sanctions:{sanctions.get('source') or 'OFAC'}")

    live = await fetch_live_signals(chain, addr)
    if live.get("tether_blacklisted"):
        reasons.append("tether_blacklist")

    goplus = live.get("goplus") or {}
    if isinstance(goplus, dict):
        if str(goplus.get("cybercrime", "0")) == "1":
            reasons.append("goplus:cybercrime")
        if str(goplus.get("money_laundering", "0")) == "1":
            reasons.append("goplus:money_laundering")
        if str(goplus.get("sanctioned", "0")) == "1":
            reasons.append("goplus:sanctioned")

    detail = {
        "sanctions": sanctions,
        "live": {k: v for k, v in live.items() if k != "goplus"},
        "reasons": reasons,
    }

    hard = [r for r in reasons if r.startswith("sanctions") or r == "tether_blacklist" or r == "goplus:sanctioned"]
    if hard:
        return {"status": REJECT, "reasons": reasons, "detail": detail}

    soft = [r for r in reasons if r.startswith("goplus:")]
    if soft:
        return {"status": REVIEW, "reasons": reasons, "detail": detail}

    return {"status": PASS, "reasons": [], "detail": detail}


def screening_to_json(result: dict) -> str:
    return json.dumps({"status": result.get("status"), "reasons": result.get("reasons", [])})
