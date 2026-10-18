import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
from database import SessionLocal, CheckHistory, init_db
from services.report_v2 import compute_report_metadata

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


def test_compute_report_metadata_deterministic():
    now = datetime(2026, 9, 19, 14, 0, 0)
    addr = "TAaWbC862cHV9vXzbxoCJZNUuQLJLKh9dy"
    report_id_1, sha_1, exp_1 = compute_report_metadata("TRON", addr, 0, now)
    report_id_2, sha_2, exp_2 = compute_report_metadata("TRON", addr, 0, now)

    assert report_id_1 == report_id_2
    assert sha_1 == sha_2
    assert exp_1 == exp_2
    assert report_id_1.startswith("AG-20260919-TRO-")
    assert len(sha_1) == 64  # SHA-256 hex string


def test_verification_api_and_page():
    now = datetime.utcnow()
    addr = "0x71C836e4b360D4e2b0F8B7e4f9b2d86F3E48fA51"
    report_id, sha256_hash, exp_date = compute_report_metadata("ETH", addr, 15, now)

    # Insert test record into DB
    db = SessionLocal()
    try:
        db.query(CheckHistory).filter(CheckHistory.report_id == report_id).delete()
        db.commit()
        check = CheckHistory(
            address=addr,
            chain="ETH",
            risk_score=15,
            risk_level="SAFE",
            report_id=report_id,
            sha256_hash=sha256_hash,
            share_expires_at=now + timedelta(days=7),
            created_at=now,
        )
        db.add(check)
        db.commit()
    finally:
        db.close()

    # 1. Test JSON API verification by report_id
    resp_by_id = client.get(f"/api/v1/verify/{report_id}")
    assert resp_by_id.status_code == 200
    data = resp_by_id.json()
    assert data["verified"] is True
    assert data["status"] == "VALID"
    assert data["report_id"] == report_id
    assert data["sha256"] == sha256_hash
    assert data["address"] == addr
    assert data["risk_score"] == 15

    # 2. Test JSON API verification by SHA-256 hash
    resp_by_hash = client.get(f"/api/v1/verify/{sha256_hash}")
    assert resp_by_hash.status_code == 200
    assert resp_by_hash.json()["report_id"] == report_id

    # 3. Test HTML verification page
    page_resp = client.get(f"/p/{report_id}")
    assert page_resp.status_code == 200
    assert "ПОДЛИННОСТЬ ПОДТВЕРЖДЕНА" in page_resp.text
    assert report_id in page_resp.text
    assert sha256_hash in page_resp.text


def test_verification_not_found():
    fake_id = "AG-20999999-FAKE-000000"
    resp = client.get(f"/api/v1/verify/{fake_id}")
    assert resp.status_code == 404

    page_resp = client.get(f"/p/{fake_id}")
    assert page_resp.status_code == 404
    assert "Отчёт не найден или сфальсифицирован" in page_resp.text
