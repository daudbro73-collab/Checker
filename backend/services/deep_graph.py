"""Deep Multi-Hop Graph & Taint Analysis Engine (2-hop and 3-hop).

Traces indirect exposure paths to mixers, sanctions, and darknet entities through
intermediate relay wallets with distance-decay weighting.
"""
import asyncio
import logging
from typing import Dict, Any, List, Set, Tuple

from services.chain import ChainService
from services.sanctions import bulk_check_sanctions
from services.known_entities import lookup_known_entity
from services.redis_client import cache_json_get, cache_json_set

logger = logging.getLogger("aml.deep_graph")

# Known mixer and privacy protocol addresses (normalized lowercase)
KNOWN_MIXERS: Dict[str, Dict[str, str]] = {
    # Tornado Cash Router & Pools (ETH / BSC / Arbitrum)
    "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b": {"name": "Tornado.Cash: Router", "category": "mixer"},
    "0x722122df12d4e14e13ac3b6895a86e84145b6967": {"name": "Tornado.Cash: 0.1 ETH", "category": "mixer"},
    "0xd4744b7988ba9745084931a55a028ea6188e0866": {"name": "Tornado.Cash: 1 ETH", "category": "mixer"},
    "0x07687e702b410fa43f4cb4af7fa09a02204207e0": {"name": "Tornado.Cash: 10 ETH", "category": "mixer"},
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": {"name": "Tornado.Cash: 100 ETH", "category": "mixer"},
    "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936": {"name": "Tornado.Cash: 100 USDT", "category": "mixer"},
    "0x169ad27a470d064dae56857772405dae12f67266": {"name": "Tornado.Cash: 1000 USDT", "category": "mixer"},
    "0x0836222f2b2b24a3f36f98668ed8f0b38d1a872f": {"name": "Tornado.Cash: BSC 1 BNB", "category": "mixer"},
    "0xb8a4a58087ab9113d5a42fb449f8ecf7596ff1b8": {"name": "Tornado.Cash: BSC 10 BNB", "category": "mixer"},
    # Railgun privacy contracts
    "0xfa7093cdd9ee6932b4eb2c9e1cde7ce00b1fa4b9": {"name": "Railgun Privacy Contract", "category": "mixer"},
}


class DeepGraphService:
    @staticmethod
    async def expand_deep_graph(chain: str, address: str, depth: int = 2) -> Dict[str, Any]:
        """
        Recursively trace counterparty transactions up to `depth` hops (max 3).
        Identifies indirect taint paths to mixers, OFAC sanctions, and bridge hops.
        """
        chain_norm = (chain or "ETH").upper()
        target_norm = address.lower() if chain_norm in ("ETH", "BSC", "BTC") else address
        depth_clamped = max(1, min(depth, 3))

        cache_key = f"deep_graph:{chain_norm}:{target_norm}:d{depth_clamped}"
        cached = cache_json_get(cache_key)
        if cached:
            return cached

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        edge_keys: Set[str] = set()
        taint_paths: List[Dict[str, Any]] = []

        # Queue of addresses to explore: (address, current_hop, path_from_target)
        explored_addrs: Set[str] = set()
        current_layer: List[Tuple[str, List[str]]] = [(target_norm, [target_norm])]

        # Target node initialization
        nodes[target_norm] = {
            "id": target_norm,
            "label": f"{target_norm[:6]}...{target_norm[-4:]}",
            "hop": 0,
            "category": "target",
            "color": "#3b82f6",  # Blue
            "size": 65,
        }
        explored_addrs.add(target_norm)

        for hop in range(1, depth_clamped + 1):
            if not current_layer:
                break

            next_layer: List[Tuple[str, List[str]]] = []
            # Limit parallel branch expansion to top counterparties per node
            tasks = []
            layer_metadata = []

            for cur_addr, path in current_layer:
                tasks.append(ChainService.get_transactions(chain_norm, cur_addr, limit=12 if hop == 1 else 6))
                layer_metadata.append((cur_addr, path))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (parent_addr, parent_path), res in zip(layer_metadata, results):
                if not isinstance(res, list) or not res:
                    continue

                # Sort by value descending to pick highest flow counterparties
                valid_txs = []
                for tx in res:
                    src = str(tx.get("source") or "").strip()
                    dst = str(tx.get("target") or "").strip()
                    if not src or not dst or src.lower() == dst.lower():
                        continue
                    try:
                        val = float(tx.get("value") or 0)
                    except (ValueError, TypeError):
                        val = 0.0
                    valid_txs.append((src, dst, val, tx))

                valid_txs.sort(key=lambda x: x[2], reverse=True)
                # Take top 5 counterparties per node for Hop 1, top 3 for Hop 2/3
                branch_limit = 5 if hop == 1 else 3

                for src, dst, val, raw_tx in valid_txs[:branch_limit]:
                    src_clean = src.lower() if chain_norm in ("ETH", "BSC", "BTC") else src
                    dst_clean = dst.lower() if chain_norm in ("ETH", "BSC", "BTC") else dst
                    counterparty = dst_clean if src_clean == parent_addr else src_clean

                    # Add unique edge
                    e_key = f"{src_clean}->{dst_clean}:{raw_tx.get('hash') or val}"
                    if e_key not in edge_keys:
                        edge_keys.add(e_key)
                        edges.append({
                            "source": src_clean,
                            "target": dst_clean,
                            "value": val,
                            "currency": raw_tx.get("currency") or chain_norm,
                            "hop": hop,
                            "hash": raw_tx.get("hash"),
                            "timestamp": raw_tx.get("timestamp"),
                        })

                    # Track new node
                    if counterparty not in nodes:
                        nodes[counterparty] = {
                            "id": counterparty,
                            "label": f"{counterparty[:6]}...{counterparty[-4:]}",
                            "hop": hop,
                            "category": "counterparty" if hop == 1 else "intermediary",
                            "color": "#94a3b8",  # Default slate gray
                            "size": 40 if hop > 1 else 50,
                        }

                    new_path = parent_path + [counterparty]
                    if counterparty not in explored_addrs and hop < depth_clamped:
                        explored_addrs.add(counterparty)
                        next_layer.append((counterparty, new_path))

            current_layer = next_layer

        # Bulk check all gathered nodes against OFAC & Sanctions
        all_unique_nodes = list(nodes.keys())
        sanction_map = bulk_check_sanctions(all_unique_nodes)

        # Classify nodes and trace taint paths
        for addr_id, node in nodes.items():
            if addr_id == target_norm:
                continue

            addr_l = addr_id.lower()
            s_info = sanction_map.get(addr_l, {})
            mixer_info = KNOWN_MIXERS.get(addr_l)
            known_ent = lookup_known_entity(addr_l)

            if s_info.get("is_sanctioned"):
                node["category"] = "sanctions"
                node["color"] = "#ef4444"  # Red
                node["risk"] = "CRITICAL"
                node["reason"] = f"{s_info.get('source')} ({s_info.get('reason')})"
                node["size"] = 55
                taint_paths.append({
                    "risk_type": "SANCTIONS",
                    "entity": s_info.get("reason") or "OFAC SDN",
                    "hop_distance": node["hop"],
                    "threat_node": addr_id,
                    "decay_weight": 1.0 if node["hop"] == 1 else (0.5 if node["hop"] == 2 else 0.25),
                })
            elif mixer_info:
                node["category"] = "mixer"
                node["color"] = "#dc2626"  # Deep red
                node["risk"] = "HIGH"
                node["reason"] = mixer_info.get("name")
                node["size"] = 55
                taint_paths.append({
                    "risk_type": "MIXER",
                    "entity": mixer_info.get("name"),
                    "hop_distance": node["hop"],
                    "threat_node": addr_id,
                    "decay_weight": 1.0 if node["hop"] == 1 else (0.5 if node["hop"] == 2 else 0.25),
                })
            elif known_ent:
                cat = known_ent.get("category")
                if cat == "bridge":
                    node["category"] = "bridge"
                    node["color"] = "#a855f7"  # Purple
                    node["label"] = known_ent.get("name")
                elif cat == "cex":
                    node["category"] = "cex"
                    node["color"] = "#10b981"  # Emerald Green
                    node["label"] = known_ent.get("name")
                elif cat == "dex":
                    node["category"] = "dex"
                    node["color"] = "#06b6d4"  # Cyan

        result = {
            "target": target_norm,
            "chain": chain_norm,
            "depth_explored": depth_clamped,
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "taint_paths_found": len(taint_paths),
                "max_hop": max([n.get("hop", 0) for n in nodes.values()]) if nodes else 0,
                "has_mixer_taint": any(t["risk_type"] == "MIXER" for t in taint_paths),
                "has_sanctions_taint": any(t["risk_type"] == "SANCTIONS" for t in taint_paths),
            },
            "taint_paths": taint_paths,
            "nodes": list(nodes.values()),
            "edges": edges,
        }

        # Cache deep graph response for 10 minutes
        cache_json_set(cache_key, result, ttl_seconds=600)
        return result
