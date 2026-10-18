import httpx
import asyncio
from datetime import datetime
import json
import time
import random

async def analyze_tron_2025(address: str):
    base_url = "https://api.trongrid.io/v1/accounts"
    
    # Time range for 2025 (in milliseconds)
    start_2025 = int(datetime(2025, 1, 1).timestamp() * 1000)
    end_2025 = int(datetime(2025, 12, 31, 23, 59, 59).timestamp() * 1000)
    
    print(f"Analyzing TRC20 transactions for {address} in 2025...")
    print(f"Range: {datetime.fromtimestamp(start_2025/1000)} to {datetime.fromtimestamp(end_2025/1000)}")
    
    txs = []
    limit = 200 
    fingerprint = None
    
    async with httpx.AsyncClient() as client:
        while True:
            url = f"{base_url}/{address}/transactions/trc20"
            params = {
                "limit": limit,
                "min_timestamp": start_2025,
                "max_timestamp": end_2025
            }
            if fingerprint:
                params["fingerprint"] = fingerprint
            
            success = False
            for attempt in range(10): 
                try:
                    resp = await client.get(url, params=params, timeout=30.0)
                    if resp.status_code == 429:
                        wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                        print(f"Rate limited (429). Waiting {wait_time:.2f}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if resp.status_code >= 500:
                        print(f"Server error {resp.status_code}. Retrying...")
                        await asyncio.sleep(2)
                        continue
                        
                    resp.raise_for_status()
                    success = True
                    break
                except httpx.RequestError as e:
                    print(f"Request failed: {e}, retrying...")
                    await asyncio.sleep(2)
            
            if not success:
                print("Max retries reached or request failed repeatedly. Stopping.")
                break

            data = resp.json()
            
            if not data.get("data"):
                if "Error" in data:
                    print(f"API Error: {data}")
                else:
                    print("No more data found.")
                break
            
            batch = data.get("data", [])
            if not batch:
                print("Empty batch returned.")
                break

            first_ts = batch[0].get("block_timestamp", 0)
            last_ts = batch[-1].get("block_timestamp", 0)
            print(f"Fetched {len(batch)} transactions. Range: {datetime.fromtimestamp(first_ts/1000)} -> {datetime.fromtimestamp(last_ts/1000)}")
            
            for tx in batch:
                ts = tx.get("block_timestamp", 0)
                # Double check timestamp just in case
                if ts < start_2025 or ts > end_2025:
                    continue
                txs.append(tx)
            
            fingerprint = data.get("meta", {}).get("fingerprint")
            if not fingerprint:
                print("No more pages.")
                break
            
            await asyncio.sleep(0.2)
    
    print(f"Total relevant transactions found: {len(txs)}")
    
    # Process Data
    monthly_stats = {}
    for i in range(1, 13):
        monthly_stats[i] = {"in": 0.0, "out": 0.0, "count": 0}
        
    for tx in txs:
        token_info = tx.get("token_info", {})
        symbol = token_info.get("symbol")
        contract_address = token_info.get("address")
        
        is_usdt = (symbol == "USDT") or (contract_address == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
        if not is_usdt:
            continue
            
        decimals = token_info.get("decimals", 6)
        try:
            val_str = tx.get("value", "0")
            amount = float(val_str) / (10 ** decimals)
        except ValueError:
            amount = 0.0
        
        ts = tx.get("block_timestamp", 0)
        dt = datetime.fromtimestamp(ts / 1000)
        month = dt.month
        
        sender = tx.get("from")
        
        if sender == address:
            monthly_stats[month]["out"] += amount
        else:
            monthly_stats[month]["in"] += amount
            
        monthly_stats[month]["count"] += 1

    # Generate Report
    print("\n" + "="*80)
    print(f"TRC20 (USDT) TURNOVER REPORT 2025: {address}")
    print("="*80)
    print(f"{'Month':<10} | {'Incoming (USDT)':<20} | {'Outgoing (USDT)':<20} | {'Txs':<5}")
    print("-" * 80)
    
    total_in = 0
    total_out = 0
    total_txs = 0
    
    for m in range(1, 13):
        month_name = datetime(2025, m, 1).strftime("%B")
        data = monthly_stats[m]
        
        in_str = f"{data['in']:,.2f}"
        out_str = f"{data['out']:,.2f}"
        
        print(f"{month_name:<10} | {in_str:<20} | {out_str:<20} | {data['count']}")
        
        total_in += data['in']
        total_out += data['out']
        total_txs += data['count']
        
    print("-" * 80)
    print(f"{'TOTAL':<10} | {total_in:,.2f}".ljust(33) + f" | {total_out:,.2f}".ljust(23) + f" | {total_txs}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(analyze_tron_2025("TU4vEruvZwLLkSfV9bNw12EJTPvNr7Pvaa"))
