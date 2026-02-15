import time

def calculate_risk_score(sanctions_data, chain_data):
    """
    Advanced Heuristic Risk Scoring
    Score: 0 (Safe) - 100 (Critical)
    """
    score = 0
    factors = []
    
    # 1. Sanctions Check (Critical)
    if sanctions_data.get("is_sanctioned"):
        score = 100
        factors.append({"level": "CRITICAL", "desc": f"Direct Match: {sanctions_data.get('source')}"})
        return score, factors, "CRITICAL"

    # 2. Activity Metrics
    tx_count = chain_data.get("tx_count", 0)
    balance = chain_data.get("balance", 0)
    tx_list = chain_data.get("tx_list", [])
    
    # Wallet Age / Usage
    if tx_count == 0:
        score += 0 # Neutral, just empty
        factors.append({"level": "INFO", "desc": "Inactive Wallet (No History)"})
    elif tx_count < 5 and balance > 100:
        # New wallet with high balance -> Suspicious layering?
        score += 25
        factors.append({"level": "MEDIUM", "desc": "New Wallet with High Balance (Potential Layering)"})
    elif tx_count > 10000:
        score += 15
        factors.append({"level": "LOW", "desc": "High Frequency Activity (Exchange/Bot/Service)"})

    # 3. Transaction Pattern Analysis (Velocity & Volume)
    if tx_list:
        now = time.time()
        recent_txs = [tx for tx in tx_list if (now - tx.get("timestamp", 0)) < 3600] # Last 1 hour (timestamps in SECONDS)
        
        # Velocity
        if len(recent_txs) > 10:
            score += 20
            factors.append({"level": "MEDIUM", "desc": "High Velocity (>10 Tx in 1h)"})
            
        # Volume Analysis
        total_val = sum([float(tx.get("value", "0").split()[0]) for tx in tx_list if tx.get("value")])
        if total_val > 100000:
            score += 30
            factors.append({"level": "HIGH", "desc": "High Volume Transaction Flow (>100k)"})
            
        # Round Numbers Heuristic (often human/payment, less organic defi)
        round_vals = 0
        for tx in tx_list:
            val_str = tx.get("value", "0").split()[0]
            try:
                val = float(val_str)
                if val > 10 and val % 10 == 0:
                    round_vals += 1
            except:
                pass
        
        if round_vals > 2:
            score += 10
            factors.append({"level": "LOW", "desc": "Multiple Round-Number Transactions"})

    # 4. Balance Metrics
    if balance > 10000: # Whale
        score += 10
        factors.append({"level": "INFO", "desc": "Whale Wallet (>10k Native)"})
    
    # 5. Contract Interaction
    if chain_data.get("is_contract"):
        score -= 10 # Contracts are often safe infrastructure
        factors.append({"level": "INFO", "desc": "Verified Contract Address"})
        if score < 0: score = 0

    # Cap score
    score = min(score, 99)
    
    # Determine Level
    level = "SAFE"
    if score >= 75: level = "CRITICAL"
    elif score >= 40: level = "WARNING"
    elif score >= 20: level = "CAUTION"
    
    return score, factors, level
