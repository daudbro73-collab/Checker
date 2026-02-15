import asyncio
import httpx
import json

async def test_tron_deep():
    print("=== DEEP TRON DEBUGGING ===")
    
    user_addr = "TVj7RNVHy6thvtPs56TSpILscvNoYidkqE"
    
    # 1. Basic Account Info
    print(f"\n--- 1. Account Info: {user_addr} ---")
    url_info = f"https://api.trongrid.io/v1/accounts/{user_addr}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url_info, timeout=10.0)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                print("Account found.")
            else:
                print("Account data empty (might be inactive).")
        else:
            print(f"Error: {resp.text}")

    # 2. TRC20 Transactions (Retry with correct endpoint structure?)
    print(f"\n--- 2. TRC20 Txs: {user_addr} ---")
    # Endpoint reference: https://developers.tron.network/reference/get-trc20-transaction-info-by-account-address
    url_trc20 = f"https://api.trongrid.io/v1/accounts/{user_addr}/transactions/trc20"
    
    # Maybe add some params?
    params = {"limit": 5}
    
    async with httpx.AsyncClient() as client:
        print(f"Requesting: {url_trc20}")
        resp = await client.get(url_trc20, params=params, timeout=10.0)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            txs = data.get("data", [])
            print(f"TRC20 Txs found: {len(txs)}")
            if len(txs) > 0:
                print(f"Sample TRC20 Tx: {json.dumps(txs[0], indent=2)}")
        else:
            print(f"Error: {resp.text}")

    # 3. Check USDT Contract for TRC20 Txs (Control Group)
    print(f"\n--- 3. TRC20 Txs (USDT Contract) ---")
    usdt_contract = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    url_trc20_usdt = f"https://api.trongrid.io/v1/accounts/{usdt_contract}/transactions/trc20"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url_trc20_usdt, params={"limit": 2}, timeout=10.0)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            txs = data.get("data", [])
            print(f"USDT TRC20 Txs found: {len(txs)}")
        else:
            print(f"Error: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_tron_deep())
