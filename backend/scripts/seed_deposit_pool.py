#!/usr/bin/env python3
"""Sync deposit pool from env. Start with 1 address via PAYMENT_ADDRESS_TRON."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from database import SessionLocal, init_db
from services.deposit_keys import can_auto_generate
from services.deposit_pool import pool_status, sync_all_pools


def main():
    init_db()
    settings = get_settings()
    db = SessionLocal()
    try:
        reports = sync_all_pools(db)
        status = pool_status(db)
        print("=== Deposit pool sync ===")
        print(f"target active size: {settings.DEPOSIT_POOL_SIZE}")
        print(f"auto-generate: {can_auto_generate()}")
        for r in reports:
            print(r)
        if not reports:
            print("No addresses. Set PAYMENT_ADDRESS_TRON or DEPOSIT_POOL_TRON in .env")
        print("=== Pool status ===")
        for chain, info in status.items():
            active = [a for a in info["addresses"] if a["status"] == "active"]
            print(f"{chain}: {len(active)}/{info['target_active']} active, treasury={info.get('treasury') or '(not set)'}")
            for a in active:
                print(f"  slot {a['slot']}: {a['address']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
