"""
Wave B — address monitoring: recheck wallets and notify on risk change.

Why: OTC/P2P users need alerts when a counterparty wallet gets dirtier after they checked it.
Rechecks are free (product retention), not billed per check.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Optional

import httpx

from config import get_settings
from database import AddressMonitor, SessionLocal, User
from services.analysis import analyze_wallet

settings = get_settings()
logger = logging.getLogger(__name__)


async def _notify_telegram(telegram_id: int, text: str) -> bool:
    if not settings.BOT_TOKEN or not telegram_id:
        return False
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"chat_id": telegram_id, "text": text, "disable_web_page_preview": True},
                timeout=10.0,
            )
            return resp.status_code == 200
    except Exception as e:
        logger.warning("[monitor] telegram notify failed: %s", e)
        return False


def _short(addr: str) -> str:
    if not addr or len(addr) < 12:
        return addr or ""
    return f"{addr[:6]}…{addr[-4:]}"


async def recheck_monitor(db, monitor: AddressMonitor) -> dict:
    """Run analysis, update score, notify if level/score changed meaningfully."""
    user = db.query(User).filter(User.id == monitor.user_id).first()
    try:
        result = await analyze_wallet(monitor.address, monitor.chain)
    except Exception as e:
        return {"id": monitor.id, "error": str(e)}

    score = int(result.get("risk_score") or 0)
    level = (result.get("risk_level") or "SAFE").upper()
    prev_score = monitor.last_score
    prev_level = (monitor.last_level or "").upper() or None

    changed = prev_score is None or prev_level != level or abs((prev_score or 0) - score) >= 5

    monitor.last_score = score
    monitor.last_level = level
    monitor.last_checked_at = datetime.utcnow()
    db.add(monitor)
    db.commit()

    notified = False
    if changed and monitor.notify_telegram and user and user.telegram_id:
        name = monitor.label or _short(monitor.address)
        if prev_level is None:
            text = (
                f"AML Guard monitor set\n"
                f"{name} ({monitor.chain})\n"
                f"Baseline: {level} — {score}/100\n"
                f"We will notify you if risk changes."
            )
        else:
            text = (
                f"⚠ AML Guard alert\n"
                f"{name} ({monitor.chain})\n"
                f"{prev_level} {prev_score} → {level} {score}\n"
                f"Open Mini App to re-check before sending funds.\n"
                f"(Informational — not legal advice)"
            )
        notified = await _notify_telegram(int(user.telegram_id), text)

    return {
        "id": monitor.id,
        "address": monitor.address,
        "chain": monitor.chain,
        "score": score,
        "level": level,
        "changed": changed,
        "notified": notified,
    }


async def run_monitor_pass(limit: int = 50) -> dict:
    """Recheck monitors that are due (never checked or older than interval)."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=settings.MONITOR_RECHECK_INTERVAL_SECONDS)
        due = (
            db.query(AddressMonitor)
            .filter(AddressMonitor.active == True)
            .filter(
                (AddressMonitor.last_checked_at == None) | (AddressMonitor.last_checked_at < cutoff)
            )
            .order_by(AddressMonitor.last_checked_at.asc().nullsfirst())
            .limit(limit)
            .all()
        )
        results = []
        for m in due:
            results.append(await recheck_monitor(db, m))
        return {
            "ok": True,
            "checked": len(results),
            "changed": sum(1 for r in results if r.get("changed")),
            "notified": sum(1 for r in results if r.get("notified")),
            "results": results,
        }
    finally:
        db.close()


async def monitor_loop():
    import asyncio

    interval = min(3600, max(300, settings.MONITOR_RECHECK_INTERVAL_SECONDS // 6))
    while True:
        try:
            report = await run_monitor_pass()
            logger.info(
                "[monitor] checked=%s changed=%s notified=%s",
                report.get('checked'), report.get('changed'), report.get('notified'),
            )
        except Exception as e:
            logger.error("[monitor] pass failed: %s", e, exc_info=True)
        await asyncio.sleep(interval)
