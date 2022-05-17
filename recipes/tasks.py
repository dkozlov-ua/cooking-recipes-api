import datetime
from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger

from backend.celery import log_exception
from recipes import models
from recipes import scrapers

logger = get_task_logger(__name__)


@shared_task
@log_exception(logger)
def update_recipes_bonappetit(from_date: Optional[datetime.datetime] = None, from_page: int = 1) -> None:
    if not from_date:
        try:
            from_date = models.Recipe.objects.latest().pub_date
        except models.Recipe.DoesNotExist:
            from_date = None
    saved_count, _ = scrapers.bonappetit(from_date, from_page)
    logger.debug(f"Fetched {saved_count} bonappetit recipes")
