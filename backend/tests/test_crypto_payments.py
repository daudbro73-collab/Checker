"""
Tests for Multi-Chain Crypto Payments:
- USDT on TRON (TRC-20)
- USDT on Ethereum (ERC-20)
- USDT on BNB Chain (BEP-20)
- USDT on Solana (SPL)
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.chain import ChainService
from services.solana_service import SolanaService, USDT_SOL_MINT


@pytest.mark.asyncio
class TestBscPaymentVerification:
    async def test_verify_bsc_usdt_transfer(self):
        tx_hash = "0x" + "b" * 64
        expected_dest = "0x" + "1" * 40

        mock_tx_resp = MagicMock()
        mock_tx_resp.status_code = 200
        mock_tx_resp.json.return_value = {
            "hash": tx_hash,
            "to": {"hash": "0x55d398326f99059ff775485246999027b3197955"}, # USDT BEP-20 contract
            "from": {"hash": "0x" + "a" * 40},
            "token_transfers": [
                {
                    "to": {"hash": expected_dest},
                    "from": {"hash": "0x" + "a" * 40},
                    "total": {"value": str(int(10.0 * 1e18))},
                    "token": {"symbol": "USDT", "decimals": "18", "address": "0x55d398326f99059ff775485246999027b3197955"},
                }
            ],
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_tx_resp
            res = await ChainService.verify_tx("BSC", tx_hash, expected_dest)

            assert res["verified"] is True
            assert res["amount"] == 10.0
            assert res["currency"] == "USDT"
            assert res["sender"] == "0x" + "a" * 40


@pytest.mark.asyncio
class TestSolanaPaymentVerification:
    async def test_verify_solana_usdt_transfer(self):
        sig = "sig_" + "s" * 64
        dest = "SolDestAddress11111111111111111111111111111"

        mock_tx = {
            "meta": {
                "err": None,
                "preTokenBalances": [
                    {"accountIndex": 1, "mint": USDT_SOL_MINT, "uiTokenAmount": {"uiAmount": 5.0}}
                ],
                "postTokenBalances": [
                    {
                        "accountIndex": 1,
                        "mint": USDT_SOL_MINT,
                        "owner": dest,
                        "uiTokenAmount": {"uiAmount": 15.0}, # +10 USDT received
                    }
                ],
            },
            "transaction": {
                "message": {
                    "accountKeys": ["SolSender1111111111111111111111111111111111", dest],
                    "instructions": [],
                }
            },
        }

        with patch.object(SolanaService, "_rpc_call", new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = mock_tx
            res = await SolanaService.verify_tx(sig, dest)

            assert res["verified"] is True
            assert res["amount"] == 10.0
            assert res["currency"] == "USDT"
            assert res["sender"] == "SolSender1111111111111111111111111111111111"

    async def test_verify_solana_failed_tx(self):
        sig = "sig_failed"
        dest = "SolDestAddress11111111111111111111111111111"

        mock_tx = {
            "meta": {"err": "InstructionError"},
            "transaction": {"message": {"accountKeys": ["Sender"]}},
        }

        with patch.object(SolanaService, "_rpc_call", new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = mock_tx
            res = await SolanaService.verify_tx(sig, dest)

            assert res["verified"] is False
            assert "failed on Solana" in res["error"]
