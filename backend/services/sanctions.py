from database import SessionLocal, SanctionedAddress

# Manual overrides MUST include source + date + URL. No memory-only entries.
# Tornado Cash removed after OFAC delisting (Mar 2025).
MANUAL_BLACKLIST = {
    "0x53b6936513e738f44fb50d2b9476730c0ab3bfc1": {
        "source": "OFAC",
        "category": "Sanctions",
        "reason": "Lazarus Group (DPRK)",
        "source_url": "https://home.treasury.gov/policy-issues/financial-sanctions",
        "listed_at": "2022-04-14",
    },
    "0x8576acc5c05d6ce88f4e49bf65bdf0c62f91353c": {
        "source": "OFAC",
        "category": "Sanctions",
        "reason": "Garantex Exchange",
        "source_url": "https://home.treasury.gov/policy-issues/financial-sanctions",
        "listed_at": "2022-04-06",
    },
}


def check_sanctions(address: str):
    address_lower = (address or "").lower()

    if address_lower in MANUAL_BLACKLIST:
        data = MANUAL_BLACKLIST[address_lower]
        return {
            "is_sanctioned": True,
            "source": data.get("source"),
            "category": data.get("category"),
            "reason": data.get("reason"),
            "source_url": data.get("source_url"),
            "listed_at": data.get("listed_at"),
            "confidence": "high",
        }

    db = SessionLocal()
    try:
        record = db.query(SanctionedAddress).filter(SanctionedAddress.address == address_lower).first()
        if record:
            return {
                "is_sanctioned": True,
                "source": record.source,
                "category": record.category,
                "reason": record.entity_name,
                "source_url": getattr(record, "source_url", None),
                "listed_at": record.updated_at.isoformat() if record.updated_at else None,
                "confidence": "high",
            }
    except Exception as e:
        print(f"DB Error checking sanctions: {e}")
    finally:
        db.close()

    return {"is_sanctioned": False, "source": None, "category": None, "reason": None}


def bulk_check_sanctions(addresses):
    results = {}
    to_query = []

    for raw in addresses or []:
        addr = (raw or "").lower()
        if not addr:
            continue
        if addr in MANUAL_BLACKLIST:
            data = MANUAL_BLACKLIST[addr]
            results[addr] = {
                "is_sanctioned": True,
                "source": data.get("source"),
                "category": data.get("category"),
                "reason": data.get("reason"),
            }
        elif addr not in results:
            to_query.append(addr)

    if not to_query:
        return results

    db = SessionLocal()
    try:
        records = db.query(SanctionedAddress).filter(SanctionedAddress.address.in_(to_query)).all()
        found_set = set()
        for record in records:
            found_set.add(record.address)
            results[record.address] = {
                "is_sanctioned": True,
                "source": record.source,
                "category": record.category,
                "reason": record.entity_name,
            }
        for addr in to_query:
            if addr not in found_set:
                results[addr] = {"is_sanctioned": False, "source": None, "category": None, "reason": None}
    except Exception as e:
        print(f"DB Error in bulk check: {e}")
        for addr in to_query:
            if addr not in results:
                results[addr] = {"is_sanctioned": False, "source": None, "category": None, "reason": None}
    finally:
        db.close()

    return results
