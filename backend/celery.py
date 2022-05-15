from functools import wraps
from logging import Logger
from typing import Callable, Any

from celery import Celery

app = Celery('backend')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


def log_exception(logger: Logger) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapped(*args, **kwargs) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                logger.exception(f"{type(exc).__name__}: {str(exc)}")
                raise
        return wrapped

    return decorator
