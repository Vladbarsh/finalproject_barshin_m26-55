"""Настройки источников курсов."""

import os
from dataclasses import dataclass, field

from valutatrade_hub.infra.settings import SettingsLoader


@dataclass
class ParserConfig:
    """Общие параметры обоих HTTP-клиентов."""

    EXCHANGERATE_API_KEY: str = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", ""), repr=False
    )
    COINGECKO_API_KEY: str = field(
        default_factory=lambda: os.getenv("COINGECKO_API_KEY", ""), repr=False
    )
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    EXCHANGERATE_OPEN_URL: str = "https://open.er-api.com/v6/latest/USD"
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )
    REQUEST_TIMEOUT: int = field(
        default_factory=lambda: SettingsLoader().get("request_timeout")
    )
    REQUEST_ATTEMPTS: int = 3
    RETRY_DELAY: float = 0.4

    def __post_init__(self):
        if self.BASE_CURRENCY != "USD":
            raise ValueError("Для источников базовая валюта должна быть USD")
        if any(code not in self.CRYPTO_ID_MAP for code in self.CRYPTO_CURRENCIES):
            raise ValueError("В CRYPTO_ID_MAP отсутствует ID валюты")
