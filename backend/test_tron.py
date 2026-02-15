import asyncio
from services.chain import ChainService

async def test_chain():
    print("=== Testing TRON Integration ===")
    # Test with USDT Contract Address
    address_tron = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t" 
    print(f"Fetching stats for {address_tron}...")
    
    try:
        data = await ChainService._get_tron_stats(address_tron)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print("Success!")
            print(f"Explorer Link: {data.get('explorer_link')}")
            txs = data.get('tx_list', [])
            if txs:
                print(f"Sample Tx URL: {txs[0].get('explorer_url')}")
            else:
                print("No txs found")
    except Exception as e:
        print(f"Exception: {e}")

    print("\n=== Testing EVM (ETH) Integration ===")
    address_eth = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045" # Vitalik
    print(f"Fetching stats for {address_eth}...")
    
    try:
        data = await ChainService.get_stats("ETH", address_eth)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print("Success!")
            print(f"Explorer Link: {data.get('explorer_link')}")
            txs = data.get('tx_list', [])
            if txs:
                print(f"Sample Tx URL: {txs[0].get('explorer_url')}")
            else:
                print("No txs found")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_chain())
