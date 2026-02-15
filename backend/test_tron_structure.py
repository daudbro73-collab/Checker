import asyncio
import httpx
import json
import time

async def test_tron_structure():
    print("=== TRON STRUCTURE DEBUG ===")
    
    # Check USDT Contract Account Info to see how balances are stored
    addr = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    url = f"https://api.trongrid.io/v1/accounts/{addr}"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                acc = data['data'][0]
                # Check for trc20 field
                trc20 = acc.get("trc20", [])
                print(f"TRC20 Field Type: {type(trc20)}")
                print(f"TRC20 Sample: {json.dumps(trc20[:3], indent=2) if isinstance(trc20, list) and trc20 else 'Empty'}")
                
                # Check for assetV2 (TRC10)
                assetV2 = acc.get("assetV2", [])
                print(f"AssetV2 Sample: {json.dumps(assetV2[:1], indent=2) if assetV2 else 'Empty'}")
            else:
                print("No data found")
        else:
            print(f"Error: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_tron_structure())
