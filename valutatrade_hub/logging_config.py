"""Файловые логи приложения с ротацией."""

import logging
import time
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader


def setup_logging():
    """Настраивает независимые журналы операций и получения курсов."""
    settings = SettingsLoader()
    directory = settings.get("log_dir")
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(levelname)s %(asctime)sZ %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )
    formatter.converter = time.gmtime
    for name, filename in (("actions", "actions.log"), ("parser", "parser.log")):
        logger = logging.getLogger(f"valutatrade.{name}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        target = str((directory / filename).resolve())
        if any(
            getattr(handler, "baseFilename", None) == target
            for handler in logger.handlers
        ):
            continue
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
        handler = RotatingFileHandler(
            target,
            maxBytes=settings.get("log_max_bytes"),
            backupCount=settings.get("log_backup_count"),
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
