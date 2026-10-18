import httpx
import asyncio
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.database import SessionLocal, SanctionedAddress, engine, init_db
except ImportError:
    from database import SessionLocal, SanctionedAddress, engine, init_db
import datetime

# Publicly maintained list of OFAC sanctioned addresses
BASE_URL = "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists"

SUPPORTED_ASSETS = ["ETH", "TRX", "XBT", "USDT", "USDC"]

async def fetch_and_update_sanctions():
    """
    Fetches the latest OFAC sanctioned addresses from the GitHub repo
    and updates the local database.
    """
    # Ensure DB is initialized
    init_db()
    
    db = SessionLocal()
    try:
        total_added = 0
        async with httpx.AsyncClient() as client:
            for asset in SUPPORTED_ASSETS:
                url = f"{BASE_URL}/sanctioned_addresses_{asset}.json"
                try:
                    print(f"Fetching {asset} sanctions list from {url}...")
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        addresses = resp.json()
                        count = 0
                        for addr in addresses:
                            # Normalize address
                            normalized_addr = addr.lower()
                            
                            # Check if exists
                            exists = db.query(SanctionedAddress).filter(SanctionedAddress.address == normalized_addr).first()
                            if not exists:
                                new_entry = SanctionedAddress(
                                    address=normalized_addr,
                                    currency=asset,
                                    source="OFAC",
                                    category="Sanctions",
                                    entity_name="Specially Designated National (SDN)",
                                    updated_at=datetime.datetime.utcnow()
                                )
                                db.add(new_entry)
                                count += 1
                        
                        db.commit()
                        print(f"Added {count} new {asset} addresses.")
                        total_added += count
                    else:
                        print(f"Failed to fetch {asset}: {resp.status_code}")
                except Exception as e:
                    print(f"Error processing {asset}: {e}")
                    
        return {"status": "success", "added": total_added}
    finally:
        db.close()

if __name__ == "__main__":
    # For manual running
    asyncio.run(fetch_and_update_sanctions())
