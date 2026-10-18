"""TON blockchain service using TonAPI.io.
Provides:
- Native TON balance & Jetton USDT balance
- Decoded transaction history & counterparty flows
- Anti-Address Poisoning detection (spoofing attacks)
- Memo / Payload spam & phishing filtering
"""
import logging
import os
import re
from typing import Dict, Any, List, Optional
import httpx

from services.ton_address import parse_and_validate_ton_address

logger = logging.getLogger("aml.ton_service")

# Official Tether USD₮ Jetton Master Contract on TON
USDT_TON_MASTER_RAW = "0:b113a994b5024a16719f69139328eb759596c38a25f59028b146fecdc3621dfe"
USDT_TON_MASTER_BOUNCEABLE = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"

_SPAM_KEYWORDS = re.compile(
    r"(t\.me/|claim|airdrop|free\s*ton|free\s*usdt|bonus|gift|giveaway|reward|drainer|presale|whitelist)",
    re.IGNORECASE,
)


def detect_address_poisoning(
    target_addr: str,
    incoming_txs: List[Dict[str, Any]],
    all_counterparties: List[str],
) -> List[Dict[str, Any]]:
    """
    Detects Address Poisoning Attacks.
    Scammers generate vanity addresses with matching prefix and suffix
    and send dust transactions to place the fake address in victim's history.
    """
    poisoning_alerts = []
    # Only compare against established counterparties
    frequent_contacts = [cp for cp in all_counterparties if cp and len(cp) >= 40]

    for tx in incoming_txs:
        sender = tx.get("from") or ""
        try:
            val = float(str(tx.get("value", "0")).split()[0])
        except (ValueError, TypeError):
            val = 0.0
        # Poisoning attacks are almost always dust (< 0.05 TON or < 0.1 USDT)
        if val > 0.05 or len(sender) < 40:
            continue

        for contact in frequent_contacts:
            if contact.lower() == sender.lower():
                continue
            # Check 4-character prefix and suffix collision
            prefix_match = sender[:4].lower() == contact[:4].lower()
            suffix_match = sender[-4:].lower() == contact[-4:].lower()
            if prefix_match and suffix_match:
                poisoning_alerts.append({
                    "fake_sender": sender,
                    "target_contact": contact,
                    "dust_amount": val,
                    "tx_hash": tx.get("hash"),
                    "note": f"Адрес {sender[:6]}...{sender[-4:]} имитирует контакт {contact[:6]}...{contact[-4:]}",
                })
                break

    return poisoning_alerts


class TonService:
    BASE_URL = "https://tonapi.io/v2"

    @staticmethod
    def _headers() -> Dict[str, str]:
        token = os.getenv("TONAPI_KEY", "")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @classmethod
    async def get_stats(cls, address: str) -> Dict[str, Any]:
        """Fetch full TON account state, Jetton balances, and transaction graph data."""
        ok, err, parsed = parse_and_validate_ton_address(address)
        if not ok or not parsed:
            return {"error": f"Invalid TON address: {err}"}

        raw_addr = parsed["raw"]
        friendly_addr = parsed["bounceable"]
        non_bounceable = parsed["non_bounceable"]

        headers = cls._headers()
        balance_ton = 0.0
        balance_usdt = 0.0
        is_scam = False
        status = "uninit"
        tx_list = []
        graph_data = []
        verified_jettons = []
        spam_transactions = []
        all_incoming = []
        seen_counterparties = set()

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Account details
            try:
                r_acc = await client.get(f"{cls.BASE_URL}/accounts/{raw_addr}", headers=headers)
                if r_acc.status_code == 200:
                    data = r_acc.json()
                    balance_ton = float(data.get("balance", 0) or 0) / 1e9
                    is_scam = bool(data.get("is_scam"))
                    status = data.get("status", "active")
            except Exception as e:
                logger.warning("TonAPI account query failed: %s", e)

            # 2. Jetton balances (USDT and others)
            try:
                r_jet = await client.get(f"{cls.BASE_URL}/accounts/{raw_addr}/jettons", headers=headers)
                if r_jet.status_code == 200:
                    jet_data = r_jet.json().get("balances") or []
                    for item in jet_data:
                        jetton = item.get("jetton") or {}
                        symbol = (jetton.get("symbol") or "").upper()
                        master = (jetton.get("address") or "").lower()
                        raw_val = item.get("balance") or 0
                        decimals = int(jetton.get("decimals") or 6)
                        j_bal = float(raw_val) / (10 ** decimals)

                        # Check Tether USD₮
                        if "USD" in symbol or master in (USDT_TON_MASTER_RAW.lower(), USDT_TON_MASTER_BOUNCEABLE.lower()):
                            balance_usdt = j_bal
                            verified_jettons.append({
                                "symbol": "USD₮",
                                "name": "Tether USD₮ (TON)",
                                "balance": j_bal,
                                "contract": master,
                                "verified": True,
                            })
                        else:
                            verified_jettons.append({
                                "symbol": symbol,
                                "name": jetton.get("name"),
                                "balance": j_bal,
                                "contract": master,
                                "verified": jetton.get("verification") == "whitelist",
                            })
            except Exception as e:
                logger.warning("TonAPI jettons query failed: %s", e)

            # 3. Events & Decoded Transfers
            try:
                r_ev = await client.get(f"{cls.BASE_URL}/accounts/{raw_addr}/events?limit=30", headers=headers)
                if r_ev.status_code == 200:
                    events = r_ev.json().get("events") or []
                    for ev in events:
                        actions = ev.get("actions") or []
                        timestamp = float(ev.get("timestamp") or 0)
                        tx_hash = ev.get("event_id")

                        for act in actions:
                            act_type = act.get("type")
                            sender_addr = ""
                            recipient_addr = ""
                            amount = 0.0
                            currency = "TON"
                            comment = ""

                            if act_type == "TonTransfer":
                                detail = act.get("TonTransfer") or {}
                                sender_data = detail.get("sender") or {}
                                recipient_data = detail.get("recipient") or {}
                                sender_addr = sender_data.get("address") or ""
                                recipient_addr = recipient_data.get("address") or ""
                                amount = float(detail.get("amount", 0) or 0) / 1e9
                                currency = "TON"
                                comment = detail.get("comment") or ""

                            elif act_type == "JettonTransfer":
                                detail = act.get("JettonTransfer") or {}
                                sender_data = detail.get("sender") or {}
                                recipient_data = detail.get("recipient") or {}
                                sender_addr = sender_data.get("address") or ""
                                recipient_addr = recipient_data.get("address") or ""
                                jetton_info = detail.get("jetton") or {}
                                decimals = int(jetton_info.get("decimals") or 6)
                                amount = float(detail.get("amount", 0) or 0) / (10 ** decimals)
                                currency = jetton_info.get("symbol") or "JETTON"
                                comment = detail.get("comment") or ""

                            if not sender_addr or not recipient_addr:
                                continue

                            # Normalize to raw for internal mapping
                            sender_raw = sender_addr.lower()
                            recipient_raw = recipient_addr.lower()
                            target_is_recipient = recipient_raw == raw_addr.lower()

                            # Convert to friendly address for display
                            _, _, s_info = parse_and_validate_ton_address(sender_addr)
                            _, _, r_info = parse_and_validate_ton_address(recipient_addr)
                            s_disp = s_info["bounceable"] if s_info else sender_addr
                            r_disp = r_info["bounceable"] if r_info else recipient_addr

                            counterparty = s_disp if target_is_recipient else r_disp
                            seen_counterparties.add(counterparty)

                            # Check for memo-spam / phishing in comment
                            is_spam = False
                            if comment and _SPAM_KEYWORDS.search(comment) and amount < 0.05:
                                is_spam = True
                                spam_transactions.append({
                                    "from": s_disp,
                                    "amount": amount,
                                    "comment": comment,
                                    "tx_hash": tx_hash,
                                })

                            tx_item = {
                                "hash": tx_hash,
                                "method": act_type,
                                "from": s_disp,
                                "to": r_disp,
                                "value": f"{amount:.4f} {currency}",
                                "currency": currency,
                                "timestamp": timestamp,
                                "comment": comment,
                                "is_spam": is_spam,
                                "explorer_url": f"https://tonviewer.com/transaction/{tx_hash}",
                            }

                            if not is_spam:
                                tx_list.append(tx_item)
                                graph_data.append({
                                    "source": s_disp,
                                    "target": r_disp,
                                    "value": amount,
                                    "currency": currency,
                                    "hash": tx_hash,
                                    "timestamp": timestamp * 1000,
                                })
                            if target_is_recipient:
                                all_incoming.append(tx_item)
            except Exception as e:
                logger.warning("TonAPI events query failed: %s", e)

        # Run Anti-Address Poisoning detection
        poisoning_attacks = detect_address_poisoning(
            friendly_addr, all_incoming, list(seen_counterparties)
        )

        return {
            "balance": balance_ton,
            "balance_usdt": balance_usdt,
            "balance_native_symbol": "TON",
            "balance_display": f"{balance_ton:.4f} TON",
            "tx_count": len(tx_list),
            "is_contract": False,
            "type": "TON",
            "explorer_link": "https://tonviewer.com",
            "graph_data": graph_data,
            "tx_list": tx_list,
            "ton_status": status,
            "is_scam": is_scam,
            "raw_address": raw_addr,
            "bounceable_address": friendly_addr,
            "non_bounceable_address": non_bounceable,
            "verified_jettons": verified_jettons,
            "spam_transactions_filtered": len(spam_transactions),
            "spam_transactions": spam_transactions,
            "address_poisoning_attacks": poisoning_attacks,
            "anti_poisoning_shield_active": True,
        }
