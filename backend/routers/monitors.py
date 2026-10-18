"""
Monitors router — address monitoring CRUD and status checks.
Prefix: /auth (preserves /auth/monitors backward compatibility)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from database import AddressMonitor, User
from dependencies import get_current_user, get_db

router = APIRouter(prefix="/auth", tags=["monitors"])
settings = get_settings()


class MonitorCreate(BaseModel):
    address: str
    chain: str = "ETH"
    label: Optional[str] = None


@router.get("/monitors")
def list_monitors(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(AddressMonitor)
        .filter(AddressMonitor.user_id == current_user.id, AddressMonitor.active == True)
        .order_by(AddressMonitor.id.desc())
        .all()
    )
    return {
        "monitors": [
            {
                "id": m.id,
                "address": m.address,
                "chain": m.chain,
                "label": m.label,
                "last_score": m.last_score,
                "last_level": m.last_level,
                "last_checked_at": m.last_checked_at.isoformat() if m.last_checked_at else None,
                "notify_telegram": m.notify_telegram,
            }
            for m in rows
        ],
        "max_per_user": settings.MONITOR_MAX_PER_USER,
    }


@router.post("/monitors")
async def add_monitor(body: MonitorCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Watch an address — worker rechecks periodically and TGs on risk change."""
    address = (body.address or "").strip()
    chain = (body.chain or "ETH").upper()
    if not address:
        raise HTTPException(status_code=400, detail="Address required")
    if chain not in settings.ALLOWED_CHAINS:
        raise HTTPException(status_code=400, detail="Unsupported chain")

    count = db.query(AddressMonitor).filter(
        AddressMonitor.user_id == current_user.id,
        AddressMonitor.active == True,
    ).count()
    if count >= settings.MONITOR_MAX_PER_USER:
        raise HTTPException(status_code=400, detail=f"Max {settings.MONITOR_MAX_PER_USER} monitors")

    existing = db.query(AddressMonitor).filter(
        AddressMonitor.user_id == current_user.id,
        AddressMonitor.address == address,
        AddressMonitor.chain == chain,
        AddressMonitor.active == True,
    ).first()
    if existing:
        if body.label:
            existing.label = body.label[:80]
            db.commit()
        return {"status": "exists", "monitor": {"id": existing.id, "address": existing.address, "chain": existing.chain, "label": existing.label}}

    m = AddressMonitor(
        user_id=current_user.id,
        address=address,
        chain=chain,
        label=(body.label or "").strip()[:80] or None,
        active=True,
        notify_telegram=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    # Baseline score now (free, not billed)
    try:
        from services.monitor_worker import recheck_monitor
        await recheck_monitor(db, m)
        db.refresh(m)
    except Exception as e:
        print(f"monitor baseline: {e}")

    return {
        "status": "ok",
        "monitor": {
            "id": m.id,
            "address": m.address,
            "chain": m.chain,
            "label": m.label,
            "last_score": m.last_score,
            "last_level": m.last_level,
        },
    }


@router.delete("/monitors/{monitor_id}")
def delete_monitor(monitor_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.query(AddressMonitor).filter(AddressMonitor.id == monitor_id, AddressMonitor.user_id == current_user.id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    m.active = False
    db.commit()
    return {"status": "ok"}


@router.patch("/monitors/{monitor_id}")
def update_monitor(
    monitor_id: int,
    label: Optional[str] = None,
    notify_telegram: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = db.query(AddressMonitor).filter(AddressMonitor.id == monitor_id, AddressMonitor.user_id == current_user.id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    if label is not None:
        m.label = label.strip()[:80] or None
    if notify_telegram is not None:
        m.notify_telegram = notify_telegram
    db.commit()
    return {"status": "ok", "id": m.id, "label": m.label, "notify_telegram": m.notify_telegram}
