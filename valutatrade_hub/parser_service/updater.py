"""Координация независимых источников котировок."""

import logging

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import iso_time, number
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import RatesStorage


class RatesUpdater:
    """Получает данные от доступных источников и сохраняет корректные пары."""

    def __init__(self, clients=None, storage=None):
        self.clients = (
            [CoinGeckoClient(), ExchangeRateApiClient()] if clients is None else clients
        )
        self.storage = storage or RatesStorage()

    def run_update(self, source=None):
        """Обновляет все либо один источник, переживая частичный отказ."""
        supported = {client.source_key for client in self.clients}
        if source is not None and source not in supported:
            raise ValueError("Источник: coingecko или exchangerate")
        logger = logging.getLogger("valutatrade.parser")
        logger.info("Starting rates update source=%s", source or "all")
        measurements, errors, successful = [], [], []
        for client in self.clients:
            if source is not None and client.source_key != source:
                continue
            try:
                rates = client.fetch_rates()
                if not rates:
                    raise ApiRequestError(f"{client.source}: пустой ответ")
                stamp = iso_time()
                batch = []
                for pair, value in rates.items():
                    left, right = pair.split("_")
                    batch.append(
                        {
                            "id": f"{pair}_{stamp}",
                            "from_currency": left,
                            "to_currency": right,
                            "rate": number(value),
                            "timestamp": stamp,
                            "source": client.source,
                            "meta": dict(getattr(client, "meta", {})),
                        }
                    )
                measurements.extend(batch)
                successful.append(client.source)
                logger.info(
                    "Fetching from %s: OK (%s rates)", client.source, len(batch)
                )
            except ApiRequestError as error:
                errors.append(str(error))
                logger.warning("Fetching from %s: %s", client.source, error)
            except (ValueError, TypeError, KeyError) as error:
                message = f"{client.source}: неверные данные ({type(error).__name__})"
                errors.append(message)
                logger.warning("%s", message)
        if not measurements:
            raise ApiRequestError("; ".join(errors) or "Нет доступных источников")
        count = self.storage.save(measurements)
        logger.info("Writing rates: %s updated, %s errors", count, len(errors))
        return {
            "count": count,
            "errors": errors,
            "sources": successful,
            "last_refresh": iso_time(),
        }
