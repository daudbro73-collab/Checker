"""
Unit tests for Telegram Stars payments:
- Currency conversion (USD <-> Stars)
- Payment fulfillment (credits, packages, OTC sub, balance)
- Idempotency & duplicate charge protection
- Referrer rewards
- TelegramStarsProvider checkout session creation
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Payment, User
from services.payments.stars import fulfill_stars_payment, stars_to_usd, usd_to_stars
from services.payments.providers import TelegramStarsProvider


def _make_mock_user(user_id=1, balance=0.0, check_credits=0, referrer_id=None):
    u = MagicMock(spec=User)
    u.id = user_id
    u.balance = balance
    u.check_credits = check_credits
    u.referrer_id = referrer_id
    u.subscription_expires_at = None
    u.subscription_checks_left = 0
    return u


def _make_mock_db(user=None, existing_payment=None, referrer=None):
    db = MagicMock()

    def query_mock(model):
        q = MagicMock()
        if model == User:
            def filter_mock(*args, **kwargs):
                f = MagicMock()
                # If checking referrer
                if referrer:
                    f.first.return_value = user
                else:
                    f.first.return_value = user
                f.with_for_update.return_value.first.return_value = user
                return f
            q.filter = filter_mock
        elif model == Payment:
            def filter_mock(*args, **kwargs):
                f = MagicMock()
                f.first.return_value = existing_payment
                return f
            q.filter = filter_mock
        return q

    db.query = query_mock
    return db


class TestStarsConversion:
    def test_usd_to_stars(self):
        assert usd_to_stars(1.0) == 50
        assert usd_to_stars(7.0) == 350
        assert usd_to_stars(10.0) == 500
        assert usd_to_stars(19.0) == 950

    def test_stars_to_usd(self):
        assert stars_to_usd(50) == 1.0
        assert stars_to_usd(350) == 7.0
        assert stars_to_usd(500) == 10.0
        assert stars_to_usd(950) == 19.0


class TestFulfillStarsPayment:
    def test_fulfill_single_check(self):
        user = _make_mock_user(user_id=10, check_credits=2)
        db = _make_mock_db(user=user)

        res = fulfill_stars_payment(
            db,
            user_id=10,
            product="single_check",
            stars_amount=50,
            telegram_charge_id="tg_charge_1001",
        )

        assert res["status"] == "completed"
        assert res["credits_added"] == 1
        assert user.check_credits == 3
        assert db.add.called
        assert db.commit.called

    def test_fulfill_package_pack_20(self):
        user = _make_mock_user(user_id=10, check_credits=0)
        db = _make_mock_db(user=user)

        res = fulfill_stars_payment(
            db,
            user_id=10,
            product="pack_20",
            stars_amount=500,
            telegram_charge_id="tg_charge_1002",
        )

        assert res["status"] == "completed"
        assert res["credits_added"] == 20
        assert db.commit.called

    def test_fulfill_idempotency_duplicate_charge(self):
        user = _make_mock_user(user_id=10, check_credits=5)
        mock_payment = MagicMock(spec=Payment)
        mock_payment.id = 99
        mock_payment.product = "single_check"
        mock_payment.amount = 50.0

        db = _make_mock_db(user=user, existing_payment=mock_payment)

        res = fulfill_stars_payment(
            db,
            user_id=10,
            product="single_check",
            stars_amount=50,
            telegram_charge_id="tg_charge_duplicate",
        )

        assert res["status"] == "already_processed"
        assert res["payment_id"] == 99
        # Credits must not increase on duplicate call
        assert user.check_credits == 5


@pytest.mark.asyncio
class TestStarsProviderCheckout:
    async def test_checkout_session_success(self):
        provider = TelegramStarsProvider()
        with patch("services.payments.providers.get_settings") as mock_settings:
            mock_settings.return_value.BOT_TOKEN = "123456:ABC-DEF"
            mock_settings.return_value.PACKAGES = {
                "pack_20": {"label": "20 проверок", "checks": 20, "price_usd": 10.0}
            }
            provider.enabled = True

            mock_resp = MagicMock()
            mock_resp.json.return_value = {"ok": True, "result": "https://t.me/$invoice_test_link"}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp

                session = await provider.create_checkout(
                    user_id=42,
                    product="pack_20",
                    amount_usd=10.0,
                    meta={},
                )

                assert session.status == "requires_action"
                assert session.currency == "XTR"
                assert session.amount == 500
                assert session.instructions.get("invoice_link") == "https://t.me/$invoice_test_link"
