"""
Тесты: атомарное списание баланса (защита от race condition) и тарифная сетка v2.
"""
import pytest
from unittest.mock import MagicMock, patch

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.billing import charge_for_check, can_afford_check, apply_package
from config import get_settings

settings = get_settings()


def _make_user(balance=0.0, check_credits=0, sub_active=False, free_check_used=True):
    user = MagicMock()
    user.id = 1
    user.balance = balance
    user.check_credits = check_credits
    user.subscription_expires_at = None
    user.subscription_checks_left = 0
    user.free_check_used = free_check_used
    return user


def _make_db(locked_user):
    """Мок сессии: with_for_update().first() → locked_user."""
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = locked_user
    return db


class TestCanAffordCheck:
    def test_can_afford_with_free_trial(self):
        user = _make_user(balance=0.0, check_credits=0, free_check_used=False)
        assert can_afford_check(user) is True

    def test_can_afford_with_credits(self):
        user = _make_user(check_credits=3, free_check_used=True)
        assert can_afford_check(user) is True

    def test_cannot_afford_zero_balance_no_credits(self):
        user = _make_user(balance=0.0, check_credits=0, free_check_used=True)
        assert can_afford_check(user) is False

    def test_can_afford_with_balance(self):
        price = settings.PRICE_PER_CHECK
        user = _make_user(balance=price, free_check_used=True)
        assert can_afford_check(user) is True

    def test_cannot_afford_insufficient_balance(self):
        price = settings.PRICE_PER_CHECK
        user = _make_user(balance=round(price - 0.01, 4), free_check_used=True)
        assert can_afford_check(user) is False


class TestChargeForCheck:
    def test_charge_free_trial_first(self):
        locked = _make_user(balance=10.0, check_credits=5, free_check_used=False)
        user = _make_user(balance=10.0, check_credits=5, free_check_used=False)
        db = _make_db(locked)

        method = charge_for_check(db, user)

        assert method == "free_trial"
        assert locked.free_check_used is True
        assert locked.check_credits == 5  # credits not touched
        assert locked.balance == 10.0      # balance not touched

    def test_charge_credits_when_free_trial_used(self):
        locked = _make_user(check_credits=5, balance=10.0, free_check_used=True)
        user = _make_user(check_credits=5, balance=10.0, free_check_used=True)
        db = _make_db(locked)

        method = charge_for_check(db, user)

        assert method == "credit"
        assert locked.check_credits == 4   # списан один кредит

    def test_charge_balance_when_no_credits(self):
        price = settings.PRICE_PER_CHECK
        locked = _make_user(balance=price * 3, check_credits=0, free_check_used=True)
        user = _make_user(balance=price * 3, check_credits=0, free_check_used=True)
        db = _make_db(locked)

        method = charge_for_check(db, user)

        assert method == "balance"
        assert abs(locked.balance - price * 2) < 0.0001

    def test_raises_402_insufficient_balance(self):
        from fastapi import HTTPException
        locked = _make_user(balance=0.0, check_credits=0, free_check_used=True)
        user = _make_user(balance=0.0, check_credits=0, free_check_used=True)
        db = _make_db(locked)

        with pytest.raises(HTTPException) as exc_info:
            charge_for_check(db, user)
        assert exc_info.value.status_code == 402

    def test_raises_404_if_user_not_found(self):
        from fastapi import HTTPException
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
        user = _make_user(free_check_used=True)

        with pytest.raises(HTTPException) as exc_info:
            charge_for_check(db, user)
        assert exc_info.value.status_code == 404

    def test_db_commit_called(self):
        locked = _make_user(check_credits=2, free_check_used=True)
        user = _make_user(check_credits=2, free_check_used=True)
        db = _make_db(locked)

        charge_for_check(db, user)
        db.commit.assert_called_once()


class TestPricingLadderV2:
    def test_packages_v2_structure(self):
        assert "pack_10" in settings.PACKAGES
        assert "pack_20" in settings.PACKAGES
        assert settings.PACKAGES["pack_10"]["price"] == 7.0
        assert settings.PACKAGES["pack_10"]["checks"] == 10
        assert settings.PACKAGES["pack_20"]["price"] == 10.0
        assert settings.PACKAGES["pack_20"]["checks"] == 20

    def test_apply_pack_10(self):
        user = _make_user(check_credits=0)
        db = MagicMock()
        pack = apply_package(db, user, "pack_10")
        assert pack["price"] == 7.0
        assert user.check_credits == 10

    def test_apply_pack_20(self):
        user = _make_user(check_credits=2)
        db = MagicMock()
        pack = apply_package(db, user, "pack_20")
        assert pack["price"] == 10.0
        assert user.check_credits == 22
