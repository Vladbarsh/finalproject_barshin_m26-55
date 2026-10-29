"""Настройки из pyproject.toml и переменных окружения."""

import os
import tomllib
from pathlib import Path

from valutatrade_hub.core.exceptions import StorageError

DEFAULTS = {
    "rates_ttl_seconds": 300,
    "base_currency": "USD",
    "log_max_bytes": 1_048_576,
    "log_backup_count": 3,
    "log_format": "%(levelname)s %(asctime)sZ %(message)s",
    "log_level": "INFO",
    "request_timeout": 10,
    "update_interval": 300,
}


class SettingsLoader:
    """Один набор настроек на процесс; __new__ проще метакласса."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_values"):
            self.reload()

    def reload(self):
        """Перечитывает настройки без создания нового экземпляра."""
        values = dict(DEFAULTS)
        config = Path(os.getenv("VALUTATRADE_CONFIG", "pyproject.toml"))
        try:
            if config.exists():
                with config.open("rb") as stream:
                    values.update(
                        tomllib.load(stream).get("tool", {}).get("valutatrade", {})
                    )
            elif "VALUTATRADE_CONFIG" in os.environ:
                raise StorageError("Не найден файл VALUTATRADE_CONFIG")
        except (OSError, ValueError, TypeError, AttributeError) as error:
            raise StorageError("Не удалось прочитать настройки") from error
        values["data_dir"] = Path(
            os.getenv("VALUTATRADE_DATA_DIR", values.get("data_dir", "data"))
        ).resolve()
        values["log_dir"] = Path(
            os.getenv("VALUTATRADE_LOG_DIR", values.get("log_dir", "logs"))
        ).resolve()
        if "VALUTATRADE_RATES_TTL" in os.environ:
            try:
                values["rates_ttl_seconds"] = int(os.environ["VALUTATRADE_RATES_TTL"])
            except ValueError as error:
                raise StorageError(
                    "VALUTATRADE_RATES_TTL должен быть целым числом"
                ) from error
        for key in (
            "rates_ttl_seconds",
            "log_max_bytes",
            "log_backup_count",
            "request_timeout",
            "update_interval",
        ):
            if type(values[key]) is not int or values[key] <= 0:
                raise StorageError(
                    f"Настройка {key} должна быть положительным целым числом"
                )
        for key in ("base_currency", "log_format", "log_level"):
            if not isinstance(values[key], str) or not values[key].strip():
                raise StorageError(f"Настройка {key} должна быть непустой строкой")
        values["log_level"] = values["log_level"].upper()
        if values["log_level"] not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise StorageError("Неизвестный уровень логирования")
        self._values = values

    def get(self, key, default=None):
        """Возвращает значение настройки или default."""
        return self._values.get(key, default)
