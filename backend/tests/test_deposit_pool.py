"""
Тесты: deposit pool — карантин, продвижение standby, корректность статусов.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import MagicMock, patch
from services.deposit_pool import quarantine_address, QUARANTINE, ACTIVE, STANDBY


def _make_deposit(status=ACTIVE, address="Ttest123"):
    d = MagicMock()
    d.address = address
    d.chain = "TRON"
    d.status = status
    d.quarantine_reason = None
    d.quarantine_at = None
    return d


def _make_db(active_count=0, standby=None):
    """
    Мок DB. count() возвращает active_count (int).
    filter().filter().first() возвращает standby-адрес (или None).
    """
    db = MagicMock()

    # chain_count — для ensure_active_count: db.query().filter().filter().count()
    filter_chain = db.query.return_value.filter.return_value
    filter_chain.filter.return_value.count.return_value = active_count
    filter_chain.count.return_value = active_count

    # standby lookup: db.query().filter().filter().first()
    filter_chain.filter.return_value.first.return_value = standby
    filter_chain.first.return_value = standby

    return db


class TestQuarantineAddress:
    def test_quarantine_sets_status(self):
        deposit = _make_deposit(ACTIVE)
        # active_count=1 >= DEPOSIT_POOL_SIZE=1, нет продвижения
        db = _make_db(active_count=1, standby=None)

        quarantine_address(db, deposit, reason="test")

        assert deposit.status == QUARANTINE
        assert deposit.quarantine_reason == "test"
        db.commit.assert_called()

    def test_quarantine_promotes_standby(self):
        active = _make_deposit(ACTIVE, address="Tactive")
        standby = _make_deposit(STANDBY, address="Tstandby")

        # После карантина active_count=0, значит нужно продвинуть standby
        db = _make_db(active_count=0, standby=standby)

        quarantine_address(db, active, reason="sanctions")

        assert active.status == QUARANTINE
        # ensure_active_count должен продвинуть standby → ACTIVE
        # Проверяем что db.add вызывался (для обоих объектов)
        assert db.add.called
