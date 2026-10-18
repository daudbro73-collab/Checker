import httpx
import asyncio
from datetime import datetime
import json
import time

async def analyze_wallet_optimized(address: str, limit_tx: int = 1000):
    """
    Optimized analysis: Fetches the last N transactions to provide a quick turnover snapshot.
    Avoids 'torturing' the API with deep historical crawls.
    """
    base_url = "https://api.trongrid.io/v1/accounts"
    
    print(f"\n🚀 Starting OPTIMIZED analysis for: {address}")
    print(f"🎯 Target: Last {limit_tx} TRC20 transactions (USDT)")
    
    txs = []
    page_limit = 200 
    fingerprint = None
    
    async with httpx.AsyncClient() as client:
        while len(txs) < limit_tx:
            url = f"{base_url}/{address}/transactions/trc20"
            params = {"limit": page_limit, "only_confirmed": "true"}
            if fingerprint:
                params["fingerprint"] = fingerprint
            
            try:
                start_time = time.time()
                resp = await client.get(url, params=params, timeout=10.0)
                
                if resp.status_code == 429:
                    print("⚠️  API Rate Limit hit. Pausing briefly...")
                    await asyncio.sleep(2)
                    continue
                    
                data = resp.json()
                batch = data.get("data", [])
                
                if not batch:
                    break
                
                # Filter for USDT only to save processing time later
                # USDT Contract: TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
                usdt_batch = [
                    tx for tx in batch 
                    if tx.get("token_info", {}).get("symbol") == "USDT" 
                    or tx.get("token_info", {}).get("address") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
                ]
                
                txs.extend(usdt_batch)
                
                # Progress update
                print(f"✅ Fetched {len(batch)} txs ({len(usdt_batch)} USDT). Total: {len(txs)}/{limit_tx}")

                fingerprint = data.get("meta", {}).get("fingerprint")
                if not fingerprint or len(txs) >= limit_tx:
                    break
                
            except Exception as e:
                print(f"❌ Error: {e}")
                break
    
    # Trim to limit
    txs = txs[:limit_tx]
    
    if not txs:
        print("No USDT transactions found in the recent history.")
        return

    # --- Analysis ---
    print("\n📊 Calculating Statistics...")
    
    total_in = 0.0
    total_out = 0.0
    count_in = 0
    count_out = 0
    
    first_tx_time = txs[-1].get("block_timestamp", 0)
    last_tx_time = txs[0].get("block_timestamp", 0)
    
    date_start = datetime.fromtimestamp(first_tx_time/1000)
    date_end = datetime.fromtimestamp(last_tx_time/1000)
    
    for tx in txs:
        token_info = tx.get("token_info", {})
        decimals = token_info.get("decimals", 6)
        
        try:
            amount = float(tx.get("value", "0")) / (10 ** decimals)
        except:
            amount = 0.0
            
        sender = tx.get("from")
        if sender == address:
            total_out += amount
            count_out += 1
        else:
            total_in += amount
            count_in += 1

    # Time delta in days
    delta = (last_tx_time - first_tx_time) / 1000 / 86400
    if delta < 1:
        delta = 1 # Avoid division by zero
        
    avg_daily_in = total_in / delta
    avg_daily_out = total_out / delta

    # --- Report Output ---
    print("\n" + "="*60)
    print(f"💎 USDT WALLET SNAPSHOT REPORT")
    print(f"Address: {address}")
    print("="*60)
    print(f"📅 Period: {date_start}  -->  {date_end} ({delta:.1f} days)")
    print("-" * 60)
    print(f"📥 TOTAL INCOMING:  {total_in:,.2f} USDT ({count_in} txs)")
    print(f"📤 TOTAL OUTGOING:  {total_out:,.2f} USDT ({count_out} txs)")
    print(f"📈 NET FLOW:        {total_in - total_out:,.2f} USDT")
    print("-" * 60)
    print(f"⚡ Velocity (In):   {avg_daily_in:,.2f} USDT/day")
    print(f"⚡ Velocity (Out):  {avg_daily_out:,.2f} USDT/day")
    print("="*60)

if __name__ == "__main__":
    # Using the same address
    asyncio.run(analyze_wallet_optimized("TU4vEruvZwLLkSfV9bNw12EJTPvNr7Pvaa", limit_tx=1000))
