"""
Daily treasury job: screen all deposit addresses BEFORE sweep to treasury.

Sweep itself is manual/off-chain for now (no private keys in app).
Worker marks clean addresses as sweep_ready and logs audit trail.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from config import get_settings
from database import DepositAddress, DepositSweepLog, SessionLocal
from services.chain import ChainService
from services.deposit_pool import QUARANTINE, sync_all_pools, quarantine_address
from services.deposit_screening import REJECT, screen_address

settings = get_settings()


async def screen_deposit_address(db: Session, deposit: DepositAddress) -> DepositSweepLog:
    """Screen one deposit wallet: all inbound senders + balance snapshot."""
    balance = await ChainService.get_usdt_balance(deposit.chain, deposit.address)
    deposit.balance_usdt = round(balance, 4)
    deposit.last_screened_at = datetime.utcnow()

    inbound = await ChainService.get_usdt_inbound_transfers(deposit.chain, deposit.address, limit=30)
    senders = []
    seen = set()
    worst = "pass"
    reasons = []

    for tx in inbound:
        sender = (tx.get("sender") or "").strip()
        if not sender or sender in seen:
            continue
        seen.add(sender)
        screen = await screen_address(sender, deposit.chain)
        senders.append({"sender": sender, "screening": screen.get("status"), "reasons": screen.get("reasons", [])})
        if screen.get("status") == REJECT:
            worst = REJECT
            reasons.extend(screen.get("reasons") or [])

    treasury = settings.TREASURY_ADDRESS_TRON if deposit.chain == "TRON" else settings.TREASURY_ADDRESS_ETH

    if worst == REJECT:
        q = quarantine_address(
            db,
            deposit,
            reason=f"daily_screen:{','.join(sorted(set(reasons)))[:500]}",
        )
        log = DepositSweepLog(
            deposit_address_id=deposit.id,
            chain=deposit.chain,
            balance_usdt=balance,
            senders_json=json.dumps(senders),
            screening_result="quarantine",
            action="quarantined",
            detail=json.dumps(q),
        )
        db.add(log)
        db.add(deposit)
        db.commit()
        return log

    if balance <= 0:
        action = "no_balance"
        detail = "No USDT balance — nothing to sweep"
    elif not treasury:
        action = "manual_sweep"
        detail = f"Clean. Balance {balance} USDT — set TREASURY_ADDRESS_{deposit.chain} and sweep manually"
    else:
        action = "sweep_ready"
        detail = f"Clean. Ready to sweep {balance} USDT → {treasury} (manual or external signer)"
        deposit.last_sweep_at = datetime.utcnow()

    log = DepositSweepLog(
        deposit_address_id=deposit.id,
        chain=deposit.chain,
        balance_usdt=balance,
        senders_json=json.dumps(senders),
        screening_result="pass",
        action=action,
        detail=detail,
    )
    db.add(log)
    db.add(deposit)
    db.commit()
    return log


async def run_daily_treasury_screen() -> dict:
    """
    Run before daily sweep:
    1) Sync pool from env (keep 10 active)
    2) Screen every active + quarantine-with-balance deposit
    """
    db = SessionLocal()
    try:
        sync_reports = sync_all_pools(db)
        targets = db.query(DepositAddress).filter(
            DepositAddress.status.in_(["active", "quarantine"]),
        ).all()

        results = []
        quarantined = 0
        sweep_ready = 0

        for dep in targets:
            if dep.status == QUARANTINE and (dep.balance_usdt or 0) <= 0:
                bal = await ChainService.get_usdt_balance(dep.chain, dep.address)
                if bal <= 0:
                    continue
            log = await screen_deposit_address(db, dep)
            results.append({
                "address": dep.address,
                "chain": dep.chain,
                "action": log.action,
                "balance_usdt": log.balance_usdt,
            })
            if log.action == "quarantined":
                quarantined += 1
            elif log.action == "sweep_ready":
                sweep_ready += 1

        return {
            "ok": True,
            "sync": sync_reports,
            "screened": len(results),
            "quarantined": quarantined,
            "sweep_ready": sweep_ready,
            "results": results,
        }
    finally:
        db.close()
