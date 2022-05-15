import telebot
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from backend.celery import log_exception
from recipes.models import Recipe
from telegram.formatters import recipe_to_message
from telegram.models import Subscription

bot = telebot.TeleBot(
    token=settings.TELEGRAM_BOT_TOKEN,
    parse_mode='MarkdownV2',
    threaded=False,
)
logger = get_task_logger(__name__)


@shared_task
@log_exception(logger)
def send_recipes_for_subscription(subscription: Subscription) -> None:
    logger.debug(f"Processing subscription: {subscription}")
    if subscription.tag:
        recipes = subscription.tag.recipes.all()
    elif subscription.author:
        recipes = subscription.author.recipes.all()
    else:
        recipes = Recipe.objects.all()
    recipes = (recipes
               .filter(pub_date__gt=subscription.last_recipe_pub_date)
               .prefetch_related('tags', 'authors')
               .order_by('pub_date'))

    for recipe in recipes:
        logger.debug(f"Sending recipe '{recipe}' to {subscription.chat.id}")
        if recipe.pub_date:
            bot.send_message(
                chat_id=subscription.chat.id,
                text=recipe_to_message(recipe),
            )
            subscription.last_recipe_pub_date = recipe.pub_date
            subscription.save()


@shared_task
@log_exception(logger)
def fulfill_subscriptions() -> None:
    subscriptions = Subscription.objects.filter(tag__isnull=False)
    for subscription in subscriptions:
        send_recipes_for_subscription.delay(subscription)
