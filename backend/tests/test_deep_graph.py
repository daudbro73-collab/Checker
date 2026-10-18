import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.deep_graph import DeepGraphService, KNOWN_MIXERS
from services.redis_client import cache_delete_prefix


@pytest.mark.asyncio
async def test_deep_graph_2hop_mixer_detection():
    target = "0x1111111111111111111111111111111111111111"
    relay = "0x2222222222222222222222222222222222222222"
    # Known Tornado Cash router from registry
    mixer = "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b"

    cache_delete_prefix("deep_graph:")

    # Mock transactions:
    # Target -> Relay (Hop 1)
    # Relay -> Tornado Router (Hop 2)
    async def mock_get_txs(chain, address, limit=10):
        addr_l = address.lower()
        if addr_l == target.lower():
            return [{
                "source": target,
                "target": relay,
                "value": 5.0,
                "currency": "ETH",
                "hash": "0xaaa1",
                "timestamp": 1700000000,
            }]
        elif addr_l == relay.lower():
            return [{
                "source": relay,
                "target": mixer,
                "value": 4.8,
                "currency": "ETH",
                "hash": "0xbbb2",
                "timestamp": 1700000500,
            }]
        return []

    with patch("services.chain.ChainService.get_transactions", side_effect=mock_get_txs):
        result = await DeepGraphService.expand_deep_graph("ETH", target, depth=2)

    assert result["depth_explored"] == 2
    assert result["summary"]["has_mixer_taint"] is True
    assert result["summary"]["taint_paths_found"] >= 1

    taint = result["taint_paths"][0]
    assert taint["risk_type"] == "MIXER"
    assert taint["hop_distance"] == 2
    assert taint["decay_weight"] == 0.5  # Hop 2 decay weight
    assert taint["threat_node"].lower() == mixer.lower()

    # Ensure nodes contains Target, Relay, and Mixer
    node_ids = {n["id"].lower() for n in result["nodes"]}
    assert target.lower() in node_ids
    assert relay.lower() in node_ids
    assert mixer.lower() in node_ids
