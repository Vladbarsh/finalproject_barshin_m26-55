"""История измерений и последний срез котировок."""

import copy

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import StorageError
from valutatrade_hub.core.utils import iso_time, number, parse_time
from valutatrade_hub.infra.database import DatabaseManager


class RatesStorage:
    """Обновляет историю без дубликатов и кэш без старых замен."""

    def __init__(self):
        self.db = DatabaseManager()

    def save(self, measurements):
        """Проверяет все измерения до записи и возвращает число новых срезов."""
        history = self.db.read("exchange_rates")
        cache = self.db.read("rates")
        try:
            known = {item["id"] for item in history}
        except (KeyError, TypeError) as error:
            raise StorageError("Неверная история курсов") from error
        history = copy.deepcopy(history)
        pairs = copy.deepcopy(cache["pairs"])
        count = 0
        for item in measurements:
            left, right = (
                get_currency(item["from_currency"]).code,
                get_currency(item["to_currency"]).code,
            )
            value, moment = number(item["rate"]), parse_time(item["timestamp"])
            key = f"{left}_{right}"
            identity = f"{key}_{iso_time(moment)}"
            if item["id"] != identity:
                raise ValueError("ID измерения не соответствует паре и времени")
            if identity not in known:
                history.append(copy.deepcopy(item))
                known.add(identity)
            try:
                newer = key not in pairs or moment > parse_time(
                    pairs[key]["updated_at"]
                )
            except (ValueError, KeyError, TypeError) as error:
                raise StorageError("Неверная дата в кэше курсов") from error
            if newer:
                pairs[key] = {
                    "rate": value,
                    "updated_at": iso_time(moment),
                    "source": item["source"],
                }
                count += 1
        if not measurements:
            return 0
        self.db.write("exchange_rates", history)
        self.db.write(
            "rates",
            {
                "pairs": pairs,
                "last_refresh": iso_time() if count else cache.get("last_refresh"),
            },
        )
        return count
