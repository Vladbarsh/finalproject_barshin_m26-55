"""Декоратор логирования торговых операций."""

import inspect
import logging
from functools import wraps


def log_action(*, verbose=False):
    """Записывает результат операции и пробрасывает её исключения."""

    def decorate(function):
        signature = inspect.signature(function)

        @wraps(function)
        def wrapper(*args, **kwargs):
            values = signature.bind(*args, **kwargs).arguments
            context = (
                f"action={function.__name__.upper()} "
                f"user_id={values.get('user_id')!r} "
                f"currency={values.get('currency_code')!r} "
                f"amount={values.get('amount')!r}"
            )
            logger = logging.getLogger("valutatrade.actions")
            try:
                result = function(*args, **kwargs)
            except Exception as error:
                logger.info(
                    "%s result=ERROR error_type=%s error_message=%r",
                    context,
                    type(error).__name__,
                    str(error),
                )
                raise
            details = f"rate={result['rate']!r} base='USD'"
            if verbose:
                details += f" before={result['before']!r} after={result['after']!r}"
            logger.info("%s %s result=OK", context, details)
            return result

        return wrapper

    return decorate
