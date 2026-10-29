"""Безопасное чтение и атомарная запись JSON."""

import copy
import json
import os
import tempfile
from pathlib import Path

from valutatrade_hub.core.exceptions import StorageError
from valutatrade_hub.infra.settings import SettingsLoader

EMPTY_DATA = {
    "users": [],
    "portfolios": [],
    "rates": {"pairs": {}, "last_refresh": None},
    "exchange_rates": [],
}


def atomic_write(path, data):
    """Заменяет JSON целиком через временный файл в том же каталоге."""
    path = Path(path)
    temporary = None
    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except (OSError, ValueError, TypeError) as error:
        raise StorageError(f"Не удалось сохранить {path.name}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class DatabaseManager:
    """Единственный менеджер хранилища; __new__ сохраняет общий экземпляр."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def path(self, name):
        """Возвращает путь известного файла данных."""
        if name not in EMPTY_DATA:
            raise ValueError("Неизвестное хранилище")
        return SettingsLoader().get("data_dir") / f"{name}.json"

    def read(self, name):
        """Читает данные, сохраняя повреждённый файл без изменений."""
        path = self.path(name)
        try:
            with path.open(encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError:
            return copy.deepcopy(EMPTY_DATA[name])
        except (OSError, ValueError, UnicodeError) as error:
            raise StorageError(
                f"Не удалось прочитать {path.name}; файл не изменён"
            ) from error
        if type(data) is not type(EMPTY_DATA[name]):
            raise StorageError(f"Неверная структура {path.name}")
        if name == "rates" and not isinstance(data.get("pairs"), dict):
            raise StorageError("В rates.json требуется объект pairs")
        return data

    def write(self, name, data):
        """Сохраняет полный документ."""
        atomic_write(self.path(name), data)

    def register(self, user, portfolio):
        """Сохраняет пользователя и портфель с откатом при второй ошибке."""
        users = self.read("users")
        portfolios = self.read("portfolios")
        self.write("portfolios", [*portfolios, portfolio])
        try:
            self.write("users", [*users, user])
        except StorageError:
            self.write("portfolios", portfolios)
            raise
