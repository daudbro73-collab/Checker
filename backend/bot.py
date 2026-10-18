"""Telegram bot — Mini App entry + Wave B monitor helpers."""
import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import get_settings

logging.basicConfig(level=logging.INFO)
settings = get_settings()

BOT_TOKEN = settings.BOT_TOKEN
WEBAPP_URL = settings.WEBAPP_URL

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN env var is required to run the bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ADDR_RE = re.compile(
    r"^(T[1-9A-HJ-NP-Za-km-z]{33}|0x[a-fA-F0-9]{40}|bc1[a-z0-9]{25,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$"
)


def _open_app_kb(path: str = "") -> InlineKeyboardMarkup:
    url = WEBAPP_URL.rstrip("/") + (path or "")
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Open AML Guard", web_app=WebAppInfo(url=url))]]
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Welcome to AML Guard\n\n"
        "Fast wallet check before you send: sanctions + on-chain behaviour.\n"
        "Explainable score, bilingual PDF, ETH / TRON / BTC.\n\n"
        "Commands:\n"
        "/check <address> — open Mini App with this wallet\n"
        "/monitor — how address monitoring works\n\n"
        "Informational service — not legal or compliance advice.",
        reply_markup=_open_app_kb(),
    )


@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    """Deep-link style: /check Txxx → open Mini App (user pastes / checks there)."""
    parts = (message.text or "").split(maxsplit=1)
    addr = parts[1].strip() if len(parts) > 1 else ""
    if not addr or not ADDR_RE.match(addr):
        await message.answer(
            "Usage: /check <wallet address>\n"
            "Example: /check TAaWbC862cHV9vXzbxoCJZNUuQLJLKh9dy",
            reply_markup=_open_app_kb(),
        )
        return
    # Mini App can read start_param later; for now show address + open button
    await message.answer(
        f"Ready to check:\n`{addr}`\n\nOpen the app and paste the address (or use Monitor after a paid check).",
        parse_mode="Markdown",
        reply_markup=_open_app_kb(),
    )


@dp.message(Command("monitor"))
async def cmd_monitor(message: types.Message):
    await message.answer(
        "Address monitoring (Wave B)\n\n"
        "1. Open Mini App → check a wallet\n"
        "2. Tap Monitor → optional label (address book)\n"
        "3. We recheck every few hours\n"
        "4. If risk level/score changes → Telegram alert\n\n"
        "Login via Telegram in the app so we know your chat id.\n"
        "Up to 20 watched wallets per account.",
        reply_markup=_open_app_kb(),
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "/start — open Mini App\n"
        "/check <address> — prepare a wallet check\n"
        "/monitor — monitoring help\n"
        "/help — this message"
    )


# ── Telegram Stars Payment Handlers ──────────────────────────────────────────

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Confirm readiness to accept Stars payment within 10 seconds."""
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Fulfill Stars payment when Telegram confirms star deduction."""
    import json
    from database import SessionLocal, User
    from services.payments.stars import fulfill_stars_payment

    sp = message.successful_payment
    if not sp:
        return

    telegram_charge_id = sp.telegram_payment_charge_id
    provider_charge_id = sp.provider_payment_charge_id
    stars_amount = sp.total_amount
    payload_str = sp.invoice_payload

    user_id = None
    product = "single_check"
    try:
        data = json.loads(payload_str)
        user_id = data.get("user_id")
        product = data.get("product") or "single_check"
    except Exception as e:
        logging.error("Failed to parse invoice payload %s: %s", payload_str, e)

    if not user_id and message.from_user:
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.telegram_id == message.from_user.id).first()
            if u:
                user_id = u.id
        finally:
            db.close()

    if not user_id:
        await message.answer("⚠️ Ошибка: аккаунт не найден. Пожалуйста, обратитесь в поддержку.")
        return

    db = SessionLocal()
    try:
        res = fulfill_stars_payment(
            db,
            user_id=user_id,
            product=product,
            stars_amount=stars_amount,
            telegram_charge_id=telegram_charge_id,
            provider_charge_id=provider_charge_id,
        )
        credits_added = res.get("credits_added", 0)
        credits_total = res.get("check_credits", 0)
        new_balance = res.get("new_balance", 0.0)

        msg = (
            f"🎉 <b>Оплата получена!</b>\n\n"
            f"Списано: <b>{stars_amount} ⭐️ Telegram Stars</b>\n"
        )
        if credits_added:
            msg += f"Начислено проверок: <b>+{credits_added}</b> (всего на балансе: {credits_total})\n"
        else:
            msg += f"Баланс пополнен на: <b>+${res.get('amount_usd', 0):.2f}</b> (баланс: ${new_balance:.2f})\n"

        msg += "\nНажмите кнопку ниже, чтобы перейти к проверке кошелька:"
        await message.answer(msg, parse_mode="HTML", reply_markup=_open_app_kb())
    except Exception as e:
        logging.error("Error fulfilling Stars payment: %s", e)
        await message.answer(
            f"⚠️ Ошибка при начислении: {e}\nПлатеж зафиксирован (ID: {telegram_charge_id})."
        )
    finally:
        db.close()


async def main():
    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
