"""Виды валют и общий реестр."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError
from valutatrade_hub.core.utils import normalize_code, number


class Currency(ABC):
    """Общие сведения о валюте и интерфейс представления."""

    def __init__(self, name, code):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        self.name = name.strip()
        self.code = normalize_code(code)

    @abstractmethod
    def get_display_info(self):
        """Возвращает описание валюты для интерфейса."""


class FiatCurrency(Currency):
    """Фиатная валюта со страной или зоной эмиссии."""

    def __init__(self, name, code, issuing_country):
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Укажите страну или зону эмиссии")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self):
        """Возвращает название и эмитента."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и справочной капитализацией."""

    def __init__(self, name, code, algorithm, market_cap):
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Укажите алгоритм")
        self.algorithm = algorithm.strip()
        self.market_cap = number(market_cap, allow_zero=True)

    def get_display_info(self):
        """Возвращает алгоритм и справочную капитализацию."""
        cap = format(self.market_cap, ".3g").replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {cap})"
        )


# Капитализация — учебная справка, котировки поступают отдельно из API.
CURRENCIES = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Proof of Stake", 4e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 7e10),
}


def get_currency(code):
    """Находит поддерживаемую валюту по коду."""
    code = normalize_code(code)
    if code not in CURRENCIES:
        raise CurrencyNotFoundError(code)
    return CURRENCIES[code]
