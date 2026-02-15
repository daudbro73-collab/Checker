import asyncio
from services.chain import ChainService
import json

async def test():
    print("=== TESTING CHAIN SERVICE ===")
    
    # 1. ETH Test
    print("\n--- ETH (Blockscout) ---")
    eth_addr = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045" # Vitalik
    try:
        eth_data = await ChainService.get_stats("ETH", eth_addr)
        print(f"ETH Balance: {eth_data.get('balance_display')}")
        print(f"ETH Tx Count: {len(eth_data.get('tx_list', []))}")
        if eth_data.get('error'):
            print(f"ETH Error: {eth_data.get('error')}")
    except Exception as e:
        print(f"ETH Exception: {e}")

    # 2. TRON Test (USDT Contract)
    print("\n--- TRON (USDT Contract) ---")
    tron_contract = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    try:
        tron_data = await ChainService.get_stats("TRON", tron_contract)
        print(f"TRON Balance: {tron_data.get('balance_display')}")
        print(f"TRON Tx Count: {len(tron_data.get('tx_list', []))}")
        if tron_data.get('error'):
            print(f"TRON Error: {tron_data.get('error')}")
    except Exception as e:
        print(f"TRON Exception: {e}")

    # 3. TRON Test (User Address)
    print("\n--- TRON (User Address) ---")
    tron_user = "TVj7RNVHy6thvtPs56TSpILscvNoYidkqE"
    try:
        tron_data_user = await ChainService.get_stats("TRON", tron_user)
        print(f"TRON Balance: {tron_data_user.get('balance_display')}")
        print(f"TRON Tx Count: {len(tron_data_user.get('tx_list', []))}")
        # Print first tx if exists to check parsing
        if tron_data_user.get('tx_list'):
            print(f"Sample Tx: {tron_data_user['tx_list'][0]}")
        
        if tron_data_user.get('error'):
            print(f"TRON Error: {tron_data_user.get('error')}")
    except Exception as e:
        print(f"TRON Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test())
