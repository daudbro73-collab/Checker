"""Create / reset local admin user."""
import os
import secrets
import sys

# Load .env if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from database import SessionLocal, User, init_db
from services.auth import get_password_hash

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@aml.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def main():
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if user:
            user.hashed_password = get_password_hash(ADMIN_PASSWORD)
            user.balance = 10000.0
            user.check_credits = 1000
            user.is_admin = True
            user.is_active = True
            if not user.referral_code:
                user.referral_code = secrets.token_hex(4)
            action = "updated"
        else:
            user = User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                balance=10000.0,
                check_credits=1000,
                is_admin=True,
                is_active=True,
                referral_code=secrets.token_hex(4),
            )
            db.add(user)
            action = "created"
        db.commit()
        db.refresh(user)
        print(f"Admin {action}: id={user.id} email={ADMIN_EMAIL} password={ADMIN_PASSWORD}")
        print(f"Balance=${user.balance} credits={user.check_credits} is_admin={user.is_admin}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
