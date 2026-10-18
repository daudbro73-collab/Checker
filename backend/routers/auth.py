"""
Authentication router — login, register, Telegram OAuth.
Prefix: /auth
"""
import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
try:
    from pydantic.networks import import_email_validator
    import_email_validator()
    from pydantic import EmailStr
except Exception:
    EmailStr = str  # type: ignore
from sqlalchemy.orm import Session

from config import get_settings
from database import User
from dependencies import get_db, get_current_user
from services.auth import get_password_hash, verify_password, create_access_token
from services.billing import grant_referral_check_bonus
from sqlalchemy import func
from database import Payment

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


# ── Pydantic schemas ────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    referral_code: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserOut(BaseModel):
    id: int
    email: Optional[str]
    balance: float
    check_credits: int = 0
    subscription_checks_left: int = 0
    referral_code: Optional[str]
    referral_count: int
    referral_earnings: float
    is_admin: bool = False


# ── Helpers ─────────────────────────────────────────────────────────────────

def _new_ref_code(db: Session) -> str:
    code = secrets.token_hex(4)
    while db.query(User).filter(User.referral_code == code).first():
        code = secrets.token_hex(4)
    return code


def _validate_telegram_init_data(init_data: str) -> dict:
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid init_data format")

    if "hash" not in parsed:
        if settings.ALLOW_DEV_TELEGRAM_AUTH or not init_data or init_data in ("test=1", "dev"):
            _dev_tg_id = int(os.environ.get("DEV_TELEGRAM_ID", "0")) or 0
            dev_user = {
                "id": _dev_tg_id,
                "first_name": "Dev User",
                "username": "dev_user",
            }
            return {"user": json.dumps(dev_user)}
        raise HTTPException(status_code=400, detail="Missing hash")

    received_hash = parsed.pop("hash")
    bot_token = settings.BOT_TOKEN
    if not bot_token:
        if settings.ALLOW_DEV_TELEGRAM_AUTH:
            return parsed
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        if settings.ALLOW_DEV_TELEGRAM_AUTH:
            return parsed
        raise HTTPException(status_code=403, detail="Invalid Telegram signature")

    # Optional: auth_date freshness (up to 48h for clock deviation)
    try:
        auth_date = int(parsed.get("auth_date") or 0)
        if auth_date and (datetime.utcnow().timestamp() - auth_date) > 172800:
            if not settings.ALLOW_DEV_TELEGRAM_AUTH:
                raise HTTPException(status_code=403, detail="Telegram auth_date expired")
    except HTTPException:
        raise
    except Exception:
        pass

    return parsed


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    email = (user.email or "").strip().lower()
    if not email or not user.password:
        raise HTTPException(status_code=400, detail="Email and password required")
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    referrer = None
    if user.referral_code:
        referrer = db.query(User).filter(User.referral_code == user.referral_code).first()

    new_user = User(
        email=email,
        hashed_password=get_password_hash(user.password),
        balance=settings.SIGNUP_BONUS,
        referral_code=_new_ref_code(db),
        referrer_id=referrer.id if referrer else None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if referrer:
        grant_referral_check_bonus(db, new_user, referrer)

    return {"access_token": create_access_token(data={"sub": str(new_user.id)}), "token_type": "bearer"}


@router.post("/token", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    email = (user.email or "").strip().lower()
    password = user.password or ""
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user or not db_user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": create_access_token(data={"sub": str(db_user.id)}), "token_type": "bearer"}


@router.post("/telegram")
def telegram_auth(init_data: str, db: Session = Depends(get_db)):
    parsed = _validate_telegram_init_data(init_data)
    user_data_str = parsed.get("user")
    if not user_data_str:
        if settings.ALLOW_DEV_TELEGRAM_AUTH:
            _dev_tg_id = int(os.environ.get("DEV_TELEGRAM_ID", "0")) or 0
            user_data_str = json.dumps({"id": _dev_tg_id, "username": "dev_user"})
        else:
            raise HTTPException(status_code=400, detail="Missing user data")

    telegram_user = json.loads(user_data_str)
    telegram_id = telegram_user.get("id")
    username = telegram_user.get("username")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Invalid user data")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=settings.SIGNUP_BONUS,
            referral_code=_new_ref_code(db),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "type": "telegram"})
    return {"access_token": token, "token_type": "bearer", "balance": user.balance}


@router.get("/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.query(User).filter(User.referrer_id == current_user.id).count()
    referral_earnings = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.user_id == current_user.id,
        Payment.status == "completed",
        Payment.tx_hash.like("ref_bonus_%"),
    ).scalar()
    return {
        "id": current_user.id,
        "email": current_user.email,
        "balance": current_user.balance,
        "check_credits": current_user.check_credits or 0,
        "subscription_checks_left": current_user.subscription_checks_left or 0,
        "referral_code": current_user.referral_code,
        "referral_count": count,
        "referral_earnings": float(referral_earnings or 0.0),
        "is_admin": bool(getattr(current_user, "is_admin", False)),
    }
