"""Проверки значений и работа с котировками."""

import math
from datetime import UTC, datetime


def number(value, *, allow_zero=False):
    """Проверяет конечное числовое значение суммы."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
        or (value == 0 and not allow_zero)
    ):
        qualifier = "неотрицательным" if allow_zero else "положительным"
        raise ValueError(f"'amount' должен быть {qualifier} числом")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("'amount' слишком велик") from error
    if not math.isfinite(result):
        raise ValueError("'amount' должен быть конечным положительным числом")
    return result


def normalize_code(code):
    """Приводит код к верхнему регистру и проверяет формат."""
    if not isinstance(code, str):
        raise ValueError("Код валюты должен быть строкой")
    code = code.strip().upper()
    if not 2 <= len(code) <= 5 or not code.isascii() or not code.isalnum():
        raise ValueError("Код валюты: 2–5 латинских букв или цифр без пробелов")
    return code


def utc_now():
    """Возвращает текущее время UTC."""
    return datetime.now(UTC)


def iso_time(moment=None):
    """Форматирует время в ISO UTC с микросекундами."""
    return (moment or utc_now()).astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value):
    """Читает ISO-время; учебные даты без зоны считаются UTC."""
    if not isinstance(value, str):
        raise ValueError("Неверная дата обновления")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
    )


def cached_rate(pairs, from_code, to_code, ttl=None):
    """Возвращает курс и дату; при ttl отклоняет устаревшие данные."""
    if from_code == to_code:
        return 1.0, iso_time()

    def entry(key):
        item = pairs[key]
        value = number(item["rate"])
        moment = parse_time(item["updated_at"])
        age = (utc_now() - moment).total_seconds()
        if age < -60 or (ttl is not None and age >= ttl):
            raise ValueError("Курс устарел или имеет неверную дату")
        return value, moment

    if f"{from_code}_{to_code}" in pairs:
        value, moment = entry(f"{from_code}_{to_code}")
    elif f"{to_code}_{from_code}" in pairs:
        reverse, moment = entry(f"{to_code}_{from_code}")
        value = 1 / reverse
    else:
        left, left_time = (
            (1.0, utc_now()) if from_code == "USD" else entry(f"{from_code}_USD")
        )
        right, right_time = (
            (1.0, utc_now()) if to_code == "USD" else entry(f"{to_code}_USD")
        )
        value, moment = left / right, min(left_time, right_time)
    return number(value), iso_time(moment)
