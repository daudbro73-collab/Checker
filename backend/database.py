import os
from datetime import datetime
from pathlib import Path

# Load .env before engine creation
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, backref

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aml.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=True)
    username = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    check_credits = Column(Integer, default=0)  # prepaid package checks
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    referral_code = Column(String, unique=True, index=True, nullable=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    subscription_checks_left = Column(Integer, default=0)
    free_check_used = Column(Boolean, default=False)

    payments = relationship("Payment", back_populates="user")
    checks = relationship("CheckHistory", back_populates="user")
    referrals = relationship("User", backref=backref("referrer", remote_side=[id]))
    api_keys = relationship("ApiKey", back_populates="user")
    monitors = relationship("AddressMonitor", back_populates="user")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    currency = Column(String, default="USDT")
    status = Column(String, default="pending")
    tx_hash = Column(String, unique=True, index=True, nullable=True)
    product = Column(String, nullable=True)  # check_credit, pack_*, otc_sub, api_*
    deposit_address_id = Column(Integer, ForeignKey("deposit_addresses.id"), nullable=True)
    sender_address = Column(String, nullable=True)
    screening_status = Column(String, nullable=True)  # pass | review | reject | pending
    screening_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payments")
    deposit_address = relationship("DepositAddress", back_populates="payments")


class DepositAddress(Base):
    """Rotating pool of deposit wallets — always DEPOSIT_POOL_SIZE active per chain."""
    __tablename__ = "deposit_addresses"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, index=True)
    chain = Column(String, index=True)  # TRON | ETH
    status = Column(String, default="standby", index=True)  # active | standby | quarantine | retired
    slot = Column(Integer, nullable=True)  # 1..N for active slots
    balance_usdt = Column(Float, default=0.0)
    reserved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reserved_until = Column(DateTime, nullable=True)
    last_assigned_at = Column(DateTime, nullable=True)
    last_screened_at = Column(DateTime, nullable=True)
    last_sweep_at = Column(DateTime, nullable=True)
    quarantine_reason = Column(Text, nullable=True)
    quarantined_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = relationship("Payment", back_populates="deposit_address")
    sweep_logs = relationship("DepositSweepLog", back_populates="deposit_address")


class DepositSweepLog(Base):
    """Daily pre-sweep screening audit trail."""
    __tablename__ = "deposit_sweep_logs"

    id = Column(Integer, primary_key=True, index=True)
    deposit_address_id = Column(Integer, ForeignKey("deposit_addresses.id"))
    chain = Column(String)
    balance_usdt = Column(Float, default=0.0)
    senders_json = Column(Text, nullable=True)
    screening_result = Column(String)  # pass | quarantine
    action = Column(String)  # sweep_ready | quarantined | no_balance | manual_sweep
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    deposit_address = relationship("DepositAddress", back_populates="sweep_logs")


class CheckHistory(Base):
    __tablename__ = "check_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    address = Column(String, index=True)
    chain = Column(String)
    risk_score = Column(Integer)
    risk_level = Column(String)
    payload_json = Column(Text, nullable=True)  # full audit trail
    list_versions_json = Column(Text, nullable=True)
    is_free = Column(Boolean, default=False)
    share_token = Column(String, unique=True, index=True, nullable=True)
    share_expires_at = Column(DateTime, nullable=True)
    report_id = Column(String, unique=True, index=True, nullable=True)
    sha256_hash = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="checks")


class SanctionedAddress(Base):
    __tablename__ = "sanctioned_addresses"

    address = Column(String, primary_key=True, index=True)
    currency = Column(String, index=True)
    source = Column(String)
    category = Column(String)
    entity_name = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    listed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class RiskLabel(Base):
    """Non-sanctions risk labels (hacks, scam, phishing, ransomware)."""
    __tablename__ = "risk_labels"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, index=True)
    chain = Column(String, nullable=True)
    source = Column(String)
    category = Column(String)
    label = Column(String, nullable=True)
    confidence = Column(String, default="medium")  # high/medium/low
    source_url = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ListSnapshot(Base):
    """Version stamp for synced data sources."""
    __tablename__ = "list_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)
    version = Column(String)
    record_count = Column(Integer, default=0)
    synced_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    check_id = Column(Integer, ForeignKey("check_history.id"), nullable=True)
    address = Column(String)
    chain = Column(String)
    message = Column(Text)
    status = Column(String, default="open")  # open, reviewing, resolved
    created_at = Column(DateTime, default=datetime.utcnow)


class AddressMonitor(Base):
    __tablename__ = "address_monitors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    address = Column(String, index=True)
    chain = Column(String)
    label = Column(String, nullable=True)  # address book name, e.g. "OTC counterparty"
    last_score = Column(Integer, nullable=True)
    last_level = Column(String, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    notify_telegram = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="monitors")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    key_hash = Column(String, unique=True, index=True)
    key_prefix = Column(String)
    plan = Column(String, default="api_starter")
    quota_monthly = Column(Integer, default=500)
    used_this_month = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")


def _migrate_sqlite_columns():
    """Add new columns to existing SQLite tables without Alembic."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    import sqlalchemy as sa
    from sqlalchemy import inspect, text

    new_payment_cols = {
        "deposit_address_id": "INTEGER",
        "sender_address": "VARCHAR",
        "screening_status": "VARCHAR",
        "screening_detail": "TEXT",
    }
    new_monitor_cols = {
        "label": "VARCHAR",
        "last_checked_at": "DATETIME",
    }
    new_check_cols = {
        "report_id": "VARCHAR",
        "sha256_hash": "VARCHAR",
    }
    new_deposit_cols = {
        "reserved_by_user_id": "INTEGER",
        "reserved_until": "DATETIME",
    }
    with engine.connect() as conn:
        insp = inspect(engine)
        if "payments" in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns("payments")}
            for col, typ in new_payment_cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE payments ADD COLUMN {col} {typ}"))
        if "address_monitors" in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns("address_monitors")}
            for col, typ in new_monitor_cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE address_monitors ADD COLUMN {col} {typ}"))
        if "check_history" in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns("check_history")}
            for col, typ in new_check_cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE check_history ADD COLUMN {col} {typ}"))
        if "deposit_addresses" in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns("deposit_addresses")}
            for col, typ in new_deposit_cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE deposit_addresses ADD COLUMN {col} {typ}"))
        conn.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns()
