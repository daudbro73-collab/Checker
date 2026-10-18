"""Billing helpers: charge after success, packages, subscriptions."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import get_settings
from database import User

settings = get_settings()


def _subscription_active(user: User) -> bool:
    if not user.subscription_expires_at:
        return False
    return user.subscription_expires_at > datetime.utcnow() and (user.subscription_checks_left or 0) > 0


def can_afford_check(user: User) -> bool:
    if not getattr(user, "free_check_used", True):
        return True
    if (user.check_credits or 0) > 0:
        return True
    if _subscription_active(user):
        return True
    return (user.balance or 0) >= settings.PRICE_PER_CHECK


def charge_for_check(db: Session, user: User) -> str:
    """
    Deduct one check. Prefer free trial, package credits, then subscription, then balance.
    Returns billing method used.
    Must be called AFTER successful analysis.
    """
    locked_user = db.query(User).filter(User.id == user.id).with_for_update().first()
    if not locked_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not getattr(locked_user, "free_check_used", True):
        locked_user.free_check_used = True
        db.add(locked_user)
        db.commit()
        return "free_trial"

    if (locked_user.check_credits or 0) > 0:
        locked_user.check_credits -= 1
        db.add(locked_user)
        db.commit()
        return "credit"

    if _subscription_active(locked_user):
        locked_user.subscription_checks_left -= 1
        db.add(locked_user)
        db.commit()
        return "subscription"

    if (locked_user.balance or 0) < settings.PRICE_PER_CHECK:
        raise HTTPException(status_code=402, detail="Insufficient balance. Please top up.")

    locked_user.balance = round(locked_user.balance - settings.PRICE_PER_CHECK, 4)
    db.add(locked_user)
    db.commit()
    return "balance"


def apply_package(db: Session, user: User, package_id: str):
    pack = settings.PACKAGES.get(package_id)
    if not pack:
        raise HTTPException(status_code=400, detail="Unknown package")
    user.check_credits = (user.check_credits or 0) + pack["checks"]
    db.add(user)
    db.commit()
    return pack


def apply_otc_subscription(db: Session, user: User):
    sub = settings.OTC_SUBSCRIPTION
    user.subscription_expires_at = datetime.utcnow() + timedelta(days=sub["days"])
    user.subscription_checks_left = sub["checks_per_month"]
    db.add(user)
    db.commit()
    return sub


def grant_referral_check_bonus(db: Session, user: User, referrer: Optional[User]):
    bonus = settings.REFERRAL_CHECK_BONUS
    if bonus <= 0:
        return
    user.balance = round((user.balance or 0) + bonus, 4)
    if referrer:
        referrer.balance = round((referrer.balance or 0) + bonus, 4)
        db.add(referrer)
    db.add(user)
    db.commit()
