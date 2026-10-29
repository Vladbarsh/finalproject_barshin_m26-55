"""Пользователь и валютные кошельки."""

import hashlib
import hmac
import secrets
from datetime import datetime
from decimal import Decimal

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import InsufficientFundsError, StorageError
from valutatrade_hub.core.utils import cached_rate, iso_time, number, parse_time


class User:
    """Пользователь с солью и хешем пароля."""

    def __init__(self, user_id, username, hashed_password, salt, registration_date):
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("Неверный ID пользователя")
        self._user_id = user_id
        self.username = username
        if not isinstance(hashed_password, str) or len(hashed_password) != 64:
            raise ValueError("Неверный хеш пароля")
        if not isinstance(salt, str) or not salt:
            raise ValueError("Пустая соль пароля")
        self._hashed_password = hashed_password
        self._salt = salt
        date = (
            registration_date.isoformat()
            if isinstance(registration_date, datetime)
            else registration_date
        )
        self._registration_date = parse_time(date)

    @classmethod
    def create(cls, user_id, username, password):
        """Создаёт пользователя с новой случайной солью."""
        cls._validate_password(password)
        salt = secrets.token_hex(16)
        return cls(user_id, username, cls._hash(password, salt), salt, iso_time())

    @staticmethod
    def _hash(password, salt):
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_password(password):
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

    @property
    def user_id(self):
        """Постоянный идентификатор пользователя."""
        return self._user_id

    @property
    def username(self):
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self):
        """Сохранённый хеш без возможности внешней замены."""
        return self._hashed_password

    @property
    def salt(self):
        """Соль сохранённого хеша."""
        return self._salt

    @property
    def registration_date(self):
        """Дата регистрации UTC."""
        return self._registration_date

    def get_user_info(self):
        """Возвращает сведения без пароля, соли и хеша."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": iso_time(self.registration_date),
        }

    def change_password(self, new_password):
        """Меняет пароль и соль после проверки длины."""
        self._validate_password(new_password)
        salt = secrets.token_hex(16)
        self._hashed_password = self._hash(new_password, salt)
        self._salt = salt

    def verify_password(self, password):
        """Проверяет пароль по сохранённой соли."""
        return isinstance(password, str) and hmac.compare_digest(
            self._hash(password, self._salt), self._hashed_password
        )

    def to_dict(self):
        """Готовит пользователя для JSON-хранилища."""
        return {
            **self.get_user_info(),
            "hashed_password": self._hashed_password,
            "salt": self._salt,
        }

    @classmethod
    def from_dict(cls, record):
        """Восстанавливает пользователя без повторного хеширования."""
        try:
            return cls(**record)
        except (TypeError, ValueError, KeyError) as error:
            raise StorageError("Неверная запись пользователя") from error


class Wallet:
    """Баланс пользователя в одной валюте."""

    def __init__(self, currency_code, balance=0.0):
        self.currency_code = get_currency(currency_code).code
        self.balance = balance

    @property
    def balance(self):
        """Текущий неотрицательный баланс."""
        return self._balance

    @balance.setter
    def balance(self, value):
        self._balance = number(value, allow_zero=True)

    def deposit(self, amount):
        """Пополняет кошелёк положительной суммой."""
        self.balance = float(Decimal(str(self.balance)) + Decimal(str(number(amount))))

    def withdraw(self, amount):
        """Списывает сумму, если остаток достаточен."""
        amount = number(amount)
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount, self.currency_code)
        self.balance = float(Decimal(str(self.balance)) - Decimal(str(amount)))

    def get_balance_info(self):
        """Возвращает строку с кодом и балансом."""
        return f"{self.currency_code}: {self.balance:.4f}"


class Portfolio:
    """Все кошельки одного пользователя."""

    def __init__(self, user, wallets=None):
        self._user = user
        self._user_id = user.user_id
        self._wallets = {}
        for code, wallet in (wallets or {}).items():
            if not isinstance(wallet, Wallet) or code != wallet.currency_code:
                raise ValueError("Неверный кошелёк в портфеле")
            self._wallets[code] = wallet

    @property
    def user(self):
        """Пользователь, которому принадлежит портфель."""
        return self._user

    @property
    def wallets(self):
        """Копия словаря кошельков."""
        return self._wallets.copy()

    def add_currency(self, currency_code):
        """Создаёт кошелёк, не меняя существующий баланс."""
        code = get_currency(currency_code).code
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code):
        """Находит кошелёк или сообщает об его отсутствии."""
        code = get_currency(currency_code).code
        if code not in self._wallets:
            raise ValueError(
                f"У вас нет кошелька '{code}'. "
                "Он создаётся автоматически при первой покупке."
            )
        return self._wallets[code]

    def get_total_value(self, base_currency="USD", exchange_rates=None):
        """Считает стоимость по переданным курсам или локальному кэшу."""
        base = get_currency(base_currency).code
        if exchange_rates is None:
            from valutatrade_hub.infra.database import DatabaseManager
            from valutatrade_hub.infra.settings import SettingsLoader

            pairs = DatabaseManager().read("rates")["pairs"]
            ttl = SettingsLoader().get("rates_ttl_seconds")
        else:
            pairs = {
                key: {"rate": value, "updated_at": iso_time()}
                for key, value in exchange_rates.items()
            }
            ttl = None
        return number(
            sum(
                wallet.balance * cached_rate(pairs, code, base, ttl)[0]
                for code, wallet in self._wallets.items()
                if wallet.balance
            ),
            allow_zero=True,
        )

    def to_dict(self):
        """Возвращает портфель для сохранения в JSON."""
        return {
            "user_id": self._user_id,
            "wallets": {
                code: {"balance": wallet.balance}
                for code, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, user, record):
        """Восстанавливает проверенные объекты кошельков."""
        try:
            if record["user_id"] != user.user_id:
                raise ValueError("Чужой портфель")
            wallets = {
                code: Wallet(code, item["balance"])
                for code, item in record["wallets"].items()
            }
            return cls(user, wallets)
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise StorageError("Неверная запись портфеля") from error
