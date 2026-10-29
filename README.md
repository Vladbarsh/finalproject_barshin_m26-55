# ValutaTrade Hub

Итоговый проект по Python. Баршин Владислав, М26-55.

Консольный валютный кошелёк: регистрация, вход, покупки и продажи,
просмотр портфеля и курсов. Поддерживаются USD, EUR, GBP, RUB, BTC, ETH и SOL.

## Запуск

Нужны Python 3.12 или новее и uv.

```console
git clone https://github.com/Vladbarsh/finalproject_barshin_m26-55.git
cd finalproject_barshin_m26-55
uv sync --locked
uv run project
```

## Команды

```text
register --username alice --password 1234
login --username alice --password 1234
update-rates
show-rates --top 2
buy --currency BTC --amount 0.05
sell --currency BTC --amount 0.01
show-portfolio
get-rate --from USD --to BTC
```

`help` показывает справку, `help buy` — аргументы команды, `exit` завершает работу.
Суммы задаются в единицах валюты. Покупка увеличивает её баланс, продажа уменьшает.
Стоимость в USD показывается для оценки, отдельного расчёта через USD-кошелёк нет.

## Как устроено

Пакет `valutatrade_hub` разделён на `core` (модели и операции), `infra` (хранение),
`parser_service` (курсы) и `cli` (интерфейс).
Данные сохраняются в JSON в папке `data/`, журналы работы — в `logs/`.
Настройки лежат в секции `[tool.valutatrade]` файла `pyproject.toml`.

Курсы берутся из CoinGecko и ExchangeRate-API. Открытый режим работает без ключей.
Персональный ключ можно передать через `EXCHANGERATE_API_KEY`, Demo-ключ CoinGecko —
через `COINGECKO_API_KEY` в окружении перед запуском.
Кэш хранит последние курсы и время получения, TTL по умолчанию — 300 секунд.
Устаревший курс обновляется по запросу; при сбое выводится ошибка.
Фиатные данные у бесплатного источника обновляются раз в сутки.
`update-rates` обновляет курсы вручную, `uv run rates-scheduler` — периодически,
до нажатия Ctrl+C. Обратные и кросс-курсы считаются через USD.

## Проверка

```console
uv run ruff check .
uv run ruff format --check .
uv build
uvx twine check dist/*
```

## Демонстрация

https://asciinema.org/a/Q9HOk0bAduMLYqde

Курсы фиатных валют — Rates By Exchange Rate API: https://www.exchangerate-api.com
