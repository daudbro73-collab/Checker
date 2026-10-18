"""Directory of known entities (CEX, Cross-Chain Bridges, DEX, DeFi).
Enables Attribution Coverage calculations and Cross-Chain Bridge Provenance break alerts.
"""
from typing import Optional, Dict, Any

# Address -> Entity info (all addresses lowercased)
KNOWN_ENTITIES: Dict[str, Dict[str, Any]] = {
    # ─── CROSS-CHAIN BRIDGES (Provenance break points) ───
    # BSC TokenHub (Binance native cross-chain bridge)
    "0x0000000000000000000000000000000000001004": {
        "name": "Binance TokenHub Bridge",
        "category": "bridge",
        "chain": "BSC",
        "is_bridge": True,
        "note": "Кросс-чейн мост: происхождение средств обрывается на мосту (BNB Beacon Chain)",
    },
    # Stargate Finance (LayerZero)
    "0x4a364f8c717ca67422e138d603945111b27a7712": {
        "name": "Stargate Finance Router",
        "category": "bridge",
        "chain": "BSC",
        "is_bridge": True,
        "note": "Кросс-чейн мост Stargate (LayerZero). Апстрим-сеть неизвестна без глубокого трекинга",
    },
    "0x8731d54e9d02c286767d56ac03e8037c07e01e98": {
        "name": "Stargate Finance Router",
        "category": "bridge",
        "chain": "ETH",
        "is_bridge": True,
        "note": "Кросс-чейн мост Stargate (LayerZero)",
    },
    # Celer cBridge
    "0xdd9038561821f68334407519ff7150c9dfeb91ff": {
        "name": "Celer cBridge",
        "category": "bridge",
        "chain": "BSC",
        "is_bridge": True,
        "note": "Кросс-чейн мост Celer cBridge. Происхождение средств обрывается",
    },
    "0x5427fea718102752b509145a3886507ebf11517f": {
        "name": "Celer cBridge",
        "category": "bridge",
        "chain": "ETH",
        "is_bridge": True,
        "note": "Кросс-чейн мост Celer cBridge",
    },
    # Multichain / AnySwap
    "0xd1c5966f9f5ee6881ff6b261bbfda459722d683c": {
        "name": "Multichain (AnySwap) Router",
        "category": "bridge",
        "chain": "BSC",
        "is_bridge": True,
        "note": "Кросс-чейн мост Multichain",
    },
    # Wormhole Portal
    "0xb6f6d86a8f9879a9c87f643768d9efc38c1da6e7": {
        "name": "Wormhole Portal Bridge",
        "category": "bridge",
        "chain": "BSC",
        "is_bridge": True,
        "note": "Кросс-чейн мост Wormhole Portal",
    },
    "0x3ee18b2214aff97000d974cf647e7c347e8fa585": {
        "name": "Wormhole Portal Bridge",
        "category": "bridge",
        "chain": "ETH",
        "is_bridge": True,
        "note": "Кросс-чейн мост Wormhole Portal",
    },
    # Synapse Bridge
    "0xd123f70ae324d34a9e76b67a27bf77593ba474f2": {
        "name": "Synapse Bridge",
        "category": "bridge",
        "chain": "BSC",
        "is_bridge": True,
        "note": "Кросс-чейн мост Synapse",
    },

    # ─── CEX HOT WALLETS (Binance, OKX, Bybit, etc.) ───
    # Binance BSC Hot Wallets
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": {"name": "Binance Hot Wallet", "category": "cex", "chain": "BSC"},
    "0xf977814e90da44bfae374775a34664772691a544": {"name": "Binance Hot Wallet 8", "category": "cex", "chain": "BSC"},
    "0x28c6c06298d514db089934071355e5743bf21d60": {"name": "Binance Hot Wallet 14", "category": "cex", "chain": "BSC"},
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": {"name": "Binance Hot Wallet 15", "category": "cex", "chain": "BSC"},
    "0xdfd5293d8e347dff59e909147973ca8180e2113c": {"name": "Binance Hot Wallet 16", "category": "cex", "chain": "BSC"},
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": {"name": "Binance Hot Wallet", "category": "cex", "chain": "ETH"},
    "0xd551234ae421e3bcba99a0da6d736074f22192ff": {"name": "Binance Hot Wallet 2", "category": "cex", "chain": "ETH"},
    "0x564286362092d8e7936f0549571a803b203aaced": {"name": "Binance Hot Wallet 3", "category": "cex", "chain": "ETH"},
    "0x0681d8db095565fe8a346fa0277bffde9c0edbbf": {"name": "Binance Hot Wallet 4", "category": "cex", "chain": "ETH"},
    "0xfe9e8709d3215310075d67e3ed32a380ccf451c8": {"name": "Binance Hot Wallet 5", "category": "cex", "chain": "ETH"},
    
    # OKX
    "0xa7efae728d2936e78bda97dc267687568dd593f3": {"name": "OKX Hot Wallet", "category": "cex", "chain": "BSC"},
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": {"name": "OKX Hot Wallet", "category": "cex", "chain": "ETH"},
    "0x236f9f97e0eb0ca2723793f0b2f561ee51a0210e": {"name": "OKX Hot Wallet 2", "category": "cex", "chain": "ETH"},

    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": {"name": "Bybit Hot Wallet", "category": "cex", "chain": "BSC"},
    "0xee5b5b923f7082c80e38955be9d7477e03c6c084": {"name": "Bybit Hot Wallet", "category": "cex", "chain": "ETH"},

    # HTX / Huobi
    "0x1062a747393198f70f71ec65a582423dba7e5ab3": {"name": "HTX Hot Wallet", "category": "cex", "chain": "BSC"},
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": {"name": "HTX Hot Wallet", "category": "cex", "chain": "ETH"},

    # KuCoin
    "0xf16e9b0d03470827a95cdfd0cb8a8a3b46969b91": {"name": "KuCoin Hot Wallet", "category": "cex", "chain": "BSC"},
    "0x2b5634c42055806a59e9107ed44d43c426e58258": {"name": "KuCoin Hot Wallet", "category": "cex", "chain": "ETH"},

    # Gate.io
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": {"name": "Gate.io Hot Wallet", "category": "cex", "chain": "ETH"},

    # ─── DEX & DEFI PROTOCOLS ───
    # PancakeSwap (BSC)
    "0x10ed43c718714eb63d5aa57b78b54704e256024e": {"name": "PancakeSwap Router v2", "category": "dex", "chain": "BSC"},
    "0x13f4ea83d0bd40e75c8222255bc855a974568dd4": {"name": "PancakeSwap Router v3", "category": "dex", "chain": "BSC"},
    "0x3a6d8ca21d1cf76f653a67577fa0d27453350dd8": {"name": "Biswap Router", "category": "dex", "chain": "BSC"},
    # Uniswap (ETH)
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": {"name": "Uniswap V2 Router", "category": "dex", "chain": "ETH"},
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": {"name": "Uniswap V3 SwapRouter02", "category": "dex", "chain": "ETH"},
    "0xe592427a0aece92de3edee1f18e0157c05861564": {"name": "Uniswap V3 SwapRouter", "category": "dex", "chain": "ETH"},
}


def lookup_known_entity(address: str) -> Optional[Dict[str, Any]]:
    """Look up an address in the curated directory of CEX, Bridges, and DEXs."""
    if not address:
        return None
    addr_l = address.lower().strip()
    return KNOWN_ENTITIES.get(addr_l)
