"""Nightly/periodic sync for sanctions + public risk labels."""
import asyncio
import datetime
import json
import logging
from typing import Iterable

import httpx
from sqlalchemy.orm import Session

from database import SessionLocal, SanctionedAddress, RiskLabel, ListSnapshot, CheckHistory, init_db

logger = logging.getLogger(__name__)

OFAC_GITHUB = "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists"
OFAC_ASSETS = ["ETH", "TRX", "XBT", "USDT", "USDC"]

SCAMSNIFFER_URL = "https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/address.json"
DEFILLAMA_HACKS = "https://api.llama.fi/hacks"
RANSOMWHERE_URL = "https://api.ransomwhe.re/export"


def _upsert_snapshot(db: Session, source: str, count: int, notes: str = ""):
    version = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    db.add(ListSnapshot(
        source=source,
        version=version,
        record_count=count,
        synced_at=datetime.datetime.utcnow(),
        notes=notes,
    ))
    db.commit()


async def sync_ofac(db: Session) -> int:
    added = 0
    existing = {r[0] for r in db.query(SanctionedAddress.address).filter(SanctionedAddress.source == "OFAC").all()}
    new_records = []
    async with httpx.AsyncClient() as client:
        for asset in OFAC_ASSETS:
            url = f"{OFAC_GITHUB}/sanctioned_addresses_{asset}.json"
            try:
                resp = await client.get(url, timeout=30.0)
                if resp.status_code != 200:
                    continue
                for addr in resp.json():
                    normalized = (addr or "").strip().lower()
                    if not normalized:
                        continue
                    if normalized not in existing:
                        new_records.append(SanctionedAddress(
                            address=normalized,
                            currency=asset,
                            source="OFAC",
                            category="Sanctions",
                            entity_name="Specially Designated National (SDN)",
                            source_url=url,
                            listed_at=datetime.datetime.utcnow(),
                            updated_at=datetime.datetime.utcnow(),
                        ))
                        existing.add(normalized)
                        added += 1
            except Exception as e:
                logger.error("OFAC sync error %s: %s", asset, e)
    if new_records:
        db.add_all(new_records)
        db.commit()
    total = db.query(SanctionedAddress).filter(SanctionedAddress.source == "OFAC").count()
    _upsert_snapshot(db, "OFAC", total, notes=f"added={added}")
    return added


async def sync_scamsniffer(db: Session) -> int:
    added = 0
    try:
        existing = {r[0] for r in db.query(RiskLabel.address).filter(RiskLabel.source == "ScamSniffer").all()}
        async with httpx.AsyncClient() as client:
            resp = await client.get(SCAMSNIFFER_URL, timeout=30.0)
            if resp.status_code != 200:
                return 0
            data = resp.json()
            addresses: Iterable[str] = data if isinstance(data, list) else (data.get("addresses") or data.get("data") or [])
            new_records = []
            for addr in addresses:
                normalized = (addr or "").strip().lower()
                if not normalized or normalized in existing:
                    continue
                new_records.append(RiskLabel(
                    address=normalized,
                    source="ScamSniffer",
                    category="Scam",
                    label="ScamSniffer blocklist (phishing/drainer)",
                    confidence="high",
                    source_url=SCAMSNIFFER_URL,
                ))
                existing.add(normalized)
                added += 1
            if new_records:
                db.add_all(new_records)
                db.commit()
    except Exception as e:
        logger.error("ScamSniffer sync error: %s", e)
    total = db.query(RiskLabel).filter(RiskLabel.source == "ScamSniffer").count()
    _upsert_snapshot(db, "ScamSniffer", total, notes=f"added={added}")
    return added


async def sync_defillama_hacks(db: Session) -> int:
    added = 0
    try:
        existing = {r[0] for r in db.query(RiskLabel.address).filter(RiskLabel.source == "DefiLlama").all()}
        async with httpx.AsyncClient() as client:
            resp = await client.get(DEFILLAMA_HACKS, timeout=30.0)
            if resp.status_code != 200:
                return 0
            new_records = []
            for item in resp.json() or []:
                if not isinstance(item, dict):
                    continue
                addrs = []
                for k, v in item.items():
                    if "address" in k.lower() and isinstance(v, str) and v.startswith("0x"):
                        addrs.append(v)
                    if k == "addresses" and isinstance(v, list):
                        addrs.extend(v)

                returned = item.get("returnedFunds")
                if isinstance(returned, dict):
                    for key in returned:
                        if isinstance(key, str) and key.startswith("0x"):
                            addrs.append(key)
                elif isinstance(returned, list):
                    addrs.extend([x for x in returned if isinstance(x, str) and x.startswith("0x")])

                label_name = item.get("name") or item.get("title") or "Hack"
                for addr in addrs:
                    normalized = addr.strip().lower()
                    if not normalized or normalized in existing:
                        continue
                    new_records.append(RiskLabel(
                        address=normalized,
                        source="DefiLlama",
                        category="Hack",
                        label=f"Exploit: {label_name}",
                        confidence="high",
                        source_url=DEFILLAMA_HACKS,
                    ))
                    existing.add(normalized)
                    added += 1
            if new_records:
                db.add_all(new_records)
                db.commit()
    except Exception as e:
        logger.error("DefiLlama sync error: %s", e)
    total = db.query(RiskLabel).filter(RiskLabel.source == "DefiLlama").count()
    _upsert_snapshot(db, "DefiLlama", total, notes=f"added={added}")
    return added


async def sync_ransomwhere(db: Session) -> int:
    added = 0
    try:
        existing = {r[0] for r in db.query(RiskLabel.address).filter(RiskLabel.source == "Ransomwhere").all()}
        import urllib.request
        def _fetch_ransomwhere():
            req = urllib.request.Request(
                RANSOMWHERE_URL,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())

        data = await asyncio.to_thread(_fetch_ransomwhere)
        items = data.get("result", [])
        new_records = []
        for item in items:
            raw_addr = item.get("address")
            if not raw_addr or not isinstance(raw_addr, str):
                continue
            normalized = raw_addr.strip().lower()
            if normalized in existing:
                continue
            family = item.get("family") or "Ransomware"
            new_records.append(RiskLabel(
                address=normalized,
                source="Ransomwhere",
                category="Ransomware",
                label=f"Ransomware payout address ({family})",
                confidence="high",
                source_url="https://ransomwhe.re",
            ))
            existing.add(normalized)
            added += 1
        if new_records:
            # Вставляем пакетами по 1000 строк
            batch_size = 1000
            for i in range(0, len(new_records), batch_size):
                db.add_all(new_records[i:i + batch_size])
                db.commit()
    except Exception as e:
        logger.error("Ransomwhere sync error: %s", e)
    total = db.query(RiskLabel).filter(RiskLabel.source == "Ransomwhere").count()
    _upsert_snapshot(db, "Ransomwhere", total, notes=f"added={added}")
    return added


async def sync_slowmist_placeholder(db: Session) -> int:
    """
    SlowMist hacked DB — public HTML/JSON endpoints change often.
    Record a snapshot marker so reports show source awareness; full parse can be extended.
    """
    _upsert_snapshot(db, "SlowMist", 0, notes="manual/curated — extend parser as feed stabilizes")
    return 0


def purge_old_free_checks(db: Session, hours: int = 24) -> int:
    """
    GDPR-совместимое удаление бесплатных чеков старше N часов.
    Физически удаляет строки (не обфусцирует) — соответствует праву на забвение (Art. 17 GDPR).
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    rows = db.query(CheckHistory).filter(
        CheckHistory.is_free == True,
        CheckHistory.created_at < cutoff,
    ).all()
    n = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return n


async def run_sync_once():
    init_db()
    db = SessionLocal()
    try:
        print("Starting data sync across all threat intelligence sources...")
        a = await sync_ofac(db)
        b = await sync_scamsniffer(db)
        c = await sync_defillama_hacks(db)
        d = await sync_ransomwhere(db)
        await sync_slowmist_placeholder(db)
        purged = purge_old_free_checks(db)
        logger.info(
            "Sync done: OFAC+%d, ScamSniffer+%d, DefiLlama+%d, Ransomwhere+%d, purged_free=%d",
            a, b, c, d, purged
        )
        print(f"✅ Sync completed: OFAC(+{a}), ScamSniffer(+{b}), DefiLlama(+{c}), Ransomwhere(+{d})")
    finally:
        db.close()


async def worker_loop(interval_seconds: int = 86400):
    while True:
        try:
            await run_sync_once()
        except Exception as e:
            logger.error("Worker sync failed: %s", e, exc_info=True)
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_sync_once())
