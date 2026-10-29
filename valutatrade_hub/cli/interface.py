"""Разбор команд, вывод таблиц и обработка ожидаемых ошибок."""

import argparse
import shlex
import sys

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import CURRENCIES
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    StorageError,
)
from valutatrade_hub.core.usecases import TradingService
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import setup_logging

COMMANDS = {
    "register": "зарегистрироваться",
    "login": "войти в систему",
    "show-portfolio": "показать кошельки и общую стоимость",
    "buy": "купить валюту в единицах выбранной валюты",
    "sell": "продать валюту",
    "get-rate": "получить свежий курс",
    "update-rates": "обновить курсы через API",
    "show-rates": "показать локальный кэш",
}


class CommandParser(argparse.ArgumentParser):
    """Парсер, возвращающий ошибку в цикл вместо SystemExit."""

    def error(self, message):
        raise ValueError(message)


def command_parser(command):
    """Создаёт схему аргументов выбранной команды."""
    parser = CommandParser(
        prog=command, description=COMMANDS[command], add_help=False, allow_abbrev=False
    )
    if command in ("register", "login"):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
    elif command in ("buy", "sell"):
        parser.add_argument("--currency", required=True)
        parser.add_argument("--amount", required=True, type=float)
    elif command == "show-portfolio":
        parser.add_argument("--base", default=SettingsLoader().get("base_currency"))
    elif command == "get-rate":
        parser.add_argument("--from", dest="from_code", required=True)
        parser.add_argument("--to", dest="to_code", required=True)
    elif command == "update-rates":
        parser.add_argument("--source", choices=("coingecko", "exchangerate"))
    elif command == "show-rates":
        parser.add_argument("--currency")
        parser.add_argument("--top", type=int)
        parser.add_argument("--base", default=SettingsLoader().get("base_currency"))
    return parser


def show_help():
    """Показывает доступные команды и валюты."""
    print("ValutaTrade Hub — виртуальный валютный портфель")
    for name, description in COMMANDS.items():
        print(f"  {name:<16} {description}")
    print("  help <команда>   аргументы команды\n  exit             выход")
    print("Валюты: " + ", ".join(CURRENCIES))
    print(
        "Модель: buy/sell меняют баланс валюты, USD показывает её оценочную стоимость."
    )


class Interface:
    """Связывает пользовательские команды со сценариями Core."""

    def __init__(self, service=None):
        self.service = service or TradingService()

    def execute(self, tokens):
        """Выполняет одну команду; False означает выход из сессии."""
        if not tokens:
            return True
        command, *arguments = tokens
        if command == "exit":
            if arguments:
                raise ValueError("У exit нет аргументов")
            return False
        if command in ("help", "--help", "-h"):
            if len(arguments) == 1 and arguments[0] in COMMANDS:
                print(command_parser(arguments[0]).format_help())
            elif not arguments:
                show_help()
            else:
                raise ValueError("Используйте help или help <команда>")
            return True
        if command not in COMMANDS:
            raise ValueError(f"Неизвестная команда '{command}'. Введите help.")
        parser = command_parser(command)
        if "--help" in arguments or "-h" in arguments:
            print(parser.format_help())
            return True
        args = parser.parse_args(arguments)
        self._dispatch(command, args)
        return True

    def _dispatch(self, command, args):
        service = self.service
        if command == "register":
            user = service.register(args.username, args.password)
            print(
                f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
                f"Войдите: login --username {shlex.quote(user.username)} "
                "--password ****"
            )
        elif command == "login":
            user = service.login(args.username, args.password)
            print(f"Вы вошли как '{user.username}'")
        elif command == "show-portfolio":
            result = service.show_portfolio(args.base)
            if not result["rows"]:
                print(f"Портфель пользователя '{result['username']}' пуст.")
                return
            print(
                f"Портфель пользователя '{result['username']}' "
                f"(база: {result['base']}):"
            )
            table = PrettyTable(["Валюта", "Баланс", f"Стоимость в {result['base']}"])
            for code, balance, value in result["rows"]:
                table.add_row([code, f"{balance:.8f}", f"{value:,.2f}"])
            print(table)
            print(f"ИТОГО: {result['total']:,.2f} {result['base']}")
        elif command in ("buy", "sell"):
            user_id = service.current_user.user_id if service.current_user else None
            operation = service.buy if command == "buy" else service.sell
            result = operation(user_id, args.currency, args.amount)
            label = "Покупка" if command == "buy" else "Продажа"
            print(
                f"{label} выполнена: {result['amount']:.4f} {result['currency']} "
                f"по курсу {result['rate']:.8g} USD/{result['currency']}"
            )
            print(
                f"Изменения в портфеле:\n- {result['currency']}: "
                f"было {result['before']:.4f} → стало {result['after']:.4f}"
            )
            label = "стоимость покупки" if command == "buy" else "выручка"
            print(f"Оценочная {label}: {result['cost']:,.2f} USD")
        elif command == "get-rate":
            result = service.get_rate(args.from_code, args.to_code)
            print(
                f"Курс {result['from']}→{result['to']}: {result['rate']:.10g} "
                f"(обновлено: {result['updated_at']})"
            )
            print(
                f"Обратный курс {result['to']}→{result['from']}: "
                f"{result['reverse']:.10g}"
            )
        elif command == "update-rates":
            result = service.update_rates(args.source)
            print(
                f"Обновлено курсов: {result['count']}. "
                f"Источники: {', '.join(result['sources'])}."
            )
            print(f"Время обновления: {result['last_refresh']}")
            for error in result["errors"]:
                print(f"Предупреждение: {error}")
            print("Rates By Exchange Rate API — https://www.exchangerate-api.com")
        elif command == "show-rates":
            rows = service.show_rates(args.currency, args.top, args.base)
            print("Курсы из локального кеша:")
            table = PrettyTable(["Пара", "Курс", "Обновлено (UTC)", "Состояние"])
            for left, right, rate, updated, stale in rows:
                table.add_row(
                    [
                        f"{left}_{right}",
                        f"{rate:.10g}",
                        updated,
                        "устарел" if stale else "свежий",
                    ]
                )
            print(table)
            print("Rates By Exchange Rate API — https://www.exchangerate-api.com")


def report_error(error):
    """Показывает ожидаемую ошибку без стека вызовов."""
    print(f"Ошибка: {error}")
    if isinstance(error, CurrencyNotFoundError):
        print("Поддерживаются: " + ", ".join(CURRENCIES) + ". Справка: help get-rate")
    elif isinstance(error, ApiRequestError):
        print("Проверьте сеть и настройки API; повторите попытку позже.")


def main(argv=None):
    """Запускает CLI в одной сессии или выполняет переданную команду."""
    if sys.platform == "win32":
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    try:
        setup_logging()
        interface = Interface()
    except (StorageError, OSError) as error:
        report_error(error)
        return 1
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        try:
            interface.execute(arguments)
        except (ValueError, ApiRequestError, StorageError) as error:
            report_error(error)
            return 1
        return 0
    show_help()
    while True:
        try:
            line = input("VT> ")
            if not interface.execute(shlex.split(line)):
                break
        except (EOFError, KeyboardInterrupt):
            print()
            break
        except (ValueError, ApiRequestError, StorageError) as error:
            report_error(error)
    print("До свидания!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
