"""
Risk scoring v2:
- exposure-weighted counterparties (not raw counts)
- dust filter
- pure behavioural heuristics capped at CAUTION
- source severity matrix
"""
import time
from datetime import datetime


DUST_USD = 10.0
DUST_PCT = 0.005  # 0.5% of wallet volume


def calculate_risk_score(sanctions_data, chain_data, address: str = ""):
    score = 0
    factors = []
    has_external_signal = False
    meta = {
        "method": "exposure_v2",
        "dust_filtered": 0,
        "exposure_pct_in_90d": 0.0,
        "computed_at": datetime.utcnow().isoformat(),
    }

    def add_factor(level, desc, details, implication, signal_type="behavioral", confidence="low", source=None, source_date=None):
        factors.append({
            "level": level,
            "desc": desc,
            "details": details,
            "implication": implication,
            "signal_type": signal_type,  # sanctions | label | behavioral
            "confidence": confidence,
            "source": source,
            "source_date": source_date,
            # legacy key kept empty — removed from product claims
            "cex_action": "",
        })

    # 0. Fake Asset Scam (поддельные токены / скам-копии USDT)
    fake_tokens = chain_data.get("fake_tokens") or []
    if fake_tokens:
        fake_symbols = [f"{t.get('symbol')} (фейк {t.get('impersonating', 'USDT')})" for t in fake_tokens[:3]]
        add_factor(
            "CRITICAL",
            f"Fake Asset Detected: {', '.join(fake_symbols)}",
            f"Адрес содержит поддельные токены ({', '.join(fake_symbols)}). Адрес смарт-контракта не принадлежит официальному эмитенту.",
            "Критический риск скама / фальшивого депозита. Не принимайте эти активы.",
            signal_type="asset_validity",
            confidence="high",
            source="Asset_Shield",
        )
        meta["has_fake_assets"] = True
        has_external_signal = True
        score = max(score, 98)
    # 0b. TON Network Scam Label
    if chain_data.get("is_scam"):
        add_factor(
            "CRITICAL",
            "TON Network Scam Label (TonAPI / Tonkeeper)",
            "Кошелек официально помечен как SCAM в сети The Open Network сообществом и Tonkeeper.",
            "Критический риск. Не отправляйте средства.",
            signal_type="label",
            confidence="high",
            source="TonAPI",
        )
        has_external_signal = True
        return 96, factors, "CRITICAL", meta

    # 0c. Address Poisoning Attack Alert
    poisoning_attacks = chain_data.get("address_poisoning_attacks") or []
    if poisoning_attacks:
        has_external_signal = True
        score = max(score, 45)
        meta["poisoning_attacks_count"] = len(poisoning_attacks)
        add_factor(
            "WARNING",
            f"Address Poisoning Attack Detected ({len(poisoning_attacks)})",
            "Обнаружены вредоносные микротранзакции, имитирующие адрес вашего частого контакта (подделка первых и последних символов).",
            "Внимание: не копируйте адрес получателя из истории транзакций! Всегда сверяйте адрес полностью.",
            signal_type="poisoning",
            confidence="high",
            source="Anti_Poisoning_Shield",
        )

    # 1. Direct sanctions / Tether freeze
    if sanctions_data.get("is_sanctioned"):
        source = sanctions_data.get("source", "SANCTION")
        category = sanctions_data.get("category", "Blacklist")
        reason = sanctions_data.get("reason", "Unknown")
        listed = sanctions_data.get("listed_at")
        severity = 100 if source != "Tether" else 95
        add_factor(
            "CRITICAL",
            f"Direct match: {source} ({category})",
            f"Address found in {source}, category '{category}'. Reason: {reason}.",
            "Do not transact. High probability of frozen or blocked funds.",
            signal_type="sanctions",
            confidence="high",
            source=source,
            source_date=listed,
        )
        meta["has_external_signal"] = True
        return severity, factors, "CRITICAL", meta

    # Live GoPlus flags on the subject address
    live_flags = chain_data.get("live_risk_flags") or []
    if live_flags:
        has_external_signal = True
        score += min(35, 10 + 5 * len(live_flags))
        add_factor(
            "WARNING",
            f"Live risk labels (GoPlus): {', '.join(live_flags[:4])}",
            "Address flagged by GoPlus aggregated security labels.",
            "Treat as elevated risk until manually verified.",
            signal_type="label",
            confidence="medium",
            source="GoPlus",
            source_date="live",
        )

    # Subject risk labels from local DB
    labels = chain_data.get("risk_labels") or {}
    addr_l = (address or "").lower()
    if addr_l in labels:
        has_external_signal = True
        lab = labels[addr_l]
        score += 40
        add_factor(
            "WARNING",
            f"Risk label: {lab.get('category')} ({lab.get('source')})",
            lab.get("label") or "Listed in public risk dataset",
            "External public label — not an official sanction.",
            signal_type="label",
            confidence=lab.get("confidence", "medium"),
            source=lab.get("source"),
        )

    # 2. Exposure analysis on counterparties
    tx_list = chain_data.get("tx_list") or []
    now = time.time()
    window = 90 * 86400

    inbound = []
    for tx in tx_list:
        try:
            val = float(str(tx.get("value", "0")).split()[0])
        except ValueError:
            val = 0.0
        ts = float(tx.get("timestamp") or 0)
        direction = "in" if (tx.get("to") or "").lower() == addr_l else "out"
        inbound.append({"value": val, "timestamp": ts, "direction": direction, "from": tx.get("from"), "to": tx.get("to")})

    total_in_90 = sum(t["value"] for t in inbound if t["direction"] == "in" and (now - t["timestamp"]) <= window) or 0.0
    # Dust filter helper
    def is_dust(val: float) -> bool:
        if val < DUST_USD:
            return True
        if total_in_90 > 0 and (val / total_in_90) < DUST_PCT:
            return True
        return False

    sanctions_summary = chain_data.get("counterparty_sanctions") or {}
    events = sanctions_summary.get("exposure_events") or []
    risky_in = 0.0
    for ev in events:
        if ev.get("direction") != "in":
            continue
        val = float(ev.get("value") or 0)
        ts = float(ev.get("timestamp") or 0)
        if (now - ts) > window:
            # time decay: older than 90d ignored for exposure %
            continue
        if is_dust(val):
            meta["dust_filtered"] += 1
            continue
        age_days = max(0, (now - ts) / 86400)
        decay = max(0.25, 1.0 - (age_days / 365.0))  # linear-ish decay over a year
        weight = 1.0
        cat = (ev.get("category") or "").lower()
        src = (ev.get("source") or "").lower()
        if "sanction" in cat or src in ("ofac", "eu", "un", "ofsi"):
            weight = 1.0
        elif "hack" in cat or "mixer" in cat:
            weight = 0.7
        else:
            weight = 0.5
        risky_in += val * decay * weight

    exposure_pct = (risky_in / total_in_90 * 100) if total_in_90 > 0 else 0.0
    meta["exposure_pct_in_90d"] = round(exposure_pct, 2)

    if exposure_pct > 0:
        has_external_signal = True
        # Map exposure to score
        if exposure_pct >= 50:
            score += 55
            lvl = "HIGH"
        elif exposure_pct >= 20:
            score += 40
            lvl = "HIGH"
        elif exposure_pct >= 5:
            score += 25
            lvl = "MEDIUM"
        else:
            score += 12
            lvl = "LOW"
        cats = ", ".join(sanctions_summary.get("categories") or []) or "risk entities"
        add_factor(
            lvl,
            f"Inbound exposure {exposure_pct:.1f}% (90d) to {cats}",
            f"Share of inbound volume (dust-filtered, time-decayed) linked to risky entities.",
            "Exposure-based estimate — not a direct sanction hit.",
            signal_type="sanctions",
            confidence="medium",
            source="counterparty_lists",
        )

    # Community / low-confidence labels on counterparties — max CAUTION contribution later
    distinct = sanctions_summary.get("distinct_sanctioned") or 0
    if distinct and exposure_pct == 0:
        # counts fallback when volume missing (e.g. BTC sparse)
        has_external_signal = True
        score += min(25, 5 * distinct)
        add_factor(
            "MEDIUM",
            f"Risky counterparties detected: {distinct}",
            "Count-based fallback (volume data incomplete for exposure %).",
            "Review counterparties manually.",
            signal_type="label",
            confidence="low",
        )

    # 3. Attribution Coverage (% атрибутированных потоков) & Bridge-Aware Provenance
    from services.known_entities import lookup_known_entity

    total_flow_vol = 0.0
    attributed_flow_vol = 0.0
    bridges_detected = []
    known_counterparties_count = 0
    all_counterparties = set()

    for tx in tx_list:
        try:
            val = float(str(tx.get("value", "0")).split()[0])
        except ValueError:
            val = 0.0
        total_flow_vol += val

        frm = (tx.get("from") or "").lower()
        to = (tx.get("to") or "").lower()
        cp = frm if to == addr_l else to
        if cp:
            all_counterparties.add(cp)

        # Check attribution
        ent = lookup_known_entity(cp)
        is_labeled = cp in labels or (sanctions_summary.get("by_address") or {}).get(cp, {}).get("is_sanctioned")
        if ent:
            attributed_flow_vol += val
            known_counterparties_count += 1
            if ent.get("is_bridge"):
                bridges_detected.append(ent.get("name"))
        elif is_labeled:
            attributed_flow_vol += val
            known_counterparties_count += 1

    if total_flow_vol > 0:
        attribution_coverage_pct = round((attributed_flow_vol / total_flow_vol) * 100, 1)
    else:
        attribution_coverage_pct = 100.0 if not tx_list else 0.0

    meta["attribution_coverage_pct"] = attribution_coverage_pct
    meta["attributed_volume"] = round(attributed_flow_vol, 4)
    meta["unattributed_volume"] = round(max(0.0, total_flow_vol - attributed_flow_vol), 4)
    meta["total_flow_volume"] = round(total_flow_vol, 4)
    meta["bridges_detected"] = list(set(bridges_detected))
    meta["known_counterparties_count"] = known_counterparties_count
    meta["total_counterparties_count"] = len(all_counterparties)

    # Bridge-aware provenance break alert
    if bridges_detected:
        unique_bridges = list(set(bridges_detected))
        add_factor(
            "INFO",
            f"Cross-Chain Bridge: {', '.join(unique_bridges[:2])}",
            f"Обнаружено взаимодействие с кросс-чейн мостом ({', '.join(unique_bridges[:2])}). Происхождение средств обрывается на мосту.",
            "Реальный источник средств находится в апстрим-сети. Аналитики видят контракт моста.",
            signal_type="bridge",
            confidence="high",
            source="Bridge_Registry",
        )

    # 4. Behavioural heuristics (soft)
    behavioral_score = 0
    tx_count = chain_data.get("tx_count", 0)
    balance = chain_data.get("balance", 0)

    if tx_count == 0:
        add_factor(
            "INFO",
            "Inactive wallet (no history)",
            "No recorded transactions on-chain.",
            "Low indicated risk; history cannot confirm behaviour.",
            signal_type="behavioral",
            confidence="low",
        )
    elif tx_count < 5 and balance > 100:
        behavioral_score += 10
        add_factor(
            "INFO",
            "Thin history with meaningful balance",
            "Few transactions but non-trivial balance — undeveloped history.",
            "Soft behavioural signal only.",
            signal_type="behavioral",
            confidence="low",
        )

    if tx_list:
        recent = [tx for tx in tx_list if (now - float(tx.get("timestamp") or 0)) < 3600]
        if len(recent) > 10:
            behavioral_score += 12
            add_factor(
                "INFO",
                "High velocity (>10 tx in 1h)",
                f"{len(recent)} transactions in the last hour.",
                "May indicate automation; soft signal.",
                signal_type="behavioral",
                confidence="low",
            )

        # Round amounts only as amplifier when external signal exists
        round_vals = 0
        for tx in tx_list:
            try:
                val = float(str(tx.get("value", "0")).split()[0])
                if val > 10 and val % 10 == 0:
                    round_vals += 1
            except ValueError:
                pass
        if round_vals > 2 and has_external_signal:
            behavioral_score += 5
            add_factor(
                "INFO",
                "Round-amount pattern (amplifier)",
                "Repeated round amounts alongside external risk signals.",
                "Amplifier only — common in stablecoin P2P.",
                signal_type="behavioral",
                confidence="low",
            )

    # Cap pure behavioural contribution
    if not has_external_signal:
        behavioral_score = min(behavioral_score, 19)  # stays under CAUTION threshold floor
        score = behavioral_score
        meta["behavioural_cap_applied"] = True
    else:
        score += behavioral_score
        meta["behavioural_cap_applied"] = False

    meta["has_external_signal"] = has_external_signal
    score = max(0, min(int(score), 99 if not has_external_signal else min(int(score), 99)))

    # Level mapping — pure behavioural never above CAUTION
    if score >= 75:
        level = "CRITICAL"
    elif score >= 40:
        level = "WARNING"
    elif score >= 20:
        level = "CAUTION"
    else:
        level = "SAFE"

    if not has_external_signal and level in ("WARNING", "CRITICAL"):
        level = "CAUTION"
        score = min(score, 39)

    return score, factors, level, meta
