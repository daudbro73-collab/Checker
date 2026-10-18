"""Deposit address pool — start with 1, grow to N; quarantine + auto-promote/generate."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config import get_settings
from database import DepositAddress

settings = get_settings()

ACTIVE = "active"
STANDBY = "standby"
QUARANTINE = "quarantine"
RETIRED = "retired"


def _parse_pool_env(chain: str) -> list[str]:
    chain = chain.upper()
    if chain == "TRON":
        raw = settings.DEPOSIT_POOL_TRON
        legacy = settings.PAYMENT_ADDRESS_TRON
    elif chain == "BSC":
        raw = getattr(settings, "DEPOSIT_POOL_BSC", "")
        legacy = getattr(settings, "PAYMENT_ADDRESS_BSC", "") or settings.PAYMENT_ADDRESS_ETH
    elif chain == "SOL":
        raw = getattr(settings, "DEPOSIT_POOL_SOL", "")
        legacy = getattr(settings, "PAYMENT_ADDRESS_SOL", "")
    else:
        raw = settings.DEPOSIT_POOL_ETH
        legacy = settings.PAYMENT_ADDRESS_ETH

    if not raw:
        return [legacy.strip()] if legacy and legacy.strip() else []
    return [a.strip() for a in raw.split(",") if a.strip()]


def sync_pool_from_config(db: Session, chain: str = "TRON") -> dict:
    """
    Load addresses from env into DB.
    Keeps up to DEPOSIT_POOL_SIZE in 'active' (default 1), rest 'standby'.
    Quarantined addresses are never re-activated automatically.
    """
    chain = chain.upper()
    addresses = _parse_pool_env(chain)
    if not addresses:
        return {"chain": chain, "synced": 0, "active": 0, "message": "no addresses in config"}

    target_active = min(settings.DEPOSIT_POOL_SIZE, len(addresses))
    seen = set()

    for addr in addresses:
        if addr in seen:
            continue
        seen.add(addr)
        row = db.query(DepositAddress).filter(
            DepositAddress.address == addr,
            DepositAddress.chain == chain,
        ).first()
        if not row:
            db.add(DepositAddress(address=addr, chain=chain, status=STANDBY))

    db.flush()

    active_rows = (
        db.query(DepositAddress)
        .filter(DepositAddress.chain == chain, DepositAddress.status == ACTIVE)
        .order_by(DepositAddress.slot.asc().nulls_last(), DepositAddress.id.asc())
        .all()
    )
    quarantined = db.query(DepositAddress).filter(
        DepositAddress.chain == chain,
        DepositAddress.status == QUARANTINE,
    ).count()

    need = target_active - len(active_rows)
    if need > 0:
        standby = (
            db.query(DepositAddress)
            .filter(DepositAddress.chain == chain, DepositAddress.status == STANDBY)
            .order_by(DepositAddress.id.asc())
            .limit(need)
            .all()
        )
        for row in standby:
            row.status = ACTIVE
            active_rows.append(row)

    if len(active_rows) > target_active:
        for row in sorted(active_rows, key=lambda r: r.slot or 999)[target_active:]:
            row.status = STANDBY
            row.slot = None
        active_rows = active_rows[:target_active]

    for i, row in enumerate(sorted(active_rows, key=lambda r: r.id), start=1):
        row.slot = i
        row.status = ACTIVE

    db.commit()
    active_count = db.query(DepositAddress).filter(
        DepositAddress.chain == chain, DepositAddress.status == ACTIVE
    ).count()
    standby_count = db.query(DepositAddress).filter(
        DepositAddress.chain == chain, DepositAddress.status == STANDBY
    ).count()

    return {
        "chain": chain,
        "synced": len(addresses),
        "active": active_count,
        "standby": standby_count,
        "quarantined": quarantined,
        "target_active": target_active,
        "auto_generate": settings.DEPOSIT_AUTO_GENERATE,
    }


def sync_all_pools(db: Session) -> list[dict]:
    out = []
    for chain in ("TRON", "ETH", "BSC", "SOL"):
        if _parse_pool_env(chain):
            out.append(sync_pool_from_config(db, chain))
    return out


def get_active_addresses(db: Session, chain: str) -> list[DepositAddress]:
    chain = chain.upper()
    rows = (
        db.query(DepositAddress)
        .filter(DepositAddress.chain == chain, DepositAddress.status == ACTIVE)
        .order_by(DepositAddress.slot.asc(), DepositAddress.id.asc())
        .all()
    )
    if rows:
        return rows
    sync_pool_from_config(db, chain)
    return (
        db.query(DepositAddress)
        .filter(DepositAddress.chain == chain, DepositAddress.status == ACTIVE)
        .order_by(DepositAddress.slot.asc(), DepositAddress.id.asc())
        .all()
    )


def assign_deposit_address(
    db: Session,
    chain: str,
    user_id: Optional[int] = None,
    reservation_seconds: int = 300,
) -> Optional[DepositAddress]:
    """
    Assign an active deposit address, prioritizing 5-minute (reservation_seconds)
    slot reservation for user_id to prevent front-running and race conditions.
    """
    active = get_active_addresses(db, chain)
    if not active:
        return None

    now = datetime.utcnow()
    row = None

    if user_id:
        # 1. Reuse existing active non-expired reservation for this user
        for r in active:
            if r.reserved_by_user_id == user_id and r.reserved_until and r.reserved_until > now:
                row = r
                break

        # 2. Pick a free slot (unreserved or expired reservation)
        if not row:
            free_slots = [
                r for r in active
                if not r.reserved_until or r.reserved_until <= now or r.reserved_by_user_id == user_id
            ]
            if free_slots:
                row = min(free_slots, key=lambda r: r.last_assigned_at or datetime.min)

    # 3. Fallback to least recently assigned if all slots currently held
    if not row:
        row = min(active, key=lambda r: r.last_assigned_at or datetime.min)

    if user_id:
        row.reserved_by_user_id = user_id
        row.reserved_until = now + timedelta(seconds=reservation_seconds)

    row.last_assigned_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def find_deposit_by_address(db: Session, chain: str, address: str) -> Optional[DepositAddress]:
    return (
        db.query(DepositAddress)
        .filter(DepositAddress.chain == chain.upper(), DepositAddress.address == address)
        .first()
    )


def is_active_pool_address(db: Session, chain: str, address: str) -> bool:
    row = find_deposit_by_address(db, chain, address)
    return bool(row and row.status == ACTIVE)


def _next_hd_index(db: Session, chain: str) -> int:
    base = settings.DEPOSIT_HD_INDEX_TRON if chain == "TRON" else settings.DEPOSIT_HD_INDEX_ETH
    total = db.query(DepositAddress).filter(DepositAddress.chain == chain).count()
    return max(base, total)


def try_auto_add_standby(db: Session, chain: str) -> Optional[DepositAddress]:
    """Create one new standby via HD when DEPOSIT_AUTO_GENERATE is on."""
    from services.deposit_keys import DepositKeyError, can_auto_generate, generate_next_address

    if not can_auto_generate():
        return None
    chain = chain.upper()
    try:
        derived = generate_next_address(chain, _next_hd_index(db, chain))
    except DepositKeyError as e:
        print(f"[deposit_pool] auto-generate skipped: {e}")
        return None

    exists = find_deposit_by_address(db, chain, derived["address"])
    if exists:
        return exists

    row = DepositAddress(
        address=derived["address"],
        chain=chain,
        status=STANDBY,
    )
    db.add(row)
    db.flush()
    print(f"[deposit_pool] auto-added standby {derived['address']} index={derived['index']}")
    return row


def ensure_active_count(db: Session, chain: str) -> dict:
    """After quarantine: promote standby or auto-generate until active ≈ DEPOSIT_POOL_SIZE."""
    chain = chain.upper()
    target = settings.DEPOSIT_POOL_SIZE
    active_count = db.query(DepositAddress).filter(
        DepositAddress.chain == chain, DepositAddress.status == ACTIVE
    ).count()
    promoted = None
    generated = None

    while active_count < target:
        standby = (
            db.query(DepositAddress)
            .filter(DepositAddress.chain == chain, DepositAddress.status == STANDBY)
            .order_by(DepositAddress.id.asc())
            .first()
        )
        if not standby:
            standby = try_auto_add_standby(db, chain)
            if standby:
                generated = standby.address
            else:
                break
        standby.status = ACTIVE
        used_slots = [
            r.slot for r in db.query(DepositAddress).filter(
                DepositAddress.chain == chain,
                DepositAddress.status == ACTIVE,
                DepositAddress.id != standby.id,
            ).all() if r.slot
        ]
        standby.slot = max(used_slots, default=0) + 1
        promoted = standby.address
        db.add(standby)
        db.flush()
        active_count += 1

    db.commit()
    return {
        "active_count": active_count,
        "target": target,
        "promoted": promoted,
        "generated": generated,
        "shortfall": max(0, target - active_count),
    }


def quarantine_address(db: Session, deposit: DepositAddress, reason: str) -> dict:
    """
    Freeze dirty deposit. Promote standby (or auto-generate) so active count stays at target.
    With 1 address and no standby/auto: active drops to 0 until you add a new address.
    """
    deposit.status = QUARANTINE
    deposit.quarantine_reason = reason[:2000]
    deposit.quarantined_at = datetime.utcnow()
    deposit.slot = None
    db.add(deposit)
    db.flush()

    refill = ensure_active_count(db, deposit.chain)

    return {
        "quarantined": deposit.address,
        "reason": reason,
        "promoted": refill.get("promoted"),
        "generated": refill.get("generated"),
        "active_count": refill.get("active_count"),
        "target": settings.DEPOSIT_POOL_SIZE,
        "shortfall": refill.get("shortfall"),
        "warning": (
            "No standby left — add address to DEPOSIT_POOL_* or enable DEPOSIT_AUTO_GENERATE"
            if refill.get("shortfall")
            else None
        ),
    }


def pool_status(db: Session, chain: Optional[str] = None) -> dict:
    from services.deposit_keys import can_auto_generate

    chains = [chain.upper()] if chain else ["TRON", "ETH", "BSC", "SOL"]
    treasury_map = {
        "TRON": settings.TREASURY_ADDRESS_TRON,
        "ETH": settings.TREASURY_ADDRESS_ETH,
        "BSC": getattr(settings, "TREASURY_ADDRESS_BSC", "") or settings.TREASURY_ADDRESS_ETH,
        "SOL": getattr(settings, "TREASURY_ADDRESS_SOL", ""),
    }
    result = {}
    for ch in chains:
        rows = db.query(DepositAddress).filter(DepositAddress.chain == ch).order_by(DepositAddress.slot).all()
        if not rows:
            continue
        result[ch] = {
            "target_active": settings.DEPOSIT_POOL_SIZE,
            "auto_generate": can_auto_generate(),
            "treasury": treasury_map.get(ch, ""),
            "addresses": [
                {
                    "id": r.id,
                    "address": r.address,
                    "status": r.status,
                    "slot": r.slot,
                    "balance_usdt": r.balance_usdt,
                    "last_screened_at": r.last_screened_at.isoformat() if r.last_screened_at else None,
                    "last_sweep_at": r.last_sweep_at.isoformat() if r.last_sweep_at else None,
                    "quarantine_reason": r.quarantine_reason,
                }
                for r in rows
            ],
        }
    return result
