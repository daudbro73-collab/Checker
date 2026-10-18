"""Telegram Stars fulfillment and credit engine."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from config import get_settings
from database import Payment, User
from services.billing import apply_package

logger = logging.getLogger(__name__)
settings = get_settings()

STARS_PER_USD = 50.0


def stars_to_usd(stars: int) -> float:
    return round(float(stars) / STARS_PER_USD, 2)


def usd_to_stars(usd: float) -> int:
    return max(1, int(round(usd * STARS_PER_USD)))


def fulfill_stars_payment(
    db: Session,
    *,
    user_id: int,
    product: str,
    stars_amount: int,
    telegram_charge_id: str,
    provider_charge_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Idempotently fulfills a Telegram Stars payment:
    1. Checks if payment with telegram_charge_id was already processed
    2. Applies package / subscription / single check credit / balance
    3. Pays referral bonus to referrer in USD equivalent
    4. Records completed Payment in DB
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error("fulfill_stars_payment: user_id %s not found", user_id)
        raise ValueError(f"User {user_id} not found")

    # 1. Проверка на повторную обработку (идемпотентность)
    existing = db.query(Payment).filter(Payment.tx_hash == telegram_charge_id).first()
    if existing:
        logger.info("Stars payment %s already fulfilled", telegram_charge_id)
        return {
            "status": "already_processed",
            "payment_id": existing.id,
            "product": existing.product,
            "stars": existing.amount,
            "new_balance": user.balance,
            "check_credits": user.check_credits or 0,
        }

    amount_usd = stars_to_usd(stars_amount)
    credits_added = 0

    # 2. Начисление товара
    if product in settings.PACKAGES:
        apply_package(db, user, product)
        credits_added = settings.PACKAGES[product]["checks"]
    elif product == "single_check":
        user.check_credits = (user.check_credits or 0) + 1
        credits_added = 1
        db.add(user)
    else:
        user.balance = round((user.balance or 0) + amount_usd, 4)
        db.add(user)

    # 3. Сохранение записи о платеже
    payment = Payment(
        user_id=user.id,
        amount=float(stars_amount),
        currency="XTR",
        status="completed",
        tx_hash=telegram_charge_id,
        product=product,
        screening_status="pass",
        screening_detail=f"Telegram Stars payment (provider_charge_id={provider_charge_id})",
    )
    db.add(payment)

    # 4. Реферальная программа (бонус в USD на баланс пригласителю)
    referrer_bonus = 0.0
    if user.referrer_id:
        referrer = db.query(User).filter(User.id == user.referrer_id).first()
        if referrer and settings.REFERRER_BONUS_RATE > 0:
            referrer_bonus = round(amount_usd * settings.REFERRER_BONUS_RATE, 2)
            if referrer_bonus > 0:
                referrer.balance = round((referrer.balance or 0) + referrer_bonus, 4)
                db.add(referrer)
                db.add(
                    Payment(
                        user_id=referrer.id,
                        amount=referrer_bonus,
                        currency="USD",
                        status="completed",
                        tx_hash=f"ref_stars_{telegram_charge_id}",
                        product="referral",
                    )
                )

    db.commit()
    db.refresh(user)

    logger.info(
        "Fulfilled Stars payment %s: user_id=%s, product=%s, stars=%s, credits_added=%s",
        telegram_charge_id,
        user.id,
        product,
        stars_amount,
        credits_added,
    )

    return {
        "status": "completed",
        "payment_id": payment.id,
        "product": product,
        "stars": stars_amount,
        "amount_usd": amount_usd,
        "credits_added": credits_added,
        "new_balance": user.balance,
        "check_credits": user.check_credits or 0,
        "referrer_bonus": referrer_bonus,
    }
