"""Явный запуск периодического обновления курсов."""

import time

from valutatrade_hub.core.exceptions import ApiRequestError, StorageError
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.updater import RatesUpdater


def main():
    """Обновляет курсы с интервалом из настроек до Ctrl+C."""
    try:
        setup_logging()
        interval = SettingsLoader().get("update_interval")
        updater = RatesUpdater()
        print(f"Обновление каждые {interval} с. Остановка: Ctrl+C.")
        while True:
            try:
                result = updater.run_update()
                print(
                    f"Обновлено курсов: {result['count']}; "
                    f"ошибок: {len(result['errors'])}"
                )
            except (ApiRequestError, StorageError) as error:
                print(error)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nПланировщик остановлен.")


if __name__ == "__main__":
    main()
