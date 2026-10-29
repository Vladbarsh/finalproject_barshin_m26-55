"""Сценарии пользователя и упрощённая модель торговли."""

from valutatrade_hub.core.currencies import CryptoCurrency, get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, StorageError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import cached_rate, number, parse_time, utc_now
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


class TradingService:
    """Оркестрирует модели, хранение и обновление курсов."""

    def __init__(self, updater=None):
        self.db = DatabaseManager()
        self.settings = SettingsLoader()
        self.current_user = None
        self._updater = updater

    def _users(self):
        users = [User.from_dict(item) for item in self.db.read("users")]
        if len({user.user_id for user in users}) != len(users) or len(
            {user.username for user in users}
        ) != len(users):
            raise StorageError("Повторяющиеся пользователи в users.json")
        return users

    def register(self, username, password):
        """Создаёт пользователя и его пустой портфель."""
        users = self._users()
        user_id = max((user.user_id for user in users), default=0) + 1
        user = User.create(user_id, username, password)
        if any(old.username == user.username for old in users):
            raise ValueError(f"Имя пользователя '{user.username}' уже занято")
        self.db.register(user.to_dict(), Portfolio(user).to_dict())
        return user

    def login(self, username, password):
        """Выполняет вход; неверный пароль не меняет текущую сессию."""
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        user = next(
            (user for user in self._users() if user.username == username.strip()), None
        )
        if user is None:
            raise ValueError(f"Пользователь '{username.strip()}' не найден")
        if not user.verify_password(password):
            raise ValueError("Неверный пароль")
        self.current_user = user
        return user

    def _require_user(self, user_id=None):
        if self.current_user is None:
            raise ValueError("Сначала выполните login")
        if user_id is not None and user_id != self.current_user.user_id:
            raise ValueError("Нет доступа к чужому портфелю")
        return self.current_user

    def _portfolio(self, user):
        records = self.db.read("portfolios")
        if any(not isinstance(record, dict) for record in records):
            raise StorageError("Неверная структура portfolios.json")
        matches = [item for item in records if item.get("user_id") == user.user_id]
        if len(matches) != 1:
            raise StorageError("Портфель пользователя отсутствует или дублируется")
        return Portfolio.from_dict(user, matches[0]), records

    def _save_portfolio(self, portfolio, records):
        self.db.write(
            "portfolios",
            [
                portfolio.to_dict()
                if item.get("user_id") == portfolio.user.user_id
                else item
                for item in records
            ],
        )

    def update_rates(self, source=None):
        """Обновляет котировки из всех либо выбранного источника."""
        if self._updater is None:
            from valutatrade_hub.parser_service.updater import RatesUpdater

            self._updater = RatesUpdater()
        return self._updater.run_update(source)

    def get_rate(self, from_code, to_code):
        """Возвращает свежий курс, при необходимости обновляя кэш."""
        left, right = get_currency(from_code).code, get_currency(to_code).code
        ttl = self.settings.get("rates_ttl_seconds")
        pairs = self.db.read("rates")["pairs"]
        try:
            rate, updated = cached_rate(pairs, left, right, ttl)
        except (KeyError, ValueError, TypeError):
            self.update_rates()
            pairs = self.db.read("rates")["pairs"]
            try:
                rate, updated = cached_rate(pairs, left, right, ttl)
            except (KeyError, ValueError, TypeError) as error:
                raise ApiRequestError(
                    f"Курс {left}→{right} недоступен или устарел. "
                    "Выполните update-rates или повторите попытку позже."
                ) from error
        return {
            "from": left,
            "to": right,
            "rate": rate,
            "reverse": 1 / rate,
            "updated_at": updated,
        }

    def show_portfolio(self, base_currency="USD"):
        """Возвращает строки портфеля и полную оценку в выбранной базе."""
        user = self._require_user()
        base = get_currency(base_currency).code
        portfolio, _ = self._portfolio(user)
        rows = []
        total = 0.0
        for code, wallet in sorted(portfolio.wallets.items()):
            value = (
                wallet.balance * self.get_rate(code, base)["rate"]
                if wallet.balance
                else 0.0
            )
            total += value
            rows.append((code, wallet.balance, value))
        return {"username": user.username, "base": base, "rows": rows, "total": total}

    @log_action(verbose=True)
    def buy(self, user_id, currency_code, amount):
        """Зачисляет валюту и показывает оценочную стоимость в USD."""
        return self._trade(user_id, currency_code, amount, selling=False)

    @log_action(verbose=True)
    def sell(self, user_id, currency_code, amount):
        """Списывает продаваемую валюту при достаточном остатке."""
        return self._trade(user_id, currency_code, amount, selling=True)

    def _trade(self, user_id, currency_code, amount, *, selling):
        user = self._require_user(user_id)
        code, amount = get_currency(currency_code).code, number(amount)
        portfolio, records = self._portfolio(user)
        if selling:
            wallet = portfolio.get_wallet(code)
            # Остаток проверяем до сетевого запроса и без изменения хранилища.
            from valutatrade_hub.core.exceptions import InsufficientFundsError

            if amount > wallet.balance:
                raise InsufficientFundsError(wallet.balance, amount, code)
        rate = self.get_rate(code, "USD")["rate"]
        cost = number(amount * rate)
        wallet = portfolio.get_wallet(code) if selling else portfolio.add_currency(code)
        before = wallet.balance
        wallet.withdraw(amount) if selling else wallet.deposit(amount)
        self._save_portfolio(portfolio, records)
        return {
            "currency": code,
            "amount": amount,
            "rate": rate,
            "cost": cost,
            "before": before,
            "after": wallet.balance,
        }

    def show_rates(self, currency=None, top=None, base="USD"):
        """Читает кэш без сети и применяет фильтры к курсам."""
        base = get_currency(base).code
        selected = get_currency(currency).code if currency else None
        if top is not None and (type(top) is not int or top <= 0):
            raise ValueError("'top' должен быть положительным целым числом")
        cache = self.db.read("rates")
        pairs = cache["pairs"]
        if not pairs:
            raise ValueError("Локальный кеш курсов пуст. Выполните 'update-rates'.")
        codes = {key.split("_")[0] for key in pairs if key.endswith("_USD")}
        rows = []
        for code in sorted(codes):
            if selected and selected != code:
                continue
            if top is not None and not isinstance(get_currency(code), CryptoCurrency):
                continue
            try:
                rate, updated = cached_rate(pairs, code, base)
                age = (utc_now() - parse_time(updated)).total_seconds()
                stale = age >= self.settings.get("rates_ttl_seconds")
            except (ValueError, KeyError, TypeError) as error:
                raise ApiRequestError(
                    f"Не удалось пересчитать {code}→{base}"
                ) from error
            rows.append((code, base, rate, updated, stale))
        if top is not None:
            rows = sorted(rows, key=lambda item: item[2], reverse=True)[:top]
        if not rows:
            raise ValueError(f"Курс для '{selected or 'криптовалют'}' не найден в кеше")
        return rows
