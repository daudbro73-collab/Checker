"""
Dirty-wallet smoke test — known OFAC / SDN addresses across ETH, TRON, BTC.

Expect CRITICAL (100) on all. Run:
  cd backend && python check_dirty_wallets.py
"""
import asyncio

from services.analysis import analyze_wallet
from services.sanctions import check_sanctions

# Ironclad dirty set (OFAC SDN / named designations). Do not use Tornado —
# delisted Mar 2025 and must NOT score as sanctioned.
WALLETS = [
    {
        "label": "Lazarus Group (DPRK) — OFAC",
        "chain": "ETH",
        "address": "0x53b6936513e738f44fb50d2b9476730c0ab3bfc1",
        "expect": "CRITICAL",
    },
    {
        "label": "Garantex Exchange — OFAC",
        "chain": "ETH",
        "address": "0x8576acc5c05d6ce88f4e49bf65bdf0c62f91353c",
        "expect": "CRITICAL",
    },
    {
        "label": "OFAC SDN — TRON",
        "chain": "TRON",
        "address": "TA3rH2A7iHnm6pKH8gr9cK1EZnShnmZdFg",
        "expect": "CRITICAL",
    },
    {
        "label": "OFAC SDN — Bitcoin",
        "chain": "BTC",
        "address": "123WBUDmSJv4GctdVEz6Qq6z8nXSKrJ4KX",
        "expect": "CRITICAL",
    },
    {
        "label": "OFAC SDN — ETH list",
        "chain": "ETH",
        "address": "0x0330070FD38Ec3bB94F58FA55D40368271E9e54A",
        "expect": "CRITICAL",
    },
]


async def main():
    print("AML Guard — dirty wallet battery\n")
    ok = 0
    fail = 0
    for w in WALLETS:
        print(f"── {w['label']} ({w['chain']})")
        print(f"   {w['address']}")
        s = check_sanctions(w["address"])
        print(f"   list hit: {s.get('is_sanctioned')} ({s.get('reason') or s.get('source')})")
        try:
            r = await analyze_wallet(w["address"], w["chain"])
            level = (r.get("risk_level") or "").upper()
            score = r.get("risk_score")
            passed = level == w["expect"] and int(score or 0) >= 90
            mark = "PASS" if passed else "FAIL"
            if passed:
                ok += 1
            else:
                fail += 1
            print(f"   → {mark}: {level} {score}/100")
            for f in (r.get("risk_factors") or [])[:3]:
                if isinstance(f, dict):
                    print(f"      [{f.get('level')}] {f.get('desc')}")
        except Exception as e:
            fail += 1
            print(f"   → FAIL: {getattr(e, 'detail', e)}")
        print()
    print(f"Result: {ok} passed, {fail} failed / {len(WALLETS)}")
    raise SystemExit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
