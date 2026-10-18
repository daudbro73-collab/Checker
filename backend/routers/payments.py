"""Unified payments API — crypto via 10-address deposit pool."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from database import Payment, User
from dependencies import get_current_user, get_db
from services.chain import ChainService
from services.deposit_pool import assign_deposit_address, get_active_addresses, pool_status, sync_all_pools
from services.payment_fulfill import PaymentRejected, verify_and_fulfill_crypto_payment
from services.payments import get_provider, list_providers, product_catalog, product_price_usd

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()


class CreatePaymentBody(BaseModel):
    product: str = "single_check"
    method: str = "crypto_usdt"
    chain: str = "TRON"
    amount_usd: Optional[float] = None


class ConfirmPaymentBody(BaseModel):
    method: str = "crypto_usdt"
    product: str = "single_check"
    tx_hash: str = ""
    chain: str = "TRON"


def _resolve_deposit(db: Session, chain: str, user_id: Optional[int] = None):
    """Pick one of active pool addresses for this checkout and reserve slot for user."""
    chain = chain.upper()
    dep = assign_deposit_address(db, chain, user_id=user_id, reservation_seconds=300)
    if dep:
        return dep
    # Legacy fallbacks
    legacy_map = {
        "TRON": settings.PAYMENT_ADDRESS_TRON,
        "ETH": settings.PAYMENT_ADDRESS_ETH,
        "BSC": getattr(settings, "PAYMENT_ADDRESS_BSC", "") or settings.PAYMENT_ADDRESS_ETH,
        "SOL": getattr(settings, "PAYMENT_ADDRESS_SOL", ""),
    }
    legacy = legacy_map.get(chain)
    if legacy:
        return type("LegacyDep", (), {"address": legacy, "id": None, "slot": None, "reserved_by_user_id": None})()
    return None


def _active_address_map(db: Session, chain: str) -> dict:
    active = get_active_addresses(db, chain)
    return {a.address: a for a in active}


@router.get("/methods")
def payment_methods(db: Session = Depends(get_db)):
    sync_all_pools(db)
    pool = pool_status(db)
    return {
        "methods": list_providers(),
        "products": product_catalog(),
        "price_per_check": settings.PRICE_PER_CHECK,
        "usd_rub_rate": settings.USD_RUB_RATE,
        "trial_checks_per_day": settings.FREE_CHECKS_PER_DAY,
        "deposit_pool_size": settings.DEPOSIT_POOL_SIZE,
        "deposit_pool": pool,
        "note": "USDT → rotating deposit pool. Sender screened before credit. Daily pre-sweep screen.",
    }


@router.get("/pool")
def deposit_pool_view(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")
    sync_all_pools(db)
    return pool_status(db)


@router.post("/pool/sync")
def deposit_pool_sync(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")
    return {"synced": sync_all_pools(db), "pool": pool_status(db)}


@router.post("/pool/screen")
async def deposit_pool_screen_now(
    current_user: User = Depends(get_current_user),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")
    from services.treasury_worker import run_daily_treasury_screen
    return await run_daily_treasury_screen()


@router.post("/create")
async def create_payment(
    body: CreatePaymentBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        provider = get_provider(body.method)
    except KeyError:
        raise HTTPException(status_code=400, detail="Unknown payment method")

    chain = (body.chain or "TRON").upper()
    product = body.product or "single_check"
    try:
        if product == "balance" and body.amount_usd:
            amount = float(body.amount_usd)
        else:
            amount = product_price_usd(product if product != "balance" else "single_check")
            if product == "balance":
                amount = body.amount_usd or settings.PRICE_PER_CHECK
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    meta = {
        "chain": chain,
        "usd_rub_rate": settings.USD_RUB_RATE,
    }

    if body.method == "crypto_usdt":
        dep = _resolve_deposit(db, chain, user_id=current_user.id)
        if not dep or not dep.address:
            raise HTTPException(status_code=503, detail="Deposit pool not configured for this chain")
        res_until_str = None
        if getattr(dep, "reserved_until", None):
            res_until_str = dep.reserved_until.isoformat()
        meta.update({
            "deposit_address": dep.address,
            "deposit_slot": getattr(dep, "slot", None),
            "deposit_address_id": getattr(dep, "id", None),
            "expires_in": 300,
            "reserved_until": res_until_str,
        })

    session = await provider.create_checkout(
        user_id=current_user.id,
        product=product,
        amount_usd=amount,
        meta=meta,
    )

    return {
        "provider": session.provider,
        "status": session.status,
        "amount": session.amount,
        "currency": session.currency,
        "product": session.product,
        "instructions": session.instructions,
        "message": session.message,
        "enabled": provider.enabled and session.status != "coming_soon",
    }


@router.post("/confirm")
async def confirm_payment(
    body: ConfirmPaymentBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.method != "crypto_usdt":
        raise HTTPException(status_code=501, detail=f"Confirm for '{body.method}' not live yet")

    chain = (body.chain or "TRON").upper()
    tx_hash = (body.tx_hash or "").strip()
    if not tx_hash:
        raise HTTPException(status_code=400, detail="Transaction hash is required")
    if tx_hash.startswith("sim_"):
        raise HTTPException(status_code=400, detail="Simulation payments are disabled")
    if db.query(Payment).filter(Payment.tx_hash == tx_hash).first():
        raise HTTPException(status_code=400, detail="Transaction already processed")

    # Try each active pool address — tx must hit one of them
    active_map = _active_address_map(db, chain)
    legacy_map = {
        "TRON": settings.PAYMENT_ADDRESS_TRON,
        "ETH": settings.PAYMENT_ADDRESS_ETH,
        "BSC": getattr(settings, "PAYMENT_ADDRESS_BSC", "") or settings.PAYMENT_ADDRESS_ETH,
        "SOL": getattr(settings, "PAYMENT_ADDRESS_SOL", ""),
    }
    legacy = legacy_map.get(chain)
    if legacy:
        active_map.setdefault(legacy, None)

    verification = None
    matched_dest = None
    for dest in active_map:
        v = await ChainService.verify_tx(chain, tx_hash, dest)
        if v.get("verified"):
            verification = v
            matched_dest = dest
            break

    if not verification:
        raise HTTPException(status_code=400, detail="Verification failed: payment not to an active deposit address")

    # Security: Anti-Frontrunning slot ownership check
    matched_dep = active_map.get(matched_dest)
    if matched_dep and getattr(matched_dep, "reserved_by_user_id", None):
        res_user_id = matched_dep.reserved_by_user_id
        res_until = getattr(matched_dep, "reserved_until", None)
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if res_user_id != current_user.id and res_until and res_until > (now - timedelta(seconds=60)):
            raise HTTPException(
                status_code=403,
                detail="Security alert: This deposit slot was reserved by another user. Front-running rejected."
            )

    amount = float(verification.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid transfer amount")

    product = body.product or "balance"
    try:
        required = product_price_usd(product) if product != "balance" else None
    except KeyError:
        required = None
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

    result["method"] = "crypto_usdt"
    return result


@router.post("/webhook/{provider_id}")
async def payment_webhook(
    provider_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Webhook receiver for payment providers.
    Validates X-Webhook-Signature (HMAC-SHA256 of raw body with WEBHOOK_SECRET).
    """
    import hashlib
    import hmac as _hmac
    import os

    webhook_secret = os.getenv("WEBHOOK_SECRET", "")
    if webhook_secret:
        signature = request.headers.get("X-Webhook-Signature", "")
        body = await request.body()
        expected = _hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not _hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    else:
        # No secret configured — log warning, accept only known providers
        import logging
        logging.getLogger(__name__).warning(
            "WEBHOOK_SECRET not set — webhook endpoint is unauthenticated. "
            "Set WEBHOOK_SECRET in .env for production."
        )

    known_providers = ("sbp", "card_rub", "yookassa", "tbank")
    if provider_id not in known_providers:
        raise HTTPException(status_code=404, detail="Unknown provider webhook")

    # Stubs — implement provider-specific logic here
    return {"status": "accepted", "provider": provider_id}
