import datetime
from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger

from recipes import models
from recipes import scrapers

logger = get_task_logger(__name__)


@shared_task
def update_recipes_bonappetit(from_date: Optional[datetime.datetime] = None, from_page: int = 1) -> None:
    """Updates saves new and/or updates old recipes in the database.

    Recipes always fetched from newer to older.
    If `from_date` is None, it is set to the latest recipe's `pub_date` ("download new recipes" mode).
    If `from_date` is not None, updates all recipes starting from page number `from_page` until `from_date` is reached.

    :param from_date: a datetime indicating when to stop scraping.
    :param from_page: a number of a page to start from.
    """

    if not from_date:
        try:
            from_date = models.Recipe.objects.latest().pub_date
        except models.Recipe.DoesNotExist:
            from_date = None
    saved_count, _ = scrapers.bonappetit(from_date, from_page)
    logger.debug(f"Fetched {saved_count} bonappetit recipes")
