import asyncio
from services.chain import ChainService
from services.risk_engine import calculate_risk_score
from services.sanctions import check_sanctions

async def test():
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045" # Vitalik
    chain = "OPTIMISM"
    
    print(f"Testing {chain} for {address}...")
    try:
        # 1. Sanctions
        print("Checking sanctions...")
        sanction_result = check_sanctions(address)
        print("Sanctions result:", sanction_result)

        # 2. Chain Stats
        print("Getting chain stats...")
        chain_data = await ChainService.get_stats(chain, address)
        print("Chain stats keys:", chain_data.keys())
        if "error" in chain_data:
            print("Chain error:", chain_data["error"])

        # 3. Risk Score
        print("Calculating risk...")
        risk_score, risk_factors, risk_level = calculate_risk_score(sanction_result, chain_data)
        print(f"Risk: {risk_score} ({risk_level})")
        
        # 4. Graph Data (import here to avoid circular if any, though unlikely)
        from services.graph import build_graph_data
        print("Building graph...")
        graph_data = build_graph_data(address, chain_data)
        print("Graph nodes:", len(graph_data["nodes"]))

        print("SUCCESS")
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
