import httpx
from datetime import datetime, timezone
from services.token_security import evaluate_token_balances
from services.ton_service import TonService
from services.solana_service import SolanaService


from services.redis_client import cache_json_get, cache_json_set


class ChainService:
    RPC_URLS = {
        "ETH": "https://rpc.ankr.com/eth",
        "BSC": "https://rpc.ankr.com/bsc",
    }

    BLOCKSCOUT = {
        "ETH": "https://eth.blockscout.com/api/v2",
        "BSC": "https://bsc.blockscout.com/api/v2",
    }

    WEB_EXPLORERS = {
        "ETH": "https://eth.blockscout.com",
        "BSC": "https://bscscan.com",
        "TON": "https://tonviewer.com",
        "SOL": "https://solscan.io",
    }

    @staticmethod
    async def get_transactions(chain: str, address: str, limit: int = 10):
        chain_norm = (chain or "").upper()
        addr_clean = address.lower() if chain_norm in ("ETH", "BSC", "BTC") else address
        cache_key = f"rpc:txs:{chain_norm}:{addr_clean}:{limit}"

        cached = cache_json_get(cache_key)
        if cached is not None:
            return cached

        res = []
        if chain_norm == "TRON":
            res = await ChainService._get_tron_txs_only(address, limit)
        elif chain_norm in ("ETH", "BSC"):
            res = await ChainService._get_evm_txs_only(chain_norm, address, limit)
        elif chain_norm == "TON":
            stats = await TonService.get_stats(address)
            res = (stats.get("graph_data") or [])[:limit]
        elif chain_norm == "SOL":
            stats = await SolanaService.get_wallet_stats(address)
            res = (stats.get("tx_list") or [])[:limit]
        elif chain_norm == "BTC":
            stats = await ChainService._get_btc_stats(address)
            res = (stats.get("graph_data") or [])[:limit]

        if res:
            cache_json_set(cache_key, res, ttl_seconds=300)
        return res

    @staticmethod
    async def _get_evm_txs_only(chain: str, address: str, limit: int):
        base_url = ChainService.BLOCKSCOUT.get(chain)
        if not base_url:
            return []
        try:
            async with httpx.AsyncClient() as client:
                resp_txs = await client.get(f"{base_url}/addresses/{address}/transactions", timeout=8.0)
                graph_data = []
                if resp_txs.status_code == 200:
                    for tx in (resp_txs.json().get("items") or [])[:limit]:
                        if not isinstance(tx, dict):
                            continue
                        sender_data = tx.get("from")
                        receiver_data = tx.get("to")
                        sender = sender_data.get("hash") if isinstance(sender_data, dict) else str(sender_data)
                        receiver = receiver_data.get("hash") if isinstance(receiver_data, dict) else str(receiver_data)
                        val = float(tx.get("value", 0)) / 1e18
                        graph_data.append({
                            "source": sender,
                            "target": receiver,
                            "value": val,
                            "currency": chain,
                            "hash": tx.get("hash"),
                            "timestamp": tx.get("timestamp"),
                        })
                return graph_data
        except Exception:
            return []

    @staticmethod
    async def _get_tron_txs_only(address: str, limit: int):
        base_url = "https://api.trongrid.io/v1/accounts"
        try:
            async with httpx.AsyncClient() as client:
                resp_txs = await client.get(f"{base_url}/{address}/transactions", params={"limit": limit}, timeout=8.0)
                graph_data = []
                if resp_txs.status_code == 200:
                    for tx in (resp_txs.json().get("data") or []):
                        tx_hash = tx.get("txID")
                        raw = tx.get("raw_data", {})
                        contract = raw.get("contract", [{}])[0]
                        val_data = contract.get("parameter", {}).get("value", {})
                        amount = float(val_data.get("amount", 0)) / 1_000_000
                        sender = val_data.get("owner_address")
                        receiver = val_data.get("to_address")
                        if sender and receiver:
                            graph_data.append({
                                "source": sender,
                                "target": receiver,
                                "value": amount,
                                "currency": "TRX",
                                "hash": tx_hash,
                            })
                return graph_data
        except Exception:
            return []

    @staticmethod
    async def get_stats(chain: str, address: str):
        if chain == "BTC":
            return await ChainService._get_btc_stats(address)
        if chain == "TRON":
            return await ChainService._get_tron_stats(address)
        if chain == "BSC":
            return await ChainService._get_bsc_stats(address)
        if chain == "TON":
            return await TonService.get_stats(address)
        if chain == "SOL":
            return await SolanaService.get_wallet_stats(address)
        if chain == "ETH":
            return await ChainService._get_evm_stats(chain, address)
        return {"error": "Unsupported chain"}

    @staticmethod
    async def refresh_balances(chain: str, address: str, data: dict) -> dict:
        """Light refresh of native/USDT balances on a cached payload."""
        if not isinstance(data, dict) or data.get("error"):
            return data
        try:
            if chain == "TRON":
                bal = await ChainService._fetch_tron_balances(address)
                if bal:
                    data["balance"] = bal.get("balance", data.get("balance", 0))
                    data["balance_usdt"] = bal.get("balance_usdt", data.get("balance_usdt", 0))
                    data["other_trc20_contracts"] = bal.get(
                        "other_trc20_contracts",
                        data.get("other_trc20_contracts", 0),
                    )
            elif chain == "BSC":
                bal = await ChainService._fetch_bsc_balances(address)
                if bal:
                    data["balance"] = bal.get("balance", data.get("balance", 0))
                    data["balance_usdt"] = bal.get("balance_usdt", data.get("balance_usdt", 0))
            elif chain == "TON":
                res = await TonService.get_stats(address)
                if res and not res.get("error"):
                    data["balance"] = res.get("balance", data.get("balance", 0))
                    data["balance_usdt"] = res.get("balance_usdt", data.get("balance_usdt", 0))
            elif chain == "SOL":
                res = await SolanaService.get_wallet_stats(address)
                if res and not res.get("error"):
                    data["balance"] = res.get("balance", data.get("balance", 0))
                    data["balance_usdt"] = res.get("balance_usdt", data.get("balance_usdt", 0))
                    data["balance_usdc"] = res.get("balance_usdc", data.get("balance_usdc", 0))
            elif chain == "ETH":
                bal = await ChainService._fetch_evm_balances(chain, address)
                if bal:
                    data["balance"] = bal.get("balance", data.get("balance", 0))
                    data["balance_usdt"] = bal.get("balance_usdt", data.get("balance_usdt", 0))
            elif chain == "BTC":
                bal = await ChainService._fetch_btc_balance(address)
                if bal is not None:
                    data["balance"] = bal
        except Exception:
            pass
        return data

    @staticmethod
    async def _fetch_tron_balances(address: str) -> dict | None:
        usdt_contract = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.trongrid.io/v1/accounts/{address}", timeout=6.0)
                if resp.status_code != 200:
                    return None
                payload = resp.json()
                rows = payload.get("data") or []
                if not rows:
                    return {"balance": 0, "balance_usdt": 0, "other_trc20_contracts": 0}
                acc = rows[0]
                balance_trx = (acc.get("balance", 0) or 0) / 1_000_000
                balance_usdt = 0.0
                other_trc20 = 0
                for item in acc.get("trc20") or []:
                    if not isinstance(item, dict):
                        continue
                    for k, v in item.items():
                        if k == usdt_contract:
                            balance_usdt = float(v) / 1_000_000
                        else:
                            other_trc20 += 1
                return {
                    "balance": balance_trx,
                    "balance_usdt": balance_usdt,
                    "other_trc20_contracts": other_trc20,
                }
        except Exception:
            return None

    @staticmethod
    async def _fetch_evm_balances(chain: str, address: str) -> dict | None:
        base_url = ChainService.BLOCKSCOUT.get(chain)
        if not base_url:
            return None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{base_url}/addresses/{address}", timeout=6.0)
                if resp.status_code != 200:
                    return None
                info = resp.json()
                if not isinstance(info, dict):
                    info = {}
                balance = float(info.get("coin_balance", 0) or 0) / 1e18
                balance_usdt = 0.0
                try:
                    tok = await client.get(f"{base_url}/addresses/{address}/token-balances", timeout=6.0)
                    if tok.status_code == 200:
                        for t in tok.json() or []:
                            token = (t.get("token") or {}) if isinstance(t, dict) else {}
                            symbol = (token.get("symbol") or "").upper()
                            if symbol in ("USDT", "BSC-USD"):
                                decimals = int(token.get("decimals") or (18 if chain == "BSC" else 6))
                                balance_usdt = float(t.get("value") or 0) / (10 ** decimals)
                                break
                except Exception:
                    pass
                return {"balance": balance, "balance_usdt": balance_usdt}
        except Exception:
            return None

    @staticmethod
    async def _fetch_eth_balances(address: str) -> dict | None:
        return await ChainService._fetch_evm_balances("ETH", address)

    @staticmethod
    async def _fetch_btc_balance(address: str) -> float | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://blockstream.info/api/address/{address}", timeout=6.0)
                if resp.status_code != 200:
                    return None
                info = resp.json()
                funded = (info.get("chain_stats") or {}).get("funded_txo_sum", 0) or 0
                spent = (info.get("chain_stats") or {}).get("spent_txo_sum", 0) or 0
                return (funded - spent) / 1e8
        except Exception:
            return None

    @staticmethod
    async def _fetch_bsc_balances(address: str) -> dict | None:
        rpc_url = "https://bsc-dataseed1.defibit.io/"
        try:
            async with httpx.AsyncClient() as client:
                p_bal = {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [address, "latest"]}
                r = await client.post(rpc_url, json=p_bal, timeout=5.0)
                balance_bnb = int(r.json().get("result", "0x0"), 16) / 1e18 if r.status_code == 200 else 0.0

                usdt_contract = "0x55d398326f99059ff775485246999027b3197955"
                call_data = "0x70a08231" + address.lower().replace("0x", "").zfill(64)
                p_usdt = {"jsonrpc": "2.0", "id": 2, "method": "eth_call", "params": [{"to": usdt_contract, "data": call_data}, "latest"]}
                r_usdt = await client.post(rpc_url, json=p_usdt, timeout=5.0)
                balance_usdt = 0.0
                if r_usdt.status_code == 200:
                    u_hex = r_usdt.json().get("result", "0x0")
                    if u_hex and u_hex != "0x":
                        balance_usdt = int(u_hex, 16) / 1e18
                return {"balance": balance_bnb, "balance_usdt": balance_usdt}
        except Exception:
            return None

    @staticmethod
    async def _get_bsc_stats(address: str):
        rpc_url = "https://bsc-dataseed1.defibit.io/"
        web_base = "https://bscscan.com"

        balance_bnb = 0.0
        balance_usdt = 0.0
        is_contract = False
        tx_list = []
        graph_data = []
        asset_validity = {"has_fake_assets": False, "fake_tokens": [], "verified_tokens": []}

        # 1. Native BNB Balance & Contract check via free public RPC
        async with httpx.AsyncClient() as client:
            try:
                p_bal = {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [address, "latest"]}
                r = await client.post(rpc_url, json=p_bal, timeout=6.0)
                if r.status_code == 200:
                    raw_hex = r.json().get("result") or "0x0"
                    balance_bnb = int(raw_hex, 16) / 1e18

                p_code = {"jsonrpc": "2.0", "id": 2, "method": "eth_getCode", "params": [address, "latest"]}
                r_code = await client.post(rpc_url, json=p_code, timeout=6.0)
                if r_code.status_code == 200:
                    code_res = r_code.json().get("result") or "0x"
                    is_contract = len(code_res) > 2

                # 2. Binance-Peg USDT Balance
                usdt_contract = "0x55d398326f99059ff775485246999027b3197955"
                call_data = "0x70a08231" + address.lower().replace("0x", "").zfill(64)
                p_usdt = {"jsonrpc": "2.0", "id": 3, "method": "eth_call", "params": [{"to": usdt_contract, "data": call_data}, "latest"]}
                r_usdt = await client.post(rpc_url, json=p_usdt, timeout=6.0)
                if r_usdt.status_code == 200:
                    u_hex = r_usdt.json().get("result") or "0x0"
                    if u_hex and u_hex != "0x":
                        balance_usdt = int(u_hex, 16) / 1e18
                        if balance_usdt > 0:
                            asset_validity["verified_tokens"].append({
                                "symbol": "USDT",
                                "name": "Binance-Peg BSC-USD",
                                "contract": usdt_contract,
                                "balance": balance_usdt,
                                "status": "GENUINE",
                            })
            except Exception as e:
                pass

            # 3. Optional BscScan API V2 if key is configured
            import os
            bsc_key = os.getenv("BSCSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY")
            if bsc_key:
                try:
                    tx_url = f"https://api.etherscan.io/v2/api?chainid=56&module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=50&sort=desc&apikey={bsc_key}"
                    r_tx = await client.get(tx_url, timeout=8.0)
                    if r_tx.status_code == 200:
                        items = r_tx.json().get("result") or []
                        if isinstance(items, list):
                            for tx in items[:50]:
                                if not isinstance(tx, dict):
                                    continue
                                sender = tx.get("from")
                                receiver = tx.get("to")
                                val = float(tx.get("value", 0) or 0) / 1e18
                                ts_ms = float(tx.get("timeStamp", 0) or 0) * 1000
                                tx_hash = tx.get("hash")
                                graph_data.append({
                                    "source": sender,
                                    "target": receiver,
                                    "value": val,
                                    "currency": "BNB",
                                    "hash": tx_hash,
                                    "timestamp": ts_ms,
                                })
                                tx_list.append({
                                    "hash": tx_hash,
                                    "method": tx.get("functionName", "transfer"),
                                    "from": sender,
                                    "to": receiver,
                                    "value": f"{val:.4f} BNB",
                                    "timestamp": ts_ms / 1000,
                                    "explorer_url": f"{web_base}/tx/{tx_hash}",
                                })
                except Exception:
                    pass

        return {
            "balance": balance_bnb,
            "balance_usdt": balance_usdt,
            "balance_native_symbol": "BNB",
            "balance_display": f"{balance_bnb:.4f} BNB",
            "tx_count": len(tx_list),
            "is_contract": is_contract,
            "type": "EVM",
            "explorer_link": web_base,
            "graph_data": graph_data,
            "tx_list": tx_list,
            "asset_validity": asset_validity,
            "fake_tokens": asset_validity.get("fake_tokens", []),
        }

    @staticmethod
    async def _get_evm_stats(chain: str, address: str):
        base_url = ChainService.BLOCKSCOUT.get(chain)
        web_base = ChainService.WEB_EXPLORERS.get(chain, "")
        if not base_url:
            return {"error": f"No real data provider configured for {chain}"}

        try:
            async with httpx.AsyncClient() as client:
                resp_info = await client.get(f"{base_url}/addresses/{address}", timeout=8.0)
                balance = 0
                tx_count = 0
                is_contract = False

                if resp_info.status_code == 404:
                    return {"error": "Address not found on explorer"}
                if resp_info.status_code != 200:
                    return {"error": f"Explorer unavailable (HTTP {resp_info.status_code})"}

                data = resp_info.json()
                if isinstance(data, dict):
                    balance = float(data.get("coin_balance", 0) or 0) / 1e18
                    is_contract = data.get("is_contract", False)

                resp_txs = await client.get(f"{base_url}/addresses/{address}/transactions", timeout=12.0)
                graph_data = []
                tx_list = []

                if resp_txs.status_code == 200:
                    items = resp_txs.json().get("items") or []
                    tx_count = len(items)
                    for tx in items[:50]:
                        if not isinstance(tx, dict):
                            continue
                        sender_data = tx.get("from")
                        receiver_data = tx.get("to")
                        sender = sender_data.get("hash") if isinstance(sender_data, dict) else str(sender_data)
                        receiver = receiver_data.get("hash") if isinstance(receiver_data, dict) else str(receiver_data)
                        val = float(tx.get("value", 0) or 0) / 1e18
                        raw_ts = tx.get("timestamp")
                        ts_ms = 0
                        if isinstance(raw_ts, str):
                            try:
                                dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                                ts_ms = dt.timestamp() * 1000
                            except Exception:
                                pass
                        elif isinstance(raw_ts, (int, float)):
                            ts_ms = raw_ts * 1000 if raw_ts < 1e11 else raw_ts

                        graph_data.append({
                            "source": sender,
                            "target": receiver,
                            "value": val,
                            "currency": chain,
                            "hash": tx.get("hash"),
                            "timestamp": ts_ms,
                            "method": tx.get("method"),
                        })
                        tx_list.append({
                            "hash": tx.get("hash"),
                            "method": tx.get("method"),
                            "from": sender,
                            "to": receiver,
                            "value": f"{val:.4f} {chain}",
                            "timestamp": ts_ms / 1000,
                            "explorer_url": f"{web_base}/tx/{tx.get('hash')}",
                        })

                # Token transfers (USDT etc.) — native ETH graph alone looks like "0.00 Coin"
                try:
                    resp_tt = await client.get(
                        f"{base_url}/addresses/{address}/token-transfers",
                        params={"type": "ERC-20"},
                        timeout=10.0,
                    )
                    if resp_tt.status_code == 200:
                        for tt in (resp_tt.json().get("items") or [])[:50]:
                            if not isinstance(tt, dict):
                                continue
                            frm = tt.get("from") or {}
                            to = tt.get("to") or {}
                            sender = frm.get("hash") if isinstance(frm, dict) else str(frm)
                            receiver = to.get("hash") if isinstance(to, dict) else str(to)
                            token = tt.get("token") or {}
                            decimals = int(token.get("decimals") or 18)
                            symbol = token.get("symbol") or "TOKEN"
                            total = tt.get("total") or {}
                            raw = total.get("value") if isinstance(total, dict) else total
                            try:
                                tval = float(raw or 0) / (10 ** decimals)
                            except (TypeError, ValueError):
                                tval = 0.0
                            if tval <= 0 or not sender or not receiver:
                                continue
                            tx_hash = tt.get("tx_hash") or tt.get("transaction_hash") or tt.get("hash")
                            graph_data.append({
                                "source": sender,
                                "target": receiver,
                                "value": tval,
                                "currency": symbol,
                                "hash": tx_hash,
                                "timestamp": 0,
                                "method": "token_transfer",
                            })
                            tx_list.append({
                                "hash": tx_hash,
                                "method": "token_transfer",
                                "from": sender,
                                "to": receiver,
                                "value": f"{tval:.4f} {symbol}",
                                "timestamp": 0,
                                "explorer_url": f"{web_base}/tx/{tx_hash}" if tx_hash else "",
                            })
                except Exception:
                    pass

                # USDT (ERC-20 / BEP-20) balance & Asset Validity (Fake Token / Clone check)
                balance_usdt = 0.0
                asset_validity = {"has_fake_assets": False, "fake_tokens": [], "verified_tokens": []}
                try:
                    usdt_addrs = {
                        "0xdac17f958d2ee523a2206206994597c13d831ec7",  # ETH USDT
                        "0x55d398326f99059ff775485246999027b3197955",  # BSC USDT (BSC-USD)
                    }
                    resp_bal = await client.get(
                        f"{base_url}/addresses/{address}/token-balances",
                        timeout=10.0,
                    )
                    if resp_bal.status_code == 200:
                        token_items = resp_bal.json() or []
                        asset_validity = evaluate_token_balances(chain, token_items)
                        for item in token_items:
                            token = item.get("token") or {}
                            tok_addr = (token.get("address") or "").lower()
                            tok_sym = (token.get("symbol") or "").upper()
                            if tok_addr in usdt_addrs or tok_sym in ("USDT", "BSC-USD"):
                                decimals = int(token.get("decimals") or (18 if chain == "BSC" else 6))
                                balance_usdt = float(item.get("value") or 0) / (10 ** decimals)
                                break
                except Exception:
                    pass

                all_ts = []
                for tx in tx_list:
                    ts_v = tx.get("timestamp")
                    if ts_v:
                        try:
                            ts_f = float(ts_v)
                            if ts_f > 1000000000:
                                all_ts.append(ts_f)
                        except Exception:
                            pass
                first_seen = "—"
                last_active = "—"
                if all_ts:
                    first_seen = datetime.fromtimestamp(min(all_ts), timezone.utc).strftime("%Y-%m-%d")
                    last_active = datetime.fromtimestamp(max(all_ts), timezone.utc).strftime("%Y-%m-%d")

                native_sym = {"ETH": "ETH", "BSC": "BNB", "POLYGON": "MATIC", "AVAX": "AVAX"}.get(chain, chain)
                return {
                    "balance": balance,
                    "balance_usdt": balance_usdt,
                    "balance_native_symbol": native_sym,
                    "balance_display": f"{balance:.4f} {native_sym}",
                    "first_seen": first_seen,
                    "last_active": last_active,
                    "tx_count": tx_count,
                    "is_contract": is_contract,
                    "type": "EVM",
                    "explorer_link": web_base,
                    "graph_data": graph_data,
                    "tx_list": tx_list,
                    "asset_validity": asset_validity,
                    "fake_tokens": asset_validity.get("fake_tokens", []),
                }
        except Exception as e:
            print(f"EVM Blockscout Error: {e}")
            return {"error": f"Chain data unavailable: {e}"}

    @staticmethod
    async def _get_tron_stats(address: str):
        base_url = "https://api.trongrid.io/v1/accounts"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{base_url}/{address}", timeout=8.0)
                if resp.status_code == 400:
                    return {"error": "Invalid TRON address"}
                if resp.status_code != 200:
                    return {"error": f"TronGrid unavailable (HTTP {resp.status_code})"}

                balance_trx = 0
                balance_usdt = 0
                usdt_contract = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
                acc = {}
                data = resp.json()
                if data.get("data"):
                    acc = data["data"][0]
                    balance_trx = acc.get("balance", 0) / 1_000_000
                    for item in acc.get("trc20", []) or []:
                        if usdt_contract in item:
                            balance_usdt = float(item[usdt_contract]) / 1_000_000
                            break

                tx_list = []
                graph_data = []
                trc10_count = len(acc.get("assetV2") or acc.get("asset") or [])
                other_trc20 = 0
                for item in acc.get("trc20") or []:
                    for k in item:
                        if k != usdt_contract:
                            other_trc20 += 1

                resp_txs = await client.get(
                    f"{base_url}/{address}/transactions",
                    params={"limit": 50, "only_confirmed": True},
                    timeout=12.0,
                )
                if resp_txs.status_code == 200:
                    from services.graph import tron_hex_to_base58
                    for tx in (resp_txs.json().get("data") or []):
                        tx_hash = tx.get("txID")
                        timestamp = tx.get("block_timestamp", 0)
                        raw = tx.get("raw_data", {})
                        contract = (raw.get("contract") or [{}])[0]
                        type_ = contract.get("type") or ""
                        val_data = (contract.get("parameter") or {}).get("value") or {}
                        sender = tron_hex_to_base58(val_data.get("owner_address") or "")
                        receiver = tron_hex_to_base58(val_data.get("to_address") or "")
                        if not sender or not receiver:
                            continue

                        if type_ == "TransferContract":
                            # Real TRX
                            amount = float(val_data.get("amount", 0) or 0) / 1_000_000
                            if amount <= 0:
                                continue
                            graph_data.append({
                                "source": sender, "target": receiver, "value": amount,
                                "currency": "TRX", "hash": tx_hash, "timestamp": timestamp,
                            })
                            tx_list.append({
                                "hash": tx_hash, "method": type_, "from": sender, "to": receiver,
                                "value": f"{amount:.6f} TRX", "timestamp": timestamp / 1000,
                                "token": "TRX", "explorer_url": f"https://tronscan.org/#/transaction/{tx_hash}",
                            })
                        elif type_ == "TransferAssetContract":
                            # TRC-10 (often airdrop spam) — NOT TRX. List only, skip graph.
                            asset_id = val_data.get("asset_name") or "TRC10"
                            if isinstance(asset_id, str) and len(asset_id) % 2 == 0 and all(
                                c in "0123456789abcdefABCDEF" for c in asset_id
                            ):
                                try:
                                    asset_id = bytes.fromhex(asset_id).decode("utf-8", errors="ignore") or asset_id
                                except Exception:
                                    pass
                            raw_amt = float(val_data.get("amount", 0) or 0)
                            tx_list.append({
                                "hash": tx_hash, "method": type_, "from": sender, "to": receiver,
                                "value": f"{raw_amt:.0f} {asset_id} (TRC-10)", "timestamp": timestamp / 1000,
                                "token": "TRC10", "explorer_url": f"https://tronscan.org/#/transaction/{tx_hash}",
                            })

                resp_trc20 = await client.get(
                    f"{base_url}/{address}/transactions/trc20",
                    params={"limit": 50, "only_confirmed": True},
                    timeout=12.0,
                )
                if resp_trc20.status_code == 200:
                    for tx in (resp_trc20.json().get("data") or []):
                        tx_hash = tx.get("transaction_id")
                        timestamp = tx.get("block_timestamp", 0)
                        token_info = tx.get("token_info") or {}
                        symbol = token_info.get("symbol", "TRC20")
                        decimals = int(token_info.get("decimals", 6) or 6)
                        amount = float(tx.get("value", 0) or 0) / (10 ** decimals)
                        sender = tx.get("from")
                        receiver = tx.get("to")
                        if not sender or not receiver or amount <= 0:
                            continue
                        # Graph: only real money for TRON — TRX/USDT. Spam TRC-20 stays in tx list only.
                        if (symbol or "").upper() in ("USDT", "USDC") or (
                            (symbol or "").upper() == "TRX"
                        ):
                            graph_data.append({
                                "source": sender, "target": receiver, "value": amount,
                                "currency": symbol, "hash": tx_hash, "timestamp": timestamp,
                            })
                        elif (symbol or "").upper() not in ("USDT", "USDC"):
                            # non-stable spam tokens: list only
                            pass
                        tx_list.append({
                            "hash": tx_hash, "method": tx.get("type", "Transfer"),
                            "from": sender, "to": receiver,
                            "value": f"{amount:.6f} {symbol}", "timestamp": timestamp / 1000,
                            "token": symbol, "explorer_url": f"https://tronscan.org/#/transaction/{tx_hash}",
                        })

                tx_list.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

                # Calculate genuine first_seen and last_active from on-chain history
                all_ts = []
                if acc.get("create_time"):
                    all_ts.append(int(acc.get("create_time")))
                for tx in tx_list:
                    ts_val = tx.get("timestamp")
                    if ts_val:
                        all_ts.append(int(float(ts_val) * 1000))

                first_seen = "—"
                last_active = "—"
                if all_ts:
                    first_seen = datetime.fromtimestamp(min(all_ts) / 1000, timezone.utc).strftime("%Y-%m-%d")
                    last_active = datetime.fromtimestamp(max(all_ts) / 1000, timezone.utc).strftime("%Y-%m-%d")

                note_bits = ["recent sample, not lifetime total"]
                if trc10_count:
                    note_bits.append(f"{trc10_count} TRC-10 assets on account (spam-prone)")
                if other_trc20:
                    note_bits.append(f"{other_trc20} other TRC-20 besides USDT")
                return {
                    "balance": balance_trx,
                    "balance_usdt": balance_usdt,
                    "balance_native_symbol": "TRX",
                    # Native only — USDT is a separate UI row (avoid double display)
                    "balance_display": f"{balance_trx:,.2f} TRX",
                    "first_seen": first_seen,
                    "last_active": last_active,
                    "tx_count": len(tx_list),
                    "tx_count_note": "; ".join(note_bits),
                    "trc10_assets": trc10_count,
                    "other_trc20_contracts": other_trc20,
                    "type": "TRON",
                    "explorer_link": f"https://tronscan.org/#/address/{address}",
                    "graph_data": graph_data,
                    "tx_list": tx_list,
                }
        except Exception as e:
            print(f"TRON Error: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _get_btc_stats(address: str):
        """
        BTC via Esplora-compatible APIs.
        mempool.space often returns 403 without a browser-like User-Agent —
        we send one and fall back to blockstream / blockchain.info.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AMLGuard/1.0; +https://amlguard.local)",
            "Accept": "application/json",
        }
        esplora_bases = (
            "https://mempool.space/api",
            "https://blockstream.info/api",
        )
        last_error = None
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            for base in esplora_bases:
                try:
                    result = await ChainService._btc_from_esplora(client, base, address)
                    if result and not result.get("error"):
                        return result
                    last_error = (result or {}).get("error") or last_error
                except Exception as e:
                    last_error = str(e)
                    print(f"BTC Esplora {base} error: {e}")

            # Last resort: blockchain.info (different JSON shape)
            try:
                result = await ChainService._btc_from_blockchain_info(client, address)
                if result and not result.get("error"):
                    return result
                last_error = (result or {}).get("error") or last_error
            except Exception as e:
                last_error = str(e)
                print(f"BTC blockchain.info error: {e}")

        return {"error": last_error or "All BTC providers unavailable"}

    @staticmethod
    async def _btc_from_esplora(client: httpx.AsyncClient, base: str, address: str):
        url = f"{base}/address/{address}"
        txs_url = f"{base}/address/{address}/txs"
        resp = await client.get(url, timeout=15.0)
        if resp.status_code == 400:
            return {"error": "Invalid BTC address"}
        if resp.status_code == 404:
            # Never-used address — still a valid check
            return {
                "balance": 0.0,
                "balance_display": "0.00000000 BTC",
                "balance_native_symbol": "BTC",
                "tx_count": 0,
                "type": "BTC",
                "explorer_link": f"https://mempool.space/address/{address}",
                "graph_data": [],
                "tx_list": [],
            }
        if resp.status_code != 200:
            return {"error": f"{base} HTTP {resp.status_code}"}

        data = resp.json()
        chain_stats = data.get("chain_stats") or {}
        funded = int(chain_stats.get("funded_txo_sum") or 0)
        spent = int(chain_stats.get("spent_txo_sum") or 0)
        balance_btc = (funded - spent) / 1e8
        tx_count = int(chain_stats.get("tx_count") or 0)

        graph_edges = []
        tx_list = []
        resp_txs = await client.get(txs_url, timeout=15.0)
        if resp_txs.status_code == 200:
            for tx in (resp_txs.json() or [])[:50]:
                tx_hash = tx.get("txid")
                status = tx.get("status") or {}
                ts = status.get("block_time") or 0
                edges, rows = ChainService._btc_counterparty_edges(
                    address, tx.get("vin") or [], tx.get("vout") or [], tx_hash, ts
                )
                graph_edges.extend(edges)
                tx_list.extend(rows)

        host = "mempool.space" if "mempool" in base else "blockstream.info"
        return {
            "balance": balance_btc,
            "balance_display": f"{balance_btc:.8f} BTC",
            "balance_native_symbol": "BTC",
            "tx_count": tx_count,
            "type": "BTC",
            "explorer_link": f"https://{host}/address/{address}",
            "graph_data": graph_edges,
            "tx_list": tx_list[:40],
            "provider": base,
        }

    @staticmethod
    def _btc_counterparty_edges(address: str, vins: list, vouts: list, tx_hash: str, ts: int):
        """
        One logical flow per counterparty, not every vin×vout of the UTXO tx.
        Values from Esplora / blockchain.info are satoshis.
        """
        edges = []
        rows = []
        our_in = 0.0
        our_out = 0.0
        external_ins = []
        external_outs = []

        def sats(v) -> float:
            return float(v or 0) / 1e8

        for vin in vins:
            prev = vin.get("prevout") or vin.get("prev_out") or {}
            sender = prev.get("scriptpubkey_address") or prev.get("addr")
            val = sats(prev.get("value"))
            if not sender:
                continue
            if sender == address:
                our_in += val
            else:
                external_ins.append((sender, val))

        for vout in vouts:
            receiver = vout.get("scriptpubkey_address") or vout.get("addr")
            val = sats(vout.get("value"))
            if not receiver:
                continue
            if receiver == address:
                our_out += val
            else:
                external_outs.append((receiver, val))

        if our_in > 1e-8:
            for recv, val in external_outs:
                if val < 1e-8:
                    continue
                edges.append({
                    "source": address, "target": recv, "value": val,
                    "currency": "BTC", "hash": tx_hash, "timestamp": (ts or 0) * 1000,
                })
                rows.append({
                    "hash": tx_hash, "method": "send", "from": address, "to": recv,
                    "value": f"{val:.8f} BTC", "timestamp": ts,
                    "explorer_url": f"https://mempool.space/tx/{tx_hash}",
                })
        elif our_out > 1e-8:
            # Receive: every external input is a real funding counterparty (full picture)
            for payer, val in external_ins:
                if val < 1e-8:
                    continue
                edges.append({
                    "source": payer, "target": address, "value": val,
                    "currency": "BTC", "hash": tx_hash, "timestamp": (ts or 0) * 1000,
                })
                rows.append({
                    "hash": tx_hash, "method": "receive", "from": payer, "to": address,
                    "value": f"{val:.8f} BTC", "timestamp": ts,
                    "explorer_url": f"https://mempool.space/tx/{tx_hash}",
                })
        return edges, rows

    @staticmethod
    async def _btc_from_blockchain_info(client: httpx.AsyncClient, address: str):
        url = f"https://blockchain.info/rawaddr/{address}"
        resp = await client.get(url, params={"limit": 20}, timeout=15.0)
        if resp.status_code == 400:
            return {"error": "Invalid BTC address"}
        if resp.status_code != 200:
            return {"error": f"blockchain.info HTTP {resp.status_code}"}

        data = resp.json()
        balance_btc = float(data.get("final_balance") or 0) / 1e8
        tx_count = int(data.get("n_tx") or 0)
        graph_edges = []
        tx_list = []
        for tx in (data.get("txs") or [])[:20]:
            tx_hash = tx.get("hash")
            ts = tx.get("time") or 0
            vins = []
            for inp in tx.get("inputs") or []:
                prev = inp.get("prev_out") or {}
                vins.append({"prev_out": {"addr": prev.get("addr"), "value": prev.get("value")}})
            vouts = []
            for out in tx.get("out") or []:
                vouts.append({"addr": out.get("addr"), "value": out.get("value")})
            edges, rows = ChainService._btc_counterparty_edges(address, vins, vouts, tx_hash, ts)
            graph_edges.extend(edges)
            tx_list.extend(rows)

        return {
            "balance": balance_btc,
            "balance_display": f"{balance_btc:.8f} BTC",
            "balance_native_symbol": "BTC",
            "tx_count": tx_count,
            "type": "BTC",
            "explorer_link": f"https://mempool.space/address/{address}",
            "graph_data": graph_edges,
            "tx_list": tx_list[:40],
            "provider": "blockchain.info",
        }

    OFFICIAL_USDT = {
        "TRON": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "ETH": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "BSC": "0x55d398326f99059ff775485246999027b3197955",
    }
    MAX_TX_AGE_SECONDS = 7200  # 2 hours

    @staticmethod
    async def verify_tx(chain: str, tx_hash: str, expected_dest: str):
        chain = (chain or "").upper()
        if chain == "TRON":
            return await ChainService._verify_tron_tx(tx_hash, expected_dest)
        if chain in ("ETH", "BSC"):
            return await ChainService._verify_evm_tx(chain, tx_hash, expected_dest)
        if chain == "SOL":
            return await SolanaService.verify_tx(tx_hash, expected_dest)
        return {"verified": False, "error": f"Unsupported chain: {chain}"}

    @staticmethod
    async def _verify_tron_tx(tx_hash: str, expected_dest: str):
        url_events = f"https://api.trongrid.io/v1/transactions/{tx_hash}/events"
        now_ts = datetime.now(timezone.utc).timestamp()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url_events, timeout=8.0)
                if resp.status_code != 200:
                    return {"verified": False, "error": "Tx events not found"}
                for event in (resp.json().get("data") or []):
                    if event.get("event_name") != "Transfer":
                        continue
                    # Security: enforce official TRON USDT contract address
                    contract_addr = event.get("contract_address")
                    if contract_addr != ChainService.OFFICIAL_USDT["TRON"]:
                        continue
                    
                    # Security: verify transaction is not older than MAX_TX_AGE_SECONDS
                    block_ts_ms = event.get("block_timestamp")
                    if block_ts_ms:
                        tx_time = block_ts_ms / 1000.0
                        if (now_ts - tx_time) > ChainService.MAX_TX_AGE_SECONDS:
                            return {"verified": False, "error": "Transaction expired (older than 2 hours)"}

                    res = event.get("result") or {}
                    to_addr = res.get("to") or res.get("1")
                    val = res.get("value") or res.get("2")
                    if to_addr == expected_dest:
                        amount = float(val) / 1_000_000
                        return {
                            "verified": True,
                            "amount": amount,
                            "currency": "USDT",
                            "sender": res.get("from") or res.get("0") or "Unknown",
                            "timestamp": tx_time if block_ts_ms else now_ts,
                        }
                return {"verified": False, "error": "No matching official USDT transfer to payment address"}
        except Exception as e:
            return {"verified": False, "error": str(e)}

    @staticmethod
    async def _verify_evm_tx(chain: str, tx_hash: str, expected_dest: str):
        base_url = ChainService.BLOCKSCOUT.get(chain)
        if not base_url:
            return {"verified": False, "error": f"Chain {chain} not supported"}
        url = f"{base_url}/transactions/{tx_hash}"
        now_ts = datetime.now(timezone.utc).timestamp()
        expected_contract = ChainService.OFFICIAL_USDT.get(chain, "").lower()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=8.0)
                if resp.status_code != 200:
                    return {"verified": False, "error": "Tx not found"}
                tx = resp.json()

                # Check tx timestamp freshness
                raw_time = tx.get("timestamp")
                tx_ts = now_ts
                if raw_time:
                    try:
                        tx_dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                        tx_ts = tx_dt.timestamp()
                        if (now_ts - tx_ts) > ChainService.MAX_TX_AGE_SECONDS:
                            return {"verified": False, "error": "Transaction expired (older than 2 hours)"}
                    except Exception:
                        pass

                # Verify token transfers strictly for official USDT contract
                for tt in tx.get("token_transfers") or []:
                    token_obj = tt.get("token") or {}
                    token_addr = (token_obj.get("address") or "").lower()
                    if token_addr != expected_contract:
                        continue  # Skip any fake/impersonating tokens

                    tt_to = tt.get("to", {})
                    tt_hash = tt_to.get("hash", "") if isinstance(tt_to, dict) else ""
                    if tt_hash.lower() == expected_dest.lower():
                        decimals = int(token_obj.get("decimals") or 18)
                        val = float((tt.get("total") or {}).get("value") or 0) / (10 ** decimals)
                        sender = tt.get("from", {})
                        return {
                            "verified": True,
                            "amount": val,
                            "currency": "USDT",
                            "sender": sender.get("hash") if isinstance(sender, dict) else sender,
                            "timestamp": tx_ts,
                        }
        except Exception as e:
            return {"verified": False, "error": str(e)}
        return {"verified": False, "error": "No matching official USDT transfer found"}

    @staticmethod
    async def get_usdt_balance(chain: str, address: str) -> float:
        chain = (chain or "").upper()
        if chain == "TRON":
            stats = await ChainService._get_tron_stats(address)
            if stats.get("error"):
                return 0.0
            return float(stats.get("balance_usdt") or 0)
        if chain in ("ETH", "BSC"):
            base_url = ChainService.BLOCKSCOUT.get(chain)
            if not base_url:
                return 0.0
            usdt_contracts = {
                "ETH": "0xdac17f958d2ee523a2206206994597c13d831ec7",
                "BSC": "0x55d398326f99059ff775485246999027b3197955",
            }
            target_contract = usdt_contracts.get(chain, "").lower()
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{base_url}/addresses/{address}/token-balances",
                        timeout=10.0,
                    )
                    if resp.status_code != 200:
                        return 0.0
                    for item in resp.json() or []:
                        token = item.get("token") or {}
                        c_addr = (token.get("address") or "").lower()
                        if c_addr == target_contract or token.get("symbol") == "USDT":
                            decimals = int(token.get("decimals") or 18)
                            val = float(item.get("value") or 0) / (10 ** decimals)
                            return round(val, 2)
            except Exception:
                return 0.0
            return 0.0
        if chain == "SOL":
            stats = await SolanaService.get_wallet_stats(address)
            return float(stats.get("balance_usdt") or 0.0)
        return 0.0

    @staticmethod
    async def get_usdt_inbound_transfers(chain: str, address: str, limit: int = 50) -> list:
        """Recent inbound USDT transfers to a deposit address (for daily treasury screen)."""
        chain = (chain or "").upper()
        inbound = []
        if chain == "TRON":
            url = f"https://api.trongrid.io/v1/accounts/{address}/transactions/trc20"
            params = {
                "limit": limit,
                "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                "only_to": True,
            }
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=params, timeout=12.0)
                    if resp.status_code != 200:
                        return []
                    for tx in resp.json().get("data") or []:
                        inbound.append({
                            "tx_hash": tx.get("transaction_id"),
                            "sender": tx.get("from"),
                            "amount": float(tx.get("value") or 0) / 1_000_000,
                            "timestamp": tx.get("block_timestamp"),
                        })
            except Exception:
                return []
            return inbound

        if chain == "ETH":
            base_url = ChainService.BLOCKSCOUT.get(chain)
            usdt = "0xdac17f958d2ee523a2206206994597c13d831ec7"
            if not base_url:
                return []
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{base_url}/addresses/{address}/token-transfers",
                        params={"type": "ERC-20", "token": usdt},
                        timeout=12.0,
                    )
                    if resp.status_code != 200:
                        return []
                    for tx in (resp.json().get("items") or [])[:limit]:
                        to_obj = tx.get("to") or {}
                        to_addr = to_obj.get("hash") if isinstance(to_obj, dict) else str(to_obj)
                        if (to_addr or "").lower() != address.lower():
                            continue
                        from_obj = tx.get("from") or {}
                        sender = from_obj.get("hash") if isinstance(from_obj, dict) else str(from_obj)
                        token = tx.get("token") or {}
                        decimals = int(token.get("decimals") or 6)
                        val = float((tx.get("total") or {}).get("value") or 0) / (10 ** decimals)
                        inbound.append({
                            "tx_hash": tx.get("tx_hash") or tx.get("hash"),
                            "sender": sender,
                            "amount": val,
                            "timestamp": tx.get("timestamp"),
                        })
            except Exception:
                return []
        return inbound
