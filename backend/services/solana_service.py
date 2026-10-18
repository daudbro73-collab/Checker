"""Solana blockchain service.
Provides:
- Native SOL balance (via getBalance)
- SPL USDT & USDC balances (via getTokenAccountsByOwner)
- Fake Token Mint detection (Anti-Scam Shield for Solana)
- Transaction history and parsed counterparty transfers
- Memo / Phishing program spam filtering
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
import httpx

from services.solana_address import validate_solana_address

logger = logging.getLogger("aml.solana_service")

# Official Solana SPL Stablecoin Mints
USDT_SOL_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
USDC_SOL_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Memo spam & phishing filter keywords
_SPAM_KEYWORDS = re.compile(
    r"(t\.me/|claim|airdrop|free\s*sol|free\s*usdt|bonus|gift|giveaway|reward|drainer|presale|whitelist|\.io|\.xyz|\.top|\.click)",
    re.IGNORECASE,
)


class SolanaService:
    RPC_ENDPOINTS = [
        "https://api.mainnet-beta.solana.com",
        "https://solana-rpc.publicnode.com",
    ]

    @classmethod
    async def _rpc_call(cls, method: str, params: list, timeout: float = 9.0) -> Optional[Any]:
        """Execute a JSON-RPC call with automatic fallback across public endpoints."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        for endpoint in cls.RPC_ENDPOINTS:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(endpoint, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        if "result" in data:
                            return data["result"]
                        if "error" in data:
                            logger.warning("Solana RPC error from %s on %s: %s", endpoint, method, data["error"])
            except Exception as e:
                logger.debug("Solana RPC endpoint %s failed for %s: %s", endpoint, method, e)
                continue
        return None

    @classmethod
    async def get_wallet_stats(cls, address: str) -> Dict[str, Any]:
        """
        Gathers comprehensive on-chain stats for a Solana address.
        """
        ok, err = validate_solana_address(address)
        if not ok:
            return {
                "chain": "SOL",
                "address": address,
                "balance": 0.0,
                "balance_native_symbol": "SOL",
                "balance_usdt": 0.0,
                "tx_count": 0,
                "tx_list": [],
                "error": err or "Invalid Solana address",
            }

        # 1. Native SOL Balance (lamports / 1e9)
        balance_sol = 0.0
        bal_res = await cls._rpc_call("getBalance", [address])
        if bal_res and isinstance(bal_res, dict) and "value" in bal_res:
            balance_sol = round(bal_res["value"] / 1e9, 6)

        # 2. SPL Token Accounts (USDT, USDC, Fake Tokens)
        balance_usdt = 0.0
        balance_usdc = 0.0
        fake_tokens = []
        token_accounts_res = await cls._rpc_call(
            "getTokenAccountsByOwner",
            [address, {"programId": TOKEN_PROGRAM_ID}, {"encoding": "jsonParsed"}]
        )

        if token_accounts_res and isinstance(token_accounts_res, dict):
            for item in token_accounts_res.get("value", []):
                try:
                    info = item.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    mint = info.get("mint", "")
                    amt_info = info.get("tokenAmount", {})
                    ui_amt = float(amt_info.get("uiAmount") or 0.0)

                    if mint == USDT_SOL_MINT:
                        balance_usdt += ui_amt
                    elif mint == USDC_SOL_MINT:
                        balance_usdc += ui_amt
                    elif ui_amt > 0:
                        # Check for fake USDT / scam tokens
                        token_str = str(info).lower()
                        if "usdt" in token_str or "tether" in token_str:
                            fake_tokens.append({
                                "symbol": "USDT",
                                "impersonating": "USDT",
                                "contract": mint,
                                "balance": ui_amt,
                                "note": f"Поддельный SPL-токен USDT с неофициальным минт-контрактом {mint[:8]}...",
                            })
                except Exception as e:
                    logger.debug("Error parsing Solana token account: %s", e)

        # 3. Transaction Signatures & Memo Spam Filter
        tx_list = []
        spam_filtered = 0
        sig_res = await cls._rpc_call("getSignaturesForAddress", [address, {"limit": 25}])

        if sig_res and isinstance(sig_res, list):
            for s in sig_res:
                sig_hash = s.get("signature")
                memo = s.get("memo") or ""
                block_time = s.get("blockTime") or 0
                err_val = s.get("err")

                # Filter spam/phishing memos
                if memo and _SPAM_KEYWORDS.search(memo):
                    spam_filtered += 1
                    continue

                tx_list.append({
                    "hash": sig_hash,
                    "timestamp": block_time,
                    "from": "",
                    "to": address,
                    "value": "0.0 SOL",
                    "status": "success" if err_val is None else "failed",
                    "memo": memo if memo else None,
                })

        # Enrich up to 5 recent transactions with actual amounts and counterparties
        enriched_count = 0
        for tx in tx_list[:5]:
            sig = tx["hash"]
            tx_detail = await cls._rpc_call(
                "getTransaction",
                [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
            )
            if tx_detail and isinstance(tx_detail, dict):
                try:
                    meta = tx_detail.get("meta", {})
                    msg = tx_detail.get("transaction", {}).get("message", {})
                    keys = [k.get("pubkey") if isinstance(k, dict) else str(k) for k in msg.get("accountKeys", [])]
                    if keys:
                        sender = keys[0]
                        tx["from"] = sender
                        if len(keys) > 1 and sender.lower() == address.lower():
                            tx["to"] = keys[1]
                        
                        # Calculate SOL transfer value from pre/post balances
                        pre_bals = meta.get("preBalances", [])
                        post_bals = meta.get("postBalances", [])
                        if len(pre_bals) > 0 and len(post_bals) > 0:
                            diff = abs(pre_bals[0] - post_bals[0]) / 1e9
                            tx["value"] = f"{diff:.4f} SOL"
                        enriched_count += 1
                except Exception as e:
                    logger.debug("Failed parsing Solana tx %s: %s", sig, e)

        tx_count = len(sig_res) if sig_res else len(tx_list)

        return {
            "chain": "SOL",
            "address": address,
            "type": "SOL",
            "balance": balance_sol,
            "balance_display": f"{balance_sol:.4f} SOL",
            "balance_native_symbol": "SOL",
            "balance_usdt": round(balance_usdt, 2),
            "balance_usdc": round(balance_usdc, 2),
            "fake_tokens": fake_tokens,
            "tx_count": tx_count,
            "tx_list": tx_list,
            "spam_transactions_filtered": spam_filtered,
            "explorer_url": f"https://solscan.io/account/{address}",
        }

    @classmethod
    async def verify_tx(cls, signature: str, expected_dest: str) -> Dict[str, Any]:
        """
        Verify on-chain that a Solana transaction transferred USDT SPL tokens to expected_dest.
        Checks both token balances delta (postTokenBalances vs preTokenBalances)
        and parsed SPL token instructions (transfer / transferChecked).
        """
        signature = (signature or "").strip()
        expected_dest = (expected_dest or "").strip()
        if not signature or not expected_dest:
            return {"verified": False, "error": "Signature and expected destination required"}

        tx_detail = await cls._rpc_call(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
        )
        if not tx_detail or not isinstance(tx_detail, dict):
            return {"verified": False, "error": "Transaction not found on Solana"}

        meta = tx_detail.get("meta") or {}
        if meta.get("err") is not None:
            return {"verified": False, "error": f"Transaction failed on Solana: {meta.get('err')}"}

        block_time = tx_detail.get("blockTime")
        if block_time:
            now_ts = datetime.now(timezone.utc).timestamp()
            if (now_ts - block_time) > 7200:
                return {"verified": False, "error": "Transaction expired (older than 2 hours)"}

        msg = tx_detail.get("transaction", {}).get("message", {})
        account_keys = [k.get("pubkey") if isinstance(k, dict) else str(k) for k in msg.get("accountKeys", [])]
        sender = account_keys[0] if account_keys else "Unknown"

        # 1. Search postTokenBalances vs preTokenBalances
        post_tokens = meta.get("postTokenBalances") or []
        pre_tokens = meta.get("preTokenBalances") or []
        pre_map = {
            f"{t.get('accountIndex')}_{t.get('mint')}": float(
                (t.get("uiTokenAmount") or {}).get("uiAmount") or 0.0
            )
            for t in pre_tokens
        }

        for pt in post_tokens:
            mint = pt.get("mint", "")
            owner = pt.get("owner", "")
            if owner.lower() == expected_dest.lower() and mint == USDT_SOL_MINT:
                post_amt = float((pt.get("uiTokenAmount") or {}).get("uiAmount") or 0.0)
                idx = pt.get("accountIndex")
                pre_amt = pre_map.get(f"{idx}_{mint}", 0.0)
                diff = round(post_amt - pre_amt, 2)
                if diff > 0:
                    return {
                        "verified": True,
                        "amount": diff,
                        "currency": "USDT",
                        "sender": sender,
                    }

        # 2. Check parsed instructions (spl-token transfer / transferChecked)
        instructions = msg.get("instructions", []) + (meta.get("innerInstructions", []) or [])
        for item in instructions:
            ixs = item.get("instructions", [item]) if "instructions" in item else [item]
            for ix in ixs:
                parsed = ix.get("parsed") if isinstance(ix, dict) else None
                if isinstance(parsed, dict) and parsed.get("type") in ("transfer", "transferChecked"):
                    info = parsed.get("info", {})
                    dest = info.get("destination", "")
                    amt_str = (
                        info.get("tokenAmount", {}).get("uiAmount")
                        if "tokenAmount" in info
                        else info.get("amount")
                    )
                    if dest.lower() == expected_dest.lower() or info.get("authority", "").lower() != expected_dest.lower():
                        try:
                            amt = float(amt_str or 0)
                            if amt > 1000 and "tokenAmount" not in info:
                                amt = amt / 1e6
                            if amt > 0:
                                return {
                                    "verified": True,
                                    "amount": amt,
                                    "currency": "USDT",
                                    "sender": sender,
                                }
                        except Exception:
                            pass

        return {"verified": False, "error": "No matching USDT transfer to payment address"}
