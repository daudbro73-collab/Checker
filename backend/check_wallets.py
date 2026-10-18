"""
Quick wallet check script — calls the internal services directly
to bypass auth/balance requirements.
"""
import asyncio
import json
from services.sanctions import check_sanctions
from services.chain import ChainService
from services.risk_engine import calculate_risk_score

# ── Wallets to check ─────────────────────────────────────────────
WALLETS = [
    # 1. Known OFAC-sanctioned (Tornado Cash deployer)
    {"address": "0xd90e2f925DA726b50C4Ed8D0Fb90Ad053324F31b", "chain": "ETH", "label": "Tornado Cash (OFAC)"},
    # 2. Vitalik Buterin's public ETH wallet (should be clean)
    {"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "chain": "ETH", "label": "Vitalik.eth"},
    # 3. Binance Hot Wallet (high volume, should be safe/caution)
    {"address": "0x28C6c06298d514Db089934071355E5743bf21d60", "chain": "ETH", "label": "Binance Hot Wallet"},
    # 4. Random TRON wallet (USDT heavy chain)
    {"address": "TDqSquXBgUCLYvYC4XZgrprLK589dkhSCf", "chain": "TRON", "label": "Justin Sun Wallet (TRON)"},
]

LEVEL_EMOJI = {
    "SAFE": "🟢",
    "CAUTION": "🟡",
    "WARNING": "🟠",
    "CRITICAL": "🔴",
}

async def check_one(wallet: dict):
    addr   = wallet["address"]
    chain  = wallet["chain"]
    label  = wallet["label"]

    print(f"\n{'='*60}")
    print(f"  🔍  {label}")
    print(f"  Address : {addr}")
    print(f"  Chain   : {chain}")
    print(f"{'='*60}")

    # 1. Sanctions
    sanction = check_sanctions(addr)
    if sanction["is_sanctioned"]:
        print(f"  ⛔ SANCTIONED — {sanction['source']} / {sanction['reason']}")
    else:
        print(f"  ✅ Not in sanctions lists")

    # 2. Chain data
    print(f"  ⏳ Fetching on-chain data …")
    chain_data = await ChainService.get_stats(chain, addr)

    if chain_data.get("error"):
        print(f"  ❌ Chain error: {chain_data['error']}")
        return

    print(f"  💰 Balance   : {chain_data.get('balance_display', chain_data.get('balance', '?'))}")
    print(f"  📊 TX Count  : {chain_data.get('tx_count', '?')}")
    print(f"  📜 TX fetched: {len(chain_data.get('tx_list', []))}")

    # 3. Risk scoring
    risk_score, risk_factors, risk_level = calculate_risk_score(sanction, chain_data)
    emoji = LEVEL_EMOJI.get(risk_level, "⚪")
    print(f"\n  {emoji}  Risk Score : {risk_score} / 100  ({risk_level})")

    if risk_factors:
        print(f"  ── Risk Factors ──")
        for f in risk_factors:
            print(f"     [{f['level']}] {f['desc']}")

    # 4. Last 3 transactions preview
    tx_list = chain_data.get("tx_list", [])
    if tx_list:
        print(f"\n  ── Last 3 Transactions ──")
        for tx in tx_list[:3]:
            val = tx.get("value", "?")
            from_ = tx.get("from", "?")[:12] + "…"
            to_   = tx.get("to", "?")[:12] + "…"
            print(f"     {from_} → {to_}  |  {val}")


async def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║        AML Guard — Wallet Check Script          ║")
    print("╚══════════════════════════════════════════════════╝")

    for w in WALLETS:
        try:
            await check_one(w)
        except Exception as e:
            print(f"  ❌ Error checking {w['label']}: {e}")

    print(f"\n{'='*60}")
    print(f"  ✅ Done — {len(WALLETS)} wallets checked.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
