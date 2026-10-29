"""HTTP-клиенты с единым результатом fetch_rates."""

import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import number
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Возвращает пары валют и положительные числовые курсы."""

    source = ""
    source_key = ""

    def __init__(self, config=None, session=None):
        self.config = config or ParserConfig()
        self.session = session or requests.Session()
        self.meta = {}

    def _request(self, url, **kwargs):
        started = time.monotonic()
        attempts = self.config.REQUEST_ATTEMPTS
        for attempt in range(attempts):
            try:
                response = self.session.get(
                    url, timeout=self.config.REQUEST_TIMEOUT, **kwargs
                )
                if response.status_code >= 500 and attempt + 1 < attempts:
                    time.sleep(self.config.RETRY_DELAY * (attempt + 1))
                    continue
                if response.status_code != 200:
                    raise ApiRequestError(f"{self.source}: HTTP {response.status_code}")
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Ожидался JSON-объект")
                break
            except (requests.Timeout, requests.ConnectionError) as error:
                if attempt + 1 < attempts:
                    time.sleep(self.config.RETRY_DELAY * (attempt + 1))
                    continue
                raise ApiRequestError(
                    f"{self.source}: {type(error).__name__}"
                ) from None
            except requests.RequestException as error:
                # Текст requests может содержать URL с ключом.
                raise ApiRequestError(
                    f"{self.source}: {type(error).__name__}"
                ) from None
            except (ValueError, TypeError) as error:
                raise ApiRequestError(f"{self.source}: неверный JSON-ответ") from error
        self.meta = {
            "request_ms": round((time.monotonic() - started) * 1000),
            "status_code": response.status_code,
        }
        return data

    @abstractmethod
    def fetch_rates(self):
        """Возвращает dict вида BTC_USD -> 59337.21."""


class CoinGeckoClient(BaseApiClient):
    """Получает цены криптовалют по их ID."""

    source = "CoinGecko"
    source_key = "coingecko"

    def fetch_rates(self):
        """Нормализует котировки CoinGecko в пары к USD."""
        config = self.config
        ids = [config.CRYPTO_ID_MAP[code] for code in config.CRYPTO_CURRENCIES]
        headers = (
            {"x-cg-demo-api-key": config.COINGECKO_API_KEY}
            if config.COINGECKO_API_KEY
            else {}
        )
        data = self._request(
            config.COINGECKO_URL,
            params={
                "ids": ",".join(ids),
                "vs_currencies": "usd",
                "include_last_updated_at": "true",
            },
            headers=headers,
        )
        try:
            result = {
                f"{code}_USD": number(data[config.CRYPTO_ID_MAP[code]]["usd"])
                for code in config.CRYPTO_CURRENCIES
            }
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ApiRequestError(
                "CoinGecko: отсутствует корректная цена валюты"
            ) from error
        self.meta["raw_ids"] = ids
        self.meta["provider_timestamps"] = {
            raw_id: data[raw_id].get("last_updated_at") for raw_id in ids
        }
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Получает фиатные курсы через персональный или открытый API."""

    source = "ExchangeRate-API"
    source_key = "exchangerate"

    def fetch_rates(self):
        """Преобразует USD→валюта в валюту→USD."""
        config = self.config
        if config.EXCHANGERATE_API_KEY:
            url = (
                f"{config.EXCHANGERATE_API_URL}/"
                f"{config.EXCHANGERATE_API_KEY}/latest/USD"
            )
            field_name = "conversion_rates"
        else:
            url, field_name = config.EXCHANGERATE_OPEN_URL, "rates"
        data = self._request(url)
        if data.get("result") != "success":
            known = {
                "invalid-key",
                "inactive-account",
                "quota-reached",
                "unsupported-code",
            }
            reason = data.get("error-type")
            if not isinstance(reason, str) or reason not in known:
                reason = "ошибка источника"
            raise ApiRequestError(f"ExchangeRate-API: {reason}")
        try:
            if data["base_code"] != "USD":
                raise ValueError("Неверная базовая валюта")
            result = {
                f"{code}_USD": number(1 / number(data[field_name][code]))
                for code in config.FIAT_CURRENCIES
            }
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ApiRequestError(
                "ExchangeRate-API: неверные фиатные котировки"
            ) from error
        self.meta["provider_timestamp"] = data.get("time_last_update_utc")
        self.meta["access"] = "key" if config.EXCHANGERATE_API_KEY else "open"
        return result
