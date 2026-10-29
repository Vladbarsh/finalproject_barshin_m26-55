"""Ошибки предметной области и хранения данных."""


class InsufficientFundsError(ValueError):
    """На кошельке не хватает валюты для продажи."""

    def __init__(self, available, required, code):
        super().__init__(
            f"Недостаточно средств: доступно {available:g} {code}, "
            f"требуется {required:g} {code}"
        )


class CurrencyNotFoundError(ValueError):
    """Код отсутствует в реестре валют."""

    def __init__(self, code):
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(Exception):
    """Не удалось получить пригодный курс."""

    def __init__(self, reason):
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class StorageError(Exception):
    """Файл данных недоступен или имеет неверный формат."""
