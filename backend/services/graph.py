import random

def build_graph_data(address, chain_data):
    nodes = []
    edges = []
    
    # Track added nodes to avoid duplicates
    nodes_seen = set()
    
    # Add Main Node (Target Address)
    main_id = address
    is_contract_main = chain_data.get("is_contract", False)
    main_type = "Contract" if is_contract_main else "Target"
    
    nodes.append({
        "data": {
            "id": main_id, 
            "label": f"{address[:6]}... ({main_type})", 
            "full_label": address,
            "type": main_type,
            "color": "#3b82f6", # Blue (Target)
            "size": 80,
            "is_contract": is_contract_main
        }
    })
    nodes_seen.add(main_id)
    
    if "graph_data" in chain_data and chain_data["graph_data"]:
        # Universal Real Data Graph Builder (BTC, EVM, TRON)
        for idx, edge in enumerate(chain_data["graph_data"]):
            source = edge["source"]
            target = edge["target"]
            val = edge["value"]
            currency = edge.get("currency", "Coin")
            tx_hash = edge.get("hash", f"tx_{idx}")
            timestamp = edge.get("timestamp", 0)
            method = edge.get("method")
            
            # Ensure Source Node Exists
            if source not in nodes_seen:
                # Determine node color/type for Source
                # If source is not the main address, it's an external wallet sending TO someone (maybe us, maybe someone else)
                label = f"{source[:4]}..."
                node_type = "Wallet"
                color = "#10b981" # Green (Incoming to someone) - Defaulting to 'external' color
                
                # If we are the target, then this source is sending to us (Incoming) -> Green
                if target == address:
                    color = "#10b981" 
                else:
                    # We are not the target. So Source is sending to Target. 
                    # If Source is not us, it's just a third party? 
                    # But usually one of them IS us.
                    # If Source is us (should be covered by nodes_seen check if address casing matches), color is Blue.
                    pass 

                # Simplified Logic: Just add any missing node as a "Related Wallet"
                if len(source) < 10: 
                    label = source
                    node_type = "Special"
                
                nodes.append({
                    "data": {
                        "id": source,
                        "label": f"{label} ({node_type})",
                        "full_label": source,
                        "type": node_type,
                        "color": "#94a3b8" if source != address else "#3b82f6", # Gray for unknown, Blue if it matches us (but casing diff)
                        "size": 40
                    }
                })
                nodes_seen.add(source)

            # Ensure Target Node Exists
            if target not in nodes_seen:
                label = f"{target[:4]}..."
                node_type = "Wallet"
                color = "#ef4444" # Red (Outgoing from someone)
                
                # Heuristic: If method implies interaction, might be contract
                if method and method != "transfer":
                    node_type = "Contract?"
                    color = "#f59e0b"
                
                if len(target) < 10:
                    label = target
                    node_type = "Special"

                nodes.append({
                    "data": {
                        "id": target,
                        "label": f"{label} ({node_type})",
                        "full_label": target,
                        "type": node_type,
                        "color": "#94a3b8" if target != address else "#3b82f6",
                        "size": 40
                    }
                })
                nodes_seen.add(target)
            
            # Edge Logic
            # Cytoscape edge id must be string
            edge_id = f"e_{idx}"
            
            edge_label = f"{val:.2f} {currency}"
            if method and method != "transfer":
                edge_label += f"\n[{method}]"
            
            edges.append({
                "data": {
                    "id": edge_id,
                    "source": source,
                    "target": target,
                    "label": edge_label,
                    "hash": tx_hash,
                    "amount": val,
                    "currency": currency,
                    "time": timestamp,
                    "method": method
                }
            })
                
    else:
        # Fallback Mock (Only if API returns absolutely nothing)
        sources = [
            {"name": "No Data", "val": "?", "color": "#94a3b8"}
        ]
        for i, src in enumerate(sources):
            node_id = f"mock_{i}"
            nodes.append({
                "data": {
                    "id": node_id, 
                    "label": src["name"], 
                    "color": src["color"], 
                    "size": 30
                }
            })
            edges.append({
                "data": {
                    "source": node_id, 
                    "target": main_id, 
                    "label": src["val"]
                }
            })
            
    return {"nodes": nodes, "edges": edges}
