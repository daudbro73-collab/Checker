import asyncio
from services.chain import ChainService
from services.sanctions import check_sanctions, bulk_check_sanctions

class GraphExpanderService:
    @staticmethod
    async def expand_graph(chain: str, address: str, depth: int = 1):
        """
        Performs 2-Hop Analysis (Clustering).
        1. Fetches direct transactions for the target address.
        2. Identifies top 3 senders and top 3 receivers by volume.
        3. Fetches transactions for these 6 related wallets.
        4. Returns a merged graph dataset.
        """
        # 1. Fetch Direct History (Level 1)
        # We reuse get_transactions for speed
        direct_txs = await ChainService.get_transactions(chain, address, limit=20)
        
        if not direct_txs:
            return {"nodes": [], "edges": []}

        # 2. Identify Key Counterparties
        # Aggregating volume per counterparty
        incoming = {} # addr -> volume
        outgoing = {} # addr -> volume

        for tx in direct_txs:
            src = tx.get("source") or ""
            dst = tx.get("target") or ""
            val = tx.get("value") or 0

            # Пропускаем транзакции с отсутствующими адресами или self-transfers
            if not src or not dst or src == dst:
                continue

            if src.lower() == address.lower():
                # Outgoing
                outgoing[dst] = outgoing.get(dst, 0) + val
            else:
                # Incoming
                incoming[src] = incoming.get(src, 0) + val

        # Sort by volume and pick top 3
        top_incoming = sorted(incoming.items(), key=lambda x: x[1], reverse=True)[:3]
        top_outgoing = sorted(outgoing.items(), key=lambda x: x[1], reverse=True)[:3]
        
        targets_to_expand = [x[0] for x in top_incoming] + [x[0] for x in top_outgoing]
        
        # 3. Fetch Level 2 History (Parallel)
        tasks = []
        for target in targets_to_expand:
            tasks.append(ChainService.get_transactions(chain, target, limit=5)) # Limit 5 for speed
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. Merge Data
        all_edges = []
        # Add direct edges first with hop=1
        for edge in direct_txs:
            edge["hop"] = 1
            all_edges.append(edge)
        
        # Add expanded edges with hop=2
        for res in results:
            if isinstance(res, list):
                for edge in res:
                    edge["hop"] = 2
                    all_edges.append(edge)
                    
        # 5. Build Final Node/Edge Structure for Cytoscape
        
        # Collect all unique addresses
        unique_addrs = set()
        unique_addrs.add(address)
        for edge in all_edges:
            unique_addrs.add(edge["source"])
            unique_addrs.add(edge["target"])
            
        # Bulk check sanctions (Optimized)
        sanction_map = bulk_check_sanctions(list(unique_addrs))

        nodes = []
        edges = []
        added_nodes = set()
        
        # Helper to determine node color
        def get_node_props(addr, hop_level):
            risk = sanction_map.get(addr.lower(), {})
            is_risky = risk.get("is_sanctioned", False)
            
            color = "#94a3b8" # Gray default (Hop 2)
            label_suffix = ""
            
            if addr.lower() == address.lower(): 
                return "#3b82f6", "Target", 60 # Blue
            
            if is_risky:
                return "#ef4444", f"RISK! ({risk.get('source')})", 50 # Red
            
            if hop_level == 1:
                return "#10b981", "Direct", 40 # Green
            
            return color, "Hop 2", 20

        # Process edges to build nodes and edges list
        for i, edge in enumerate(all_edges):
            src = edge["source"]
            dst = edge["target"]
            val = edge["value"]
            hop = edge.get("hop", 1)
            
            # Add Source Node
            if src not in added_nodes:
                color, suffix, size = get_node_props(src, hop)
                # If src is one of the expanded targets, ensure it's marked as hop 1
                if src in targets_to_expand:
                     color, suffix, size = get_node_props(src, 1)

                nodes.append({
                    "data": {
                        "id": src,
                        "label": f"{src[:4]}... {suffix}",
                        "full_label": src,
                        "color": color,
                        "size": size,
                        "risk": sanction_map.get(src.lower(), {}).get("is_sanctioned", False)
                    }
                })
                added_nodes.add(src)

            # Add Target Node
            if dst not in added_nodes:
                color, suffix, size = get_node_props(dst, hop)
                if dst in targets_to_expand:
                     color, suffix, size = get_node_props(dst, 1)

                nodes.append({
                    "data": {
                        "id": dst,
                        "label": f"{dst[:4]}... {suffix}",
                        "full_label": dst,
                        "color": color,
                        "size": size,
                        "risk": sanction_map.get(dst.lower(), {}).get("is_sanctioned", False)
                    }
                })
                added_nodes.add(dst)

            edges.append({
                "data": {
                    "id": f"e_{i}",
                    "source": src,
                    "target": dst,
                    "label": f"{val:.4f}",
                    "weight": 1 if hop == 1 else 0.5,
                    "color": "#ef4444" if (sanction_map.get(src.lower(), {}).get("is_sanctioned") or sanction_map.get(dst.lower(), {}).get("is_sanctioned")) else "#cbd5e1"
                }
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "expansion_stats": {
                "direct_neighbors": len(targets_to_expand),
                "total_nodes": len(nodes),
                "total_edges": len(edges)
            }
        }
