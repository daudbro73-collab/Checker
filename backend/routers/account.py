"""
Account router — billing, history, disputes, API keys.
Prefix: /auth  (same prefix — backward-compatible with existing clients)
"""
import hashlib
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from database import ApiKey, CheckHistory, Dispute, Payment, User
from dependencies import get_current_user, get_db
from services.billing import apply_package
from services.chain import ChainService

router = APIRouter(prefix="/auth", tags=["account"])
settings = get_settings()
logger = logging.getLogger(__name__)


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    tx_hash: str = ""
    chain: str = "TRON"
    product: str = "balance"  # balance | pack_10 | pack_20 | api_starter | api_pro


class DisputeCreate(BaseModel):
    address: str
    chain: str = "ETH"
    check_id: Optional[int] = None
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _issue_api_key(db: Session, user: User, plan: str) -> str:
    """Создаёт API-ключ и возвращает raw значение — показывается пользователю ОДИН раз."""
    raw = "aml_" + secrets.token_urlsafe(24)
    plan_info = settings.API_PLANS[plan]
    db.add(ApiKey(
        user_id=user.id,
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        key_prefix=raw[:10],
        plan=plan,
        quota_monthly=plan_info["quota"],
        used_this_month=0,
        active=True,
    ))
    db.commit()
    return raw


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/history")
def get_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """История платежей и проверок пользователя."""
    payments = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
    checks = (
        db.query(CheckHistory)
        .filter(CheckHistory.user_id == current_user.id)
        .order_by(CheckHistory.created_at.desc())
        .all()
    )
    return {"payments": payments, "checks": checks}


@router.get("/payment/config")
def payment_config(db: Session = Depends(get_db)):
    """Конфигурация платёжных методов, пул депозитных адресов, цены."""
    from services.deposit_pool import get_active_addresses, pool_status, sync_all_pools
    from services.payments import list_providers, product_catalog

    sync_all_pools(db)
    pool = pool_status(db)
    addresses = {}
    for chain in ("TRON", "ETH"):
        active = get_active_addresses(db, chain)
        if active:
            addresses[chain] = active[0].address
        else:
            legacy = settings.PAYMENT_ADDRESS_TRON if chain == "TRON" else settings.PAYMENT_ADDRESS_ETH
            if legacy:
                addresses[chain] = legacy

    return {
        "chains": list(addresses.keys()) or ["TRON"],
        "addresses": addresses,
        "deposit_pool_size": settings.DEPOSIT_POOL_SIZE,
        "deposit_pool": pool,
        "treasury": {
            "TRON": settings.TREASURY_ADDRESS_TRON,
            "ETH": settings.TREASURY_ADDRESS_ETH,
        },
        "price_per_check": settings.PRICE_PER_CHECK,
        "packages": settings.PACKAGES,
        "api_plans": settings.API_PLANS,
        "products": product_catalog(),
        "methods": list_providers(),
        "usd_rub_rate": settings.USD_RUB_RATE,
        "trial_checks_per_day": settings.FREE_CHECKS_PER_DAY,
        "preferred_chain": "TRON",
        "preferred_currency": "USDT",
        "preferred_method": "crypto_usdt",
        "note": "Use POST /payments/create for assigned deposit address from 10-address pool",
    }


@router.post("/topup")
async def topup(
    payment: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy topup — same pool + sender screening as /payments/confirm."""
    from services.deposit_pool import get_active_addresses
    from services.payment_fulfill import PaymentRejected, verify_and_fulfill_crypto_payment

    chain = (payment.chain or "TRON").upper()
    tx_hash = (payment.tx_hash or "").strip()
    if not tx_hash:
        raise HTTPException(status_code=400, detail="Transaction hash is required")
    if tx_hash.startswith("sim_"):
        raise HTTPException(status_code=400, detail="Simulation payments are disabled")
    if db.query(Payment).filter(Payment.tx_hash == tx_hash).first():
        raise HTTPException(status_code=400, detail="Transaction already processed")

    active = {a.address: a for a in get_active_addresses(db, chain)}
    legacy = settings.PAYMENT_ADDRESS_TRON if chain == "TRON" else settings.PAYMENT_ADDRESS_ETH
    if legacy:
        active.setdefault(legacy, None)
    if not active:
        raise HTTPException(status_code=503, detail="Deposit pool not configured")

    verification = None
    matched_dest = None
    for dest in active:
        v = await ChainService.verify_tx(chain, tx_hash, dest)
        if v.get("verified"):
            verification = v
            matched_dest = dest
            break
    if not verification:
        raise HTTPException(status_code=400, detail="Verification failed: not to active deposit address")

    amount = float(verification.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid transfer amount")

    product = payment.product or "balance"
    required = None
    if product in settings.PACKAGES:
        required = settings.PACKAGES[product]["price"]
    elif product in settings.API_PLANS:
        required = settings.API_PLANS[product]["price"]
    if required is not None and amount + 0.01 < required:
        raise HTTPException(status_code=400, detail=f"Amount {amount} below product price {required}")

    try:
        result = await verify_and_fulfill_crypto_payment(
            db,
            current_user=current_user,
            chain=chain,
            tx_hash=tx_hash,
            expected_dest=matched_dest,
            product=product,
            verification=verification,
        )
    except PaymentRejected as e:
        code = 402 if e.pending_review else 403
        raise HTTPException(status_code=code, detail=str(e))

    if product in settings.API_PLANS:
        raw_key = _issue_api_key(db, current_user, product)
        return {
            "status": "success",
            "new_balance": result["new_balance"],
            "check_credits": result["check_credits"],
            "verified": True,
            "amount": result["amount"],
            "currency": result["currency"],
            "product": product,
            "referrer_bonus": result.get("referrer_bonus", 0),
            "screening": result.get("screening"),
            # Ключ показывается ОДИН раз — пользователь должен сохранить его сейчас
            "api_key": raw_key,
            "api_key_note": "Save this key now — it will not be shown again. Use as X-API-Key header.",
        }

    return {
        "status": "success",
        "new_balance": result["new_balance"],
        "check_credits": result["check_credits"],
        "verified": True,
        "amount": result["amount"],
        "currency": result["currency"],
        "product": product,
        "referrer_bonus": result.get("referrer_bonus", 0),
        "screening": result.get("screening"),
    }


@router.post("/dispute")
def create_dispute(
    body: DisputeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создать оспаривание результата AML-проверки."""
    d = Dispute(
        user_id=current_user.id,
        check_id=body.check_id,
        address=body.address,
        chain=body.chain.upper(),
        message=body.message[:2000],
        status="open",
    )
    db.add(d)
    db.commit()
    return {"status": "ok", "id": d.id}


@router.post("/api-keys")
def create_api_key(
    plan: str = "api_starter",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создать API-ключ списав стоимость плана с баланса (beta)."""
    if plan not in settings.API_PLANS:
        raise HTTPException(status_code=400, detail="Unknown API plan")
    price = settings.API_PLANS[plan]["price"]
    if (current_user.balance or 0) < price:
        raise HTTPException(status_code=402, detail="Insufficient balance for API plan")
    current_user.balance = round(current_user.balance - price, 4)
    raw = _issue_api_key(db, current_user, plan)
    db.add(Payment(
        user_id=current_user.id,
        amount=price,
        currency="USD",
        status="completed",
        tx_hash=f"api_key_{secrets.token_hex(6)}",
        product=plan,
    ))
    db.commit()
    return {"api_key": raw, "plan": plan, "quota": settings.API_PLANS[plan]["quota"]}
