"""Counterparty flow graph for Cytoscape.

Quality rules:
- Full sample of fetched txs (not a tiny top-N only)
- Correct IDs: ETH lowercased, TRON hex→Base58, no duplicate Target
- No fake mock nodes; no zero-value noise
- BTC: all real counterparties for send/receive (not every unrelated UTXO spam)
- Aggregate repeated A↔B into one edge with sum + count
"""
from __future__ import annotations

import hashlib
from typing import Any

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
# Soft cap only for UI readability — raised so graph stays informative
MAX_COUNTERPARTIES = 48
DUST = 1e-12


def _b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n > 0:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = 0
    for b in raw:
        if b == 0:
            pad += 1
        else:
            break
    return _B58[0] * pad + (out or _B58[0])


def tron_hex_to_base58(addr: str) -> str:
    if not addr or isinstance(addr, dict):
        return str(addr) if addr else ""
    a = str(addr).strip()
    if a.startswith("T") and len(a) == 34:
        return a
    h = a[2:] if a.lower().startswith("0x") else a
    if not (len(h) == 42 and h.lower().startswith("41")):
        return a
    try:
        raw = bytes.fromhex(h)
        checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
        return _b58encode(raw + checksum)
    except Exception:
        return a


def _norm_id(addr: str, chain_hint: str = "") -> str:
    if not addr:
        return ""
    a = tron_hex_to_base58(str(addr).strip())
    if a.startswith("0x") or (chain_hint or "").upper() in ("ETH", "EVM"):
        return a.lower()
    return a


def _short(addr: str) -> str:
    if not addr or len(addr) <= 14:
        return addr or "?"
    return f"{addr[:7]}…{addr[-5:]}"


def _fmt_amount(val: float, currency: str) -> str:
    ccy = currency or ""
    if val >= 1000:
        return f"{val:,.2f} {ccy}".strip()
    if val >= 1:
        return f"{val:.4f} {ccy}".strip()
    if val >= 0.0001:
        return f"{val:.6f} {ccy}".strip()
    return f"{val:.8g} {ccy}".strip()


def build_graph_data(address: str, chain_data: dict) -> dict:
    chain_type = (chain_data.get("type") or "").upper()
    default_ccy = {
        "EVM": "ETH", "ETH": "ETH", "TRON": "TRX", "BTC": "BTC",
    }.get(chain_type, "Coin")

    chain_data = dict(chain_data or {})
    chain_data["address"] = address
    main = _norm_id(address, chain_type)
    if not main:
        return {"nodes": [], "edges": [], "meta": {"counterparties": 0, "flows": 0}}

    raw = _normalize_raw_edges(chain_data.get("graph_data") or [], main, default_ccy, chain_type)
    # Merge tx_list too (token transfers / richer sample) without losing graph_data
    from_tx = _edges_from_tx_list(chain_data.get("tx_list") or [], main, default_ccy, chain_type)
    raw = _merge_edge_lists(raw, from_tx)

    related = [
        e for e in raw
        if (e["source"] == main or e["target"] == main)
        and e["source"] != e["target"]
        and float(e.get("value") or 0) > DUST
    ]

    # Aggregate A→B + currency (sum of all transfers in sample)
    agg: dict[tuple, dict] = {}
    for e in related:
        key = (e["source"], e["target"], (e.get("currency") or default_ccy))
        slot = agg.get(key)
        if not slot:
            agg[key] = {
                "source": e["source"],
                "target": e["target"],
                "value": 0.0,
                "currency": key[2],
                "hashes": [],
                "count": 0,
            }
            slot = agg[key]
        slot["value"] += float(e.get("value") or 0)
        slot["count"] += 1
        h = e.get("hash")
        if h and h not in slot["hashes"]:
            slot["hashes"].append(h)

    # Rank by volume; keep both directions; soft-cap counterparties not edges
    ranked = sorted(agg.values(), key=lambda x: x["value"], reverse=True)

    # Prefer keeping highest-volume counterparties (in + out together)
    cp_volume: dict[str, float] = {}
    for e in ranked:
        other = e["target"] if e["source"] == main else e["source"]
        cp_volume[other] = cp_volume.get(other, 0) + e["value"]
    keep_cps = {
        a for a, _ in sorted(cp_volume.items(), key=lambda x: x[1], reverse=True)[:MAX_COUNTERPARTIES]
    }
    ranked = [
        e for e in ranked
        if (e["target"] if e["source"] == main else e["source"]) in keep_cps
    ]

    nodes = [{
        "data": {
            "id": main,
            "label": _node_label(address, main, chain_data, is_you=True),
            "full_label": address,
            "type": "Target",
            "flow": "target",
            "color": "#22d3ee",
            "size": 78,
            "is_you": True,
            **_node_truth(main, chain_data),
        }
    }]
    seen = {main}
    edges = []
    total_in = 0.0
    total_out = 0.0

    for i, e in enumerate(ranked):
        src, tgt = e["source"], e["target"]
        inbound = tgt == main
        other = src if inbound else tgt
        if inbound:
            total_in += e["value"]
        else:
            total_out += e["value"]

        if other not in seen:
            vol = cp_volume.get(other, e["value"])
            size = 36 + min(40, int((vol / max(total_in + total_out + vol, 1e-9)) * 80))
            truth = _node_truth(other, chain_data)
            color = "#34d399" if inbound else "#f97316"
            if truth.get("is_sanctioned"):
                color = "#ff2d2d"
            elif truth.get("is_bridge"):
                color = "#06b6d4"
            elif truth.get("is_cex"):
                color = "#3b82f6"
            nodes.append({
                "data": {
                    "id": other,
                    "label": _node_label(other, other, chain_data, is_you=False),
                    "full_label": other,
                    "type": "Sanctioned" if truth.get("is_sanctioned") else ("Bridge" if truth.get("is_bridge") else ("CEX" if truth.get("is_cex") else ("In" if inbound else "Out"))),
                    "flow": "in" if inbound else "out",
                    "color": color,
                    "size": size,
                    "is_you": False,
                    **truth,
                }
            })
            seen.add(other)

        node = next((n for n in nodes if n["data"]["id"] == other), None)
        if node and not node["data"].get("is_sanctioned"):
            has_in = any(x["target"] == main and x["source"] == other for x in ranked)
            has_out = any(x["source"] == main and x["target"] == other for x in ranked)
            if has_in and has_out:
                # No separate "both" legend — keep orange (outgoing cue) with dual flow mark
                node["data"]["color"] = "#fb923c"
                node["data"]["type"] = "In/Out"
                node["data"]["flow"] = "both"

        ccy = e.get("currency") or default_ccy
        label = _fmt_amount(e["value"], ccy)
        if e["count"] > 1:
            label += f" ({e['count']} tx)"

        edges.append({
            "data": {
                "id": f"e{i}",
                "source": src,
                "target": tgt,
                "label": label,
                "hash": (e["hashes"][0] if e["hashes"] else None),
                "hashes": e["hashes"][:8],
                "amount": e["value"],
                "currency": ccy,
                "count": e["count"],
                "color": "#ff2d2d" if (
                    (node and node["data"].get("is_sanctioned"))
                ) else ("#34d399" if inbound else "#f97316"),
                "hot": bool(node and node["data"].get("is_sanctioned")),
            }
        })

    truncated = len(cp_volume) > len(keep_cps)
    meta = {
        "counterparties": max(0, len(seen) - 1),
        "flows": len(edges),
        "sample_in": round(total_in, 8),
        "sample_out": round(total_out, 8),
        "truncated": truncated,
        "total_counterparties_in_sample": len(cp_volume),
        "sanctioned_nodes": sum(1 for n in nodes if n["data"].get("is_sanctioned")),
    }

    if len(nodes) == 1:
        nodes.append({
            "data": {
                "id": "_empty",
                "label": "No transfers in sample",
                "full_label": "Explorer returned no non-zero flows for this address sample",
                "type": "Empty",
                "color": "#64748b",
                "size": 30,
                "is_you": False,
            }
        })

    return {"nodes": nodes, "edges": edges, "meta": meta}


def _lookup_map(chain_data: dict) -> dict:
    labels = chain_data.get("risk_labels") or {}
    # keys may be lowercased
    return {str(k).lower(): v for k, v in labels.items()} if isinstance(labels, dict) else {}


def _sanction_map(chain_data: dict) -> dict:
    out = {}
    cs = chain_data.get("counterparty_sanctions") or {}
    for ev in cs.get("exposure_events") or []:
        addr = (ev.get("address") or "").lower()
        if addr:
            out[addr] = {
                "is_sanctioned": True,
                "source": ev.get("source"),
                "category": ev.get("category"),
            }
    # Also from bulk map if present as dict keyed by address
    raw = cs.get("by_address") or {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict) and v.get("is_sanctioned"):
                out[str(k).lower()] = v
    target = chain_data.get("target_sanctions") or {}
    if target.get("is_sanctioned"):
        # main id filled later via _node_truth
        out["__target__"] = target
    return out


def _node_truth(addr_id: str, chain_data: dict) -> dict:
    from services.known_entities import lookup_known_entity
    labels = _lookup_map(chain_data)
    sanctions = _sanction_map(chain_data)
    key = (addr_id or "").lower()
    lab = labels.get(key) or {}
    san = sanctions.get(key) or {}
    target = chain_data.get("target_sanctions") or {}
    # match target by comparing normalized ids loosely
    main_addr = (chain_data.get("address") or "")
    if target.get("is_sanctioned") and key and main_addr and key == main_addr.lower():
        san = target

    known = lookup_known_entity(key) or {}
    entity = lab.get("label") or lab.get("category") or san.get("reason") or san.get("category") or known.get("name")
    source = san.get("source") or lab.get("source") or ("Registry" if known else None)
    category = san.get("category") or lab.get("category") or known.get("category")
    is_bridge = bool(known.get("is_bridge"))
    is_cex = known.get("category") == "cex"
    is_dex = known.get("category") == "dex"

    return {
        "is_sanctioned": bool(san.get("is_sanctioned")),
        "entity": entity,
        "source": source,
        "category": category,
        "is_bridge": is_bridge,
        "is_cex": is_cex,
        "is_dex": is_dex,
    }


def _node_label(display: str, addr_id: str, chain_data: dict, is_you: bool) -> str:
    if is_you:
        return f"{_short(display)} · YOU"
    truth = _node_truth(addr_id, chain_data)
    if truth.get("is_sanctioned"):
        ent = truth.get("entity") or truth.get("source") or "SANCTIONED"
        return f"{_short(display)} · {str(ent)[:18]}"
    if truth.get("entity"):
        return f"{_short(display)} · {str(truth['entity'])[:16]}"
    return _short(display)


def _merge_edge_lists(a: list, b: list) -> list:
    seen = set()
    out = []
    for e in a + b:
        key = (e["source"], e["target"], e.get("currency"), e.get("hash"), round(float(e.get("value") or 0), 10))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _normalize_raw_edges(raw: list, main: str, default_ccy: str, chain_type: str) -> list[dict]:
    out = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        src = _norm_id(e.get("source") or e.get("from") or "", chain_type)
        tgt = _norm_id(e.get("target") or e.get("to") or "", chain_type)
        if not src or not tgt or src == tgt:
            continue
        try:
            val = float(e.get("value") or 0)
        except (TypeError, ValueError):
            val = 0.0
        out.append({
            "source": src,
            "target": tgt,
            "value": val,
            "currency": e.get("currency") or default_ccy,
            "hash": e.get("hash"),
        })
    return out


def _edges_from_tx_list(tx_list: list, main: str, default_ccy: str, chain_type: str) -> list[dict]:
    out = []
    for tx in tx_list:
        if not isinstance(tx, dict):
            continue
        frm = _norm_id(tx.get("from") or "", chain_type)
        to = _norm_id(tx.get("to") or "", chain_type)
        val = _parse_tx_value(tx.get("value"))
        ccy = default_ccy
        raw_val = str(tx.get("value") or "")
        for token in ("USDT", "USDC", "TRX", "ETH", "BTC", "WETH"):
            if token in raw_val.upper().split() or raw_val.upper().endswith(token):
                ccy = token
                break
        if tx.get("token"):
            ccy = str(tx.get("token"))
        # Never put TRC-10 spam / dust into the flow graph
        if (ccy or "").upper() in ("TRC10", "TRC-10") or "(TRC-10)" in raw_val:
            continue
        if frm and to and (frm == main or to == main) and val > DUST:
            out.append({
                "source": frm,
                "target": to,
                "value": val,
                "currency": ccy,
                "hash": tx.get("hash"),
            })
    return out


def _parse_tx_value(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip().split()
    if not s:
        return 0.0
    try:
        return float(s[0])
    except ValueError:
        return 0.0
