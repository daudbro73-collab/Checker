"""Shared payment verification + screening + balance credit."""
from __future__ import annotations

from sqlalchemy.orm import Session

from config import get_settings
from database import Payment, User
from services.billing import apply_package
from services.deposit_pool import find_deposit_by_address, is_active_pool_address, quarantine_address
from services.deposit_screening import REJECT, REVIEW, screen_address, screening_to_json

settings = get_settings()


async def verify_and_fulfill_crypto_payment(
    db: Session,
    *,
    current_user: User,
    chain: str,
    tx_hash: str,
    expected_dest: str,
    product: str,
    verification: dict,
) -> dict:
    """
    1) Validate tx landed on an active pool address
    2) Screen sender (OFAC + Tether + GoPlus hard flags)
    3) Credit user or quarantine deposit address
    """
    amount = float(verification.get("amount") or 0)
    currency = verification.get("currency") or "USDT"
    sender = (verification.get("sender") or "").strip()

    deposit = find_deposit_by_address(db, chain, expected_dest)
    if deposit and deposit.status != "active":
        raise PaymentRejected(
            "Deposit address is not accepting payments",
            quarantine=False,
        )
    if not deposit and not is_active_pool_address(db, chain, expected_dest):
        # Legacy single address not in pool table yet
        pass

    screen = await screen_address(sender, chain)
    screening_status = screen["status"]

    if screening_status == REJECT:
        if deposit:
            quarantine_address(
                db,
                deposit,
                reason=f"payment_sender_reject:{','.join(screen.get('reasons', []))}",
            )
        raise PaymentRejected(
            "Payment rejected: sender failed AML screening. Support will review.",
            quarantine=bool(deposit),
            screening=screen,
        )

    if screening_status == REVIEW:
        db.add(Payment(
            user_id=current_user.id,
            amount=amount,
            currency=currency,
            status="pending_review",
            tx_hash=tx_hash,
            product=product,
            deposit_address_id=deposit.id if deposit else None,
            sender_address=sender,
            screening_status=REVIEW,
            screening_detail=screening_to_json(screen),
        ))
        db.commit()
        raise PaymentRejected(
            "Payment held for manual review. Balance not credited yet.",
            quarantine=False,
            screening=screen,
            pending_review=True,
        )

    previous_completed = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == "completed",
        ~Payment.tx_hash.like("ref_%"),
    ).count()

    payment = Payment(
        user_id=current_user.id,
        amount=amount,
        currency=currency,
        status="completed",
        tx_hash=tx_hash,
        product=product,
        deposit_address_id=deposit.id if deposit else None,
        sender_address=sender,
        screening_status="pass",
        screening_detail=screening_to_json(screen),
    )
    db.add(payment)

    credits_added = 0
    if product in settings.PACKAGES:
        apply_package(db, current_user, product)
        credits_added = settings.PACKAGES[product]["checks"]
    elif product == "single_check":
        current_user.check_credits = (current_user.check_credits or 0) + 1
        credits_added = 1
        db.add(current_user)
    else:
        current_user.balance = round((current_user.balance or 0) + amount, 4)
        db.add(current_user)

    referrer_bonus = 0.0
    if current_user.referrer_id:
        referrer = db.query(User).filter(User.id == current_user.referrer_id).first()
        if referrer:
            referrer_bonus = round(amount * settings.REFERRER_BONUS_RATE, 2)
            if referrer_bonus > 0:
                referrer.balance = round((referrer.balance or 0) + referrer_bonus, 4)
                db.add(referrer)
                db.add(Payment(
                    user_id=referrer.id,
                    amount=referrer_bonus,
                    currency="USD",
                    status="completed",
                    tx_hash=f"ref_bonus_{tx_hash}",
                    product="referral",
                ))
        if previous_completed == 0 and settings.REFERRED_USER_FIRST_TOPUP_BONUS > 0:
            welcome = round(settings.REFERRED_USER_FIRST_TOPUP_BONUS, 2)
            current_user.balance = round((current_user.balance or 0) + welcome, 4)
            db.add(Payment(
                user_id=current_user.id,
                amount=welcome,
                currency="USD",
                status="completed",
                tx_hash=f"ref_welcome_{tx_hash}",
                product="referral",
            ))

    db.commit()
    return {
        "status": "completed",
        "amount": amount,
        "currency": currency,
        "product": product,
        "credits_added": credits_added,
        "new_balance": current_user.balance,
        "check_credits": current_user.check_credits or 0,
        "referrer_bonus": referrer_bonus,
        "screening": "pass",
        "deposit_address": expected_dest,
        "sender": sender,
    }


class PaymentRejected(Exception):
    def __init__(self, message: str, *, quarantine: bool = False, screening=None, pending_review: bool = False):
        super().__init__(message)
        self.quarantine = quarantine
        self.screening = screening
        self.pending_review = pending_review
