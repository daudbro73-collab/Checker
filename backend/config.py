"""Central configuration — all secrets from environment."""
import os
from functools import lru_cache
from pathlib import Path


def _load_dotenv():
    for candidate in (Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    # --- Инициализация ---
    def __init__(self):
        self._validate_secret_key()

    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "development").lower() == "production"

    def _validate_secret_key(self):
        key = os.getenv("SECRET_KEY", "")
        default_markers = ("CHANGE_ME", "change_me", "local_dev_secret", "REPLACE_WITH")
        is_weak = not key or any(m in key for m in default_markers) or len(key) < 32
        if is_weak:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env == "production":
                raise RuntimeError(
                    "\n\n❌ SECRET_KEY не установлен или слабый!\n"
                    "Сгенерируйте ключ: python3 -c \"import secrets; print(secrets.token_hex(32))\"\n"
                    "Установите в .env: SECRET_KEY=<сгенерированный_ключ>\n"
                )
            import warnings
            warnings.warn(
                "⚠️  SECRET_KEY не задан или слабый — используется временный ключ. "
                "Все сессии сбросятся при перезапуске. Установите SECRET_KEY в .env.",
                stacklevel=3,
            )

    def get_cors_origins(self) -> list:
        """Returns CORS allowed origins, excluding localhost in production."""
        origins = [
            self.WEBAPP_URL,
            "https://web.telegram.org",
            "https://t.me",
        ]
        if not self.is_production:
            origins += [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:8080",
                "http://127.0.0.1:8080",
            ]
        return origins

    SECRET_KEY: str = os.getenv("SECRET_KEY", "") or ("dev_" + __import__("secrets").token_hex(16))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7)

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://localhost/webapp")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./aml.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    PRICE_PER_CHECK: float = _float("PRICE_PER_CHECK", 1.0)
    SIGNUP_BONUS: float = _float("SIGNUP_BONUS", 1.0)
    FREE_CHECKS_PER_DAY: int = _int("FREE_CHECKS_PER_DAY", 1)  # trial checks (full product demo)
    USD_RUB_RATE: float = _float("USD_RUB_RATE", 90.0)

    PAYMENT_ADDRESS_ETH: str = os.getenv("PAYMENT_ADDRESS_ETH", "")
    PAYMENT_ADDRESS_TRON: str = os.getenv("PAYMENT_ADDRESS_TRON", "")
    PAYMENT_ADDRESS_BSC: str = os.getenv("PAYMENT_ADDRESS_BSC", "")
    PAYMENT_ADDRESS_SOL: str = os.getenv("PAYMENT_ADDRESS_SOL", "")

    # Deposit pool: start with 1 address; raise DEPOSIT_POOL_SIZE as you add more
    # Comma-separated; first N=DEPOSIT_POOL_SIZE are active, rest = standby
    DEPOSIT_POOL_TRON: str = os.getenv("DEPOSIT_POOL_TRON", "")
    DEPOSIT_POOL_ETH: str = os.getenv("DEPOSIT_POOL_ETH", "")
    DEPOSIT_POOL_BSC: str = os.getenv("DEPOSIT_POOL_BSC", "")
    DEPOSIT_POOL_SOL: str = os.getenv("DEPOSIT_POOL_SOL", "")
    DEPOSIT_POOL_SIZE: int = _int("DEPOSIT_POOL_SIZE", 1)

    TREASURY_ADDRESS_TRON: str = os.getenv("TREASURY_ADDRESS_TRON", "")
    TREASURY_ADDRESS_ETH: str = os.getenv("TREASURY_ADDRESS_ETH", "")
    TREASURY_ADDRESS_BSC: str = os.getenv("TREASURY_ADDRESS_BSC", "")
    TREASURY_ADDRESS_SOL: str = os.getenv("TREASURY_ADDRESS_SOL", "")
    TREASURY_SWEEP_HOUR_UTC: int = _int("TREASURY_SWEEP_HOUR_UTC", 3)
    # Auto HD generation (off until DEPOSIT_HD_MNEMONIC is set securely)
    DEPOSIT_AUTO_GENERATE: bool = os.getenv("DEPOSIT_AUTO_GENERATE", "false").lower() == "true"
    DEPOSIT_HD_MNEMONIC: str = os.getenv("DEPOSIT_HD_MNEMONIC", "")  # never commit
    DEPOSIT_HD_INDEX_TRON: int = _int("DEPOSIT_HD_INDEX_TRON", 0)
    DEPOSIT_HD_INDEX_ETH: int = _int("DEPOSIT_HD_INDEX_ETH", 0)

    # Wave B: address monitoring recheck interval (default 6h)
    MONITOR_RECHECK_INTERVAL_SECONDS: int = _int("MONITOR_RECHECK_INTERVAL_SECONDS", 21600)
    MONITOR_MAX_PER_USER: int = _int("MONITOR_MAX_PER_USER", 20)
    # Future: YOOKASSA_SHOP_ID, YOOKASSA_SECRET, TBANK_TERMINAL_KEY, etc.

    REFERRER_BONUS_RATE: float = _float("REFERRER_BONUS_RATE", 0.10)
    REFERRED_USER_FIRST_TOPUP_BONUS: float = _float("REFERRED_USER_FIRST_TOPUP_BONUS", 1.0)
    REFERRAL_CHECK_BONUS: float = _float("REFERRAL_CHECK_BONUS", 1.0)

    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    ALLOW_DEV_TELEGRAM_AUTH: bool = os.getenv("ALLOW_DEV_TELEGRAM_AUTH", "false").lower() == "true"

    ALLOWED_CHAINS = frozenset({"ETH", "TRON", "BTC", "BSC", "TON", "SOL"})

    # Packages v2: $1 single · 10@$7 ($0.70) · 20@$10 ($0.50)
    PACKAGES = {
        "pack_10": {"checks": 10, "price": 7.0, "label": "10 проверок ($0.70/чек)", "badge": "Выгода 30%"},
        "pack_20": {"checks": 20, "price": 10.0, "label": "20 проверок ($0.50/чек)", "badge": "ХИТ · +10 за +$3"},
    }

    API_PLANS = {
        "api_starter": {"price": 49.0, "quota": 500, "label": "API Starter"},
        "api_pro": {"price": 199.0, "quota": 3000, "label": "API Pro"},
    }
    VERIFY_BASE_URL: str = os.getenv("VERIFY_BASE_URL", "https://verify.amlguard.io/p")

    # OTC subscription plan — used by billing.apply_otc_subscription()
    OTC_SUBSCRIPTION: dict = {
        "days": _int("OTC_SUB_DAYS", 30),
        "checks_per_month": _int("OTC_SUB_CHECKS_PER_MONTH", 100),
        "price": _float("OTC_SUB_PRICE", 49.0),
        "label": "OTC Monthly",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
