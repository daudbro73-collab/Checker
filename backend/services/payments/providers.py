"""
Pluggable payment methods.

Current: crypto_usdt (TRC-20 / ETH) via rotating deposit pool
Planned: sbp (RUB), card (RUB), telegram_stars
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import get_settings

settings = get_settings()


@dataclass
class CheckoutSession:
    provider: str
    status: str  # pending | requires_action | completed | failed
    amount: float
    currency: str  # USD | RUB | XTR
    product: str
    instructions: Dict[str, Any] = field(default_factory=dict)
    external_id: Optional[str] = None
    message: str = ""


class PaymentProvider(ABC):
    id: str
    label: str
    currencies: List[str]
    enabled: bool = False

    @abstractmethod
    async def create_checkout(self, *, user_id: int, product: str, amount_usd: float, meta: dict) -> CheckoutSession:
        ...

    @abstractmethod
    async def confirm(self, *, user_id: int, payload: dict) -> CheckoutSession:
        ...

    def catalog_entry(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "currencies": self.currencies,
            "enabled": self.enabled,
            "status": "live" if self.enabled else "coming_soon",
        }


class CryptoUsdtProvider(PaymentProvider):
    id = "crypto_usdt"
    label = "USDT (TRON / BSC / SOL / ETH)"
    currencies = ["USDT", "USD"]

    def __init__(self):
        self.enabled = True

    async def create_checkout(self, *, user_id: int, product: str, amount_usd: float, meta: dict) -> CheckoutSession:
        chain = (meta.get("chain") or "TRON").upper()
        address = meta.get("deposit_address") or ""
        slot = meta.get("deposit_slot")
        pool_note = f" (deposit slot {slot})" if slot else ""
        return CheckoutSession(
            provider=self.id,
            status="requires_action",
            amount=amount_usd,
            currency="USDT",
            product=product,
            instructions={
                "type": "crypto_transfer",
                "chain": chain,
                "address": address,
                "amount": amount_usd,
                "asset": "USDT",
                "pool_slot": slot,
                "expires_in": meta.get("expires_in", 300),
                "reserved_until": meta.get("reserved_until"),
                "steps": [
                    f"Send exactly {amount_usd} USDT on {chain} to the address below",
                    "Paste the transaction hash to confirm",
                    "Sender is screened before balance is credited",
                ],
            },
            message=f"Pay to assigned deposit address{pool_note}",
        )

    async def confirm(self, *, user_id: int, payload: dict) -> CheckoutSession:
        return CheckoutSession(
            provider=self.id,
            status="pending",
            amount=float(payload.get("amount") or 0),
            currency="USDT",
            product=payload.get("product") or "balance",
            instructions=payload,
            message="Use /payments/confirm with tx_hash",
        )


class SbpProvider(PaymentProvider):
    id = "sbp"
    label = "СБП (RUB)"
    currencies = ["RUB"]
    enabled = False

    async def create_checkout(self, *, user_id: int, product: str, amount_usd: float, meta: dict) -> CheckoutSession:
        rub = round(amount_usd * float(meta.get("usd_rub_rate") or settings.USD_RUB_RATE), 2)
        return CheckoutSession(
            provider=self.id,
            status="coming_soon",
            amount=rub,
            currency="RUB",
            product=product,
            instructions={"type": "sbp_qr", "amount_rub": rub, "amount_usd": amount_usd},
            message="SBP payments coming soon",
        )

    async def confirm(self, *, user_id: int, payload: dict) -> CheckoutSession:
        raise NotImplementedError("SBP webhook confirm not configured")


class CardRubProvider(PaymentProvider):
    id = "card_rub"
    label = "Банковская карта (RUB)"
    currencies = ["RUB"]
    enabled = False

    async def create_checkout(self, *, user_id: int, product: str, amount_usd: float, meta: dict) -> CheckoutSession:
        rub = round(amount_usd * float(meta.get("usd_rub_rate") or settings.USD_RUB_RATE), 2)
        return CheckoutSession(
            provider=self.id,
            status="coming_soon",
            amount=rub,
            currency="RUB",
            product=product,
            instructions={"type": "card_redirect", "amount_rub": rub},
            message="Card payments coming soon",
        )

    async def confirm(self, *, user_id: int, payload: dict) -> CheckoutSession:
        raise NotImplementedError("Card webhook confirm not configured")


class TelegramStarsProvider(PaymentProvider):
    id = "telegram_stars"
    label = "Telegram Stars (⭐️)"
    currencies = ["XTR"]

    def __init__(self):
        self.enabled = bool(settings.BOT_TOKEN)

    async def create_checkout(self, *, user_id: int, product: str, amount_usd: float, meta: dict) -> CheckoutSession:
        import json
        import httpx
        from services.payments.stars import usd_to_stars

        stars = usd_to_stars(amount_usd)

        # Человекопонятные названия продуктов для инвойса
        title = "1 Проверка AML Guard"
        description = "Мгновенный ончейн-аудит криптокошелька на санкции, фейковые активы и риски"

        if product in settings.PACKAGES:
            pack = settings.PACKAGES[product]
            title = f"AML Guard: {pack.get('label', 'Пакет проверок')}"
            description = f"Пакет из {pack.get('checks', 10)} проверок без срока действия"
        elif product == "balance":
            title = f"Пополнение баланса AML Guard (${amount_usd:.2f})"
            description = f"Пополнение личного счета на ${amount_usd:.2f} USD"

        bot_token = get_settings().BOT_TOKEN
        if not bot_token:
            return CheckoutSession(
                provider=self.id,
                status="failed",
                amount=stars,
                currency="XTR",
                product=product,
                instructions={"type": "telegram_stars_invoice", "stars": stars, "error": "BOT_TOKEN not configured"},
                message="Telegram Bot Token не настроен в .env",
            )

        invoice_payload = json.dumps({
            "user_id": user_id,
            "product": product,
            "stars": stars,
            "amount_usd": amount_usd,
        })

        url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
        body = {
            "title": title[:32],  # Telegram title limit: 1-32 chars
            "description": description[:255],
            "payload": invoice_payload,
            "currency": "XTR",
            "prices": [{"label": title[:32], "amount": stars}],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=body)
                data = resp.json()
                if not data.get("ok"):
                    err_desc = data.get("description", "Unknown Telegram API error")
                    return CheckoutSession(
                        provider=self.id,
                        status="failed",
                        amount=stars,
                        currency="XTR",
                        product=product,
                        instructions={"type": "telegram_stars_invoice", "stars": stars, "error": err_desc},
                        message=f"Ошибка создания инвойса Stars: {err_desc}",
                    )

                invoice_link = data["result"]
                return CheckoutSession(
                    provider=self.id,
                    status="requires_action",
                    amount=stars,
                    currency="XTR",
                    product=product,
                    instructions={
                        "type": "telegram_stars_invoice",
                        "invoice_link": invoice_link,
                        "stars": stars,
                        "title": title,
                    },
                    message="Инвойс Telegram Stars успешно сформирован",
                )
        except Exception as exc:
            return CheckoutSession(
                provider=self.id,
                status="failed",
                amount=stars,
                currency="XTR",
                product=product,
                instructions={"type": "telegram_stars_invoice", "stars": stars, "error": str(exc)},
                message=f"Сбой соединения с Telegram API: {exc}",
            )

    async def confirm(self, *, user_id: int, payload: dict) -> CheckoutSession:
        return CheckoutSession(
            provider=self.id,
            status="completed",
            amount=float(payload.get("stars") or 0),
            currency="XTR",
            product=payload.get("product") or "single_check",
            instructions=payload,
            message="Telegram Stars confirmed via bot webhook",
        )


_PROVIDERS: Dict[str, PaymentProvider] = {
    p.id: p
    for p in (CryptoUsdtProvider(), SbpProvider(), CardRubProvider(), TelegramStarsProvider())
}


def list_providers() -> List[dict]:
    return [p.catalog_entry() for p in _PROVIDERS.values()]


def get_provider(method: str) -> PaymentProvider:
    p = _PROVIDERS.get(method)
    if not p:
        raise KeyError(method)
    return p


def product_price_usd(product: str) -> float:
    if product == "balance" or product == "single_check":
        return settings.PRICE_PER_CHECK
    if product in settings.PACKAGES:
        return float(settings.PACKAGES[product]["price"])
    if product in settings.API_PLANS:
        return float(settings.API_PLANS[product]["price"])
    raise KeyError(f"Unknown product: {product}")


def product_catalog() -> list:
    items = [
        {
            "id": "single_check",
            "label": "1 check",
            "price_usd": settings.PRICE_PER_CHECK,
            "effective": settings.PRICE_PER_CHECK,
            "credits": 1,
            "type": "credit",
        }
    ]
    for pid, pack in settings.PACKAGES.items():
        items.append({
            "id": pid,
            "label": pack["label"],
            "price_usd": pack["price"],
            "effective": round(pack["price"] / pack["checks"], 2),
            "credits": pack["checks"],
            "type": "package",
        })
    return items
