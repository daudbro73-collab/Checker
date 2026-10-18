"""
Тесты: TRON Base58→hex конвертация для Tether blacklist.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.live_signals import _tron_address_param_placeholder


class TestTronAddressParam:
    def test_base58_address_returns_64_hex_chars(self):
        # Известный TRON адрес
        result = _tron_address_param_placeholder("TAaWbC862cHV9vXzbxoCJZNUuQLJLKh9dy")
        assert len(result) == 64, f"Expected 64 chars, got {len(result)}: {result!r}"
        assert all(c in "0123456789abcdef" for c in result), "Result must be hex"

    def test_hex_format_address_works(self):
        # hex формат 41...
        result = _tron_address_param_placeholder("41" + "ab" * 20)
        assert len(result) == 64

    def test_empty_address_returns_empty(self):
        assert _tron_address_param_placeholder("") == ""
        assert _tron_address_param_placeholder(None) == ""

    def test_invalid_address_returns_empty(self):
        assert _tron_address_param_placeholder("invalid_address_xyz") == ""

    def test_eth_address_returns_empty(self):
        # ETH адрес не должен обрабатываться
        result = _tron_address_param_placeholder("0xAbC123" + "0" * 34)
        assert result == ""

    def test_result_is_not_all_zeros_for_valid_address(self):
        # Убеждаемся что результат не просто зеро-паддинг
        result = _tron_address_param_placeholder("TAaWbC862cHV9vXzbxoCJZNUuQLJLKh9dy")
        assert result != "0" * 64
