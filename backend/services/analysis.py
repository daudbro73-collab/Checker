"""Shared wallet analysis pipeline."""
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from config import get_settings
from database import ListSnapshot, RiskLabel, SessionLocal
from services.address_validation import validate_address
from services.chain import ChainService
from services.graph import build_graph_data
from services.live_signals import fetch_live_signals
from services.redis_client import cache_get, cache_set, cache_delete
from services.risk_engine import calculate_risk_score
from services.sanctions import bulk_check_sanctions, check_sanctions

settings = get_settings()
logger = logging.getLogger(__name__)

# TTL кэша chain_data (5 мин). Балансы на HIT всё равно освежаются.
_CHAIN_CACHE_TTL = 300


def get_list_versions(db=None) -> dict[str, str]:
    """
    Возвращает версии синхронизированных списков (OFAC, ScamSniffer и пр.).
    Принимает опциональную сессию — если не передана, открывает свою.
    """
    _own_db = db is None
    if _own_db:
        db = SessionLocal()
    try:
        rows = db.query(ListSnapshot).order_by(ListSnapshot.synced_at.desc()).all()
        seen = {}
        for row in rows:
            if row.source not in seen:
                seen[row.source] = row.synced_at.strftime("%Y-%m-%d") if row.synced_at else row.version
        return seen
    except Exception:
        return {}
    finally:
        if _own_db:
            db.close()


def _lookup_labels(addresses: list[str], db=None) -> dict[str, dict]:
    """
    Ищет RiskLabel-метки для списка адресов.
    Принимает опциональную сессию — если не передана, открывает свою.
    """
    if not addresses:
        return {}
    _own_db = db is None
    if _own_db:
        db = SessionLocal()
    try:
        rows = db.query(RiskLabel).filter(RiskLabel.address.in_([a.lower() for a in addresses])).all()
        out = {}
        for r in rows:
            out[r.address] = {
                "source": r.source,
                "category": r.category,
                "label": r.label,
                "confidence": r.confidence,
            }
        return out
    except Exception:
        return {}
    finally:
        if _own_db:
            db.close()


async def _get_chain_data_cached(chain: str, address: str) -> tuple[dict, bool]:
    """
    Возвращает (chain_data, from_cache).

    Кэшируем chain_data (txs/graph) на короткий TTL.
    Даже на cache HIT — балансы освежаем лёгким запросом (иначе 0 залипает).
    """
    addr_key = address.lower() if chain in ("ETH", "BSC", "EVM", "BTC") else address
    cache_key = f"chain_data:{chain}:{addr_key}"
    cached_raw = cache_get(cache_key)
    if cached_raw:
        try:
            data = json.loads(cached_raw)
            if not data.get("error"):
                data = await ChainService.refresh_balances(chain, address, data)
                return data, True
        except Exception:
            cache_delete(cache_key)

    data = await ChainService.get_stats(chain, address)
    if not data.get("error"):
        try:
            cache_set(cache_key, json.dumps(data, default=str), ttl_seconds=_CHAIN_CACHE_TTL)
        except Exception as e:
            logger.warning("Failed to cache chain_data for %s: %s", address, e)
    else:
        # Never cache hard failures as "0 balance"
        cache_delete(cache_key)

    return data, False


async def analyze_wallet(address: str, chain: str, db=None) -> dict[str, Any]:
    chain = (chain or "ETH").upper()
    if chain not in settings.ALLOWED_CHAINS:
        supported_str = ", ".join(sorted(settings.ALLOWED_CHAINS))
        raise HTTPException(status_code=400, detail=f"Unsupported chain. Supported: {supported_str}")

    ok, msg = validate_address(chain, address)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    address = msg  # normalized address (ETH checksum-ready / BTC lowercase bech32)

    # ── Санкции: всегда свежие (локальная БД — быстро) ──
    sanction_result = check_sanctions(address)
    if chain == "TON":
        from services.ton_address import parse_and_validate_ton_address
        ok_t, _, t_info = parse_and_validate_ton_address(address)
        if ok_t and t_info:
            if not sanction_result.get("is_sanctioned"):
                sanction_result = check_sanctions(t_info["raw"])
            if not sanction_result.get("is_sanctioned"):
                sanction_result = check_sanctions(t_info["non_bounceable"])

    # ── Chain data: с кэшем 30 минут ──
    chain_data, from_cache = await _get_chain_data_cached(chain, address)
    if from_cache:
        logger.debug("Cache HIT chain_data for %s/%s", chain, address[:12])

    # Direct sanctions or threat label hit must never fail the product because explorer is down.
    if chain_data.get("error"):
        subject_labels = _lookup_labels([address.lower()], db)
        if sanction_result.get("is_sanctioned") or (address.lower() in subject_labels):
            chain_data = {
                "balance": 0,
                "balance_display": "n/a (explorer unavailable)",
                "tx_count": 0,
                "tx_list": [],
                "graph_data": [],
                "type": chain,
                "explorer_error": chain_data.get("error"),
            }
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Chain data unavailable: {chain_data.get('error')}. Funds were not charged.",
            )

    # ── Live signals: всегда свежие (GoPlus + Tether on-chain) ──
    live = await fetch_live_signals(chain, address)
    if live.get("tether_blacklisted"):
        sanction_result = {
            "is_sanctioned": True,
            "source": "Tether",
            "category": "Frozen",
            "reason": "Address is on Tether USDT on-chain blacklist (isBlackListed)",
            "confidence": "high",
            "listed_at": datetime.utcnow().isoformat(),
        }

    # Enrich with GoPlus flags (non-sanctions)
    goplus = live.get("goplus") or {}
    live_risk_flags = []
    if isinstance(goplus, dict):
        for key in ("honeypot_related_address", "phishing_activities", "darkweb_transactions",
                    "money_laundering", "financial_crime", "mixer", "sanctioned"):
            val = goplus.get(key)
            if str(val) == "1":
                live_risk_flags.append(key)

    tx_list = chain_data.get("tx_list", [])
    counterparties = set()
    for tx in tx_list:
        sender = (tx.get("from") or "").lower()
        receiver = (tx.get("to") or "").lower()
        addr_l = address.lower()
        if sender and sender != addr_l:
            counterparties.add(sender)
        if receiver and receiver != addr_l:
            counterparties.add(receiver)

    counter_sanctions = bulk_check_sanctions(list(counterparties))

    # ── Labels: используем переданную сессию (нет N+2 запросов) ──
    labels = _lookup_labels(list(counterparties) + [address.lower()], db)

    direct_hits = 0
    distinct_sanctioned = 0
    categories = set()
    sanctioned_volumes = []

    for addr, info in counter_sanctions.items():
        if info.get("is_sanctioned"):
            distinct_sanctioned += 1
            cat = info.get("category")
            if cat:
                categories.add(cat)
            for tx in tx_list:
                if addr in ((tx.get("from") or "").lower(), (tx.get("to") or "").lower()):
                    direct_hits += 1
                    try:
                        val = float(str(tx.get("value", "0")).split()[0])
                    except ValueError:
                        val = 0
                    sanctioned_volumes.append({
                        "address": addr,
                        "value": val,
                        "timestamp": tx.get("timestamp", 0),
                        "direction": "in" if (tx.get("to") or "").lower() == address.lower() else "out",
                        "category": info.get("category"),
                        "source": info.get("source"),
                    })

    if direct_hits or distinct_sanctioned:
        chain_data["counterparty_sanctions"] = {
            "direct_hits": direct_hits,
            "distinct_sanctioned": distinct_sanctioned,
            "categories": list(categories),
            "exposure_events": sanctioned_volumes,
            "by_address": counter_sanctions,
        }

    chain_data["live_signals"] = live
    chain_data["live_risk_flags"] = live_risk_flags
    chain_data["risk_labels"] = labels
    chain_data["target_sanctions"] = sanction_result

    # ── List versions: используем переданную сессию ──
    list_versions = get_list_versions(db)
    list_versions["GoPlus"] = "live"
    list_versions["Tether"] = "live"

    risk_score, risk_factors, risk_level, meta = calculate_risk_score(
        sanction_result, chain_data, address=address
    )
    graph_data = build_graph_data(address, chain_data)

    verdict = _human_verdict(risk_level, risk_factors, sanction_result, live, meta)

    return {
        "address": address,
        "chain": chain,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "sanctions": sanction_result,
        "details": sanction_result,
        "chain_data": chain_data,
        "graph_data": graph_data,
        "list_versions": list_versions,
        "scoring_meta": meta,
        "verdict": verdict,
        "cached": from_cache,
        "disclaimer": (
            "Информационная оценка ончейн-рисков на основе открытых баз данных и поведения адреса. "
            "Не является юридической гарантией. Окончательное решение о транзакции принимает пользователь."
        ),
    }


def _human_verdict(level: str, factors: list, sanctions: dict, live: dict, meta: dict) -> dict:
    # ── Русскоязычный перевод причин риска ──
    ru_why = []
    for f in factors:
        desc = f.get("desc", "")
        lvl = f.get("level", "")
        if lvl in ("CRITICAL", "HIGH", "WARNING"):
            if "Direct match" in desc or sanctions.get("is_sanctioned"):
                src = sanctions.get("source") or "OFAC"
                ru_why.append(f"Прямое совпадение с санкционными базами ({src})")
            elif "Tether" in desc or live.get("tether_blacklisted"):
                ru_why.append("Адрес заморожен в официальном ончейн-блэклисте Tether USDT")
            elif "ScamSniffer" in desc:
                ru_why.append("Адрес заблокирован в базе ScamSniffer (фишинг / дрейнер кошельков)")
            elif "Ransomware" in desc:
                ru_why.append("Адрес замечен в выплатах вирусов-вымогателей (Ransomware)")
            elif "GoPlus" in desc:
                flags = [k for k in ("phishing", "mixer", "darkweb", "sanctioned") if k in desc.lower()]
                ru_why.append(f"Сигналы безопасности Web3 ({', '.join(flags) or 'подозрительная активность'})")
            elif "Inbound exposure" in desc:
                exp = meta.get("exposure_pct_in_90d", 0)
                ru_why.append(f"{exp}% входящих средств получено от рискованных контрагентов (90 дней)")
            else:
                ru_why.append(desc)

    if not ru_why:
        ru_why = ["Ончейн-угроз, санкционных меток и связей с криминальными адресами не обнаружено."]

    # ── Биржевой риск-профиль (Binance · Bybit · OKX · HTX) ──
    is_sanctioned = bool(sanctions.get("is_sanctioned") or live.get("tether_blacklisted"))
    has_fake_assets = bool(meta.get("has_fake_assets"))
    exp_pct = float(meta.get("exposure_pct_in_90d") or 0.0)
    dust_count = int(meta.get("dust_filtered") or 0)
    attribution_pct = float(meta.get("attribution_coverage_pct", 100.0))
    bridges = meta.get("bridges_detected") or []

    if has_fake_assets:
        ru_why.insert(0, "Обнаружен поддельный токен (Fake Asset Scam / Клон стейблкоина)")
        cex_status = "CRITICAL"
        cex_headline = "СТОП: обнаружен поддельный токен (Fake Asset Scam)"
        cex_color = "#ef4444"
        cex_badge = "🔴 ФЕЙКОВЫЙ АКТИВ"
        what_to_do = "Не принимайте эти активы и не отправляйте на биржу. Баланс содержит поддельные токены-клоны без реальной ликвидности."
    elif is_sanctioned or level == "CRITICAL":
        cex_status = "CRITICAL"
        cex_headline = "СТОП: высокий риск блокировки депозита на CEX"
        cex_color = "#ef4444"
        cex_badge = "🔴 РИСК ДЛЯ ДЕПОЗИТА"
        what_to_do = "Не принимайте и не отправляйте на CEX. По совпадениям со списками депозит с высокой вероятностью будет заморожен."
    elif level == "WARNING" or exp_pct >= 15.0:
        cex_status = "WARNING"
        cex_headline = "ВНИМАНИЕ: возможен ручной комплаенс (EDD) на CEX"
        cex_color = "#f59e0b"
        cex_badge = "🟡 РИСК ПРОВЕРКИ"
        what_to_do = "Повышенный риск. Не отправляйте крупную сумму на биржу без подтверждения источника средств. Запросите другой кошелёк у контрагента."
    elif level == "CAUTION":
        cex_status = "CAUTION"
        cex_headline = "УМЕРЕННЫЙ РИСК: при крупном переводе возможен доп. аудит"
        cex_color = "#eab308"
        cex_badge = "🟡 НУЖНО ВНИМАНИЕ"
        what_to_do = "Прямых санкционных меток нет, но есть косвенные сигналы или короткая история. Перед крупной суммой — тестовый перевод."
    else:
        cex_status = "SAFE"
        cex_headline = "Явных ончейн-блокеров для депозита на CEX не найдено"
        cex_color = "#10b981"
        cex_badge = "🟢 БЕЗ КРАСНЫХ ФЛАГОВ"
        what_to_do = "По открытым спискам и выборке транзакций критичных совпадений нет. Решение о приёме средств остаётся за вами / биржей."

    poison_attacks = int(meta.get("poisoning_attacks_count") or 0)
    spam_filtered = int(meta.get("spam_transactions_filtered") or 0)
    total_spam_blocked = dust_count + spam_filtered

    if poison_attacks > 0:
        ru_why.insert(0, f"Внимание: обнаружена атака спуфинга адреса ({poison_attacks} попыток Address Poisoning в истории)")

    cex_criteria = [
        {
            "name": "Санкционные списки (OFAC / EU / UN)",
            "passed": not bool(sanctions.get("is_sanctioned")),
            "note": "Чисто" if not bool(sanctions.get("is_sanctioned")) else "Обнаружено совпадение",
        },
        {
            "name": "Черный список смарт-контракта Tether USDT",
            "passed": not bool(live.get("tether_blacklisted")),
            "note": "Чисто" if not bool(live.get("tether_blacklisted")) else "Адрес в блэклисте Tether",
        },
        {
            "name": "Валидность активов (Fake Asset Shield)",
            "passed": not has_fake_assets,
            "note": "Оригинальные активы" if not has_fake_assets else "Поддельный токен!",
        },
        {
            "name": "Связи с миксерами и хаками (90 дней)",
            "passed": exp_pct < 10.0,
            "note": f"{exp_pct}% грязного объёма" if exp_pct > 0 else "0.0% (Чисто)",
        },
        {
            "name": "Прозрачность источников (% атрибуции)",
            "passed": attribution_pct >= 40.0,
            "note": f"{attribution_pct:.0f}% объема опознано" if attribution_pct > 0 else "0% (Неизвестно ≠ чисто)",
        },
        {
            "name": "Защита от спам-пыли (Anti-Dusting Shield)",
            "passed": True,
            "note": f"Защищено: {total_spam_blocked} спам-транзакций отсеяны" if total_spam_blocked > 0 else "Спам не обнаружен",
        },
    ]

    attribution_profile = {
        "coverage_pct": attribution_pct,
        "attributed_volume": meta.get("attributed_volume", 0.0),
        "unattributed_volume": meta.get("unattributed_volume", 0.0),
        "total_flow_volume": meta.get("total_flow_volume", 0.0),
        "bridges_detected": bridges,
        "honesty_note": (
            "Высокая прозрачность: практически все источники происхождения средств опознаны."
            if attribution_pct >= 80 else
            "Умеренная прозрачность: часть объема поступила с неклассифицированных кошельков. Неизвестно ≠ чисто."
            if attribution_pct >= 40 else
            "Низкое покрытие разметки: большая часть объема поступила с неразмеченных P2P/частных адресов. Неизвестно ≠ чисто."
        ),
    }

    return {
        "level": level,
        "why": ru_why[:3],
        "what_to_do": what_to_do,
        "cex_profile": {
            "status": cex_status,
            "badge": cex_badge,
            "headline": cex_headline,
            "color": cex_color,
            "criteria": cex_criteria,
            "supported_exchanges": ["Binance", "Bybit", "OKX", "HTX", "KuCoin"],
        },
        "attribution_profile": attribution_profile,
    }


def serialize_payload(result: dict) -> str:
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)

    return json.dumps(result, default=default)
