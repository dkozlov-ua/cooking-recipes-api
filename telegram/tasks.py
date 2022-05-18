from typing import Union

import telebot
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

import telegram.models
from telegram.formatters import recipe_to_message

bot = telebot.TeleBot(
    token=settings.TELEGRAM_BOT_TOKEN,
    parse_mode='MarkdownV2',
    threaded=False,
)
logger = get_task_logger(__name__)

AnySubscription = Union[telegram.models.TagSubscription, telegram.models.AuthorSubscription]


@shared_task
def send_recipes_for_subscription(subscription: AnySubscription) -> None:
    logger.debug(f"Processing subscription: {subscription}")
    if isinstance(subscription, telegram.models.TagSubscription):
        recipes_list = subscription.tag.recipes.all()
    elif isinstance(subscription, telegram.models.AuthorSubscription):
        recipes_list = subscription.author.recipes.all()
    else:
        raise ValueError(f"Unknown subscription type: {subscription}")

    recipes_list = (recipes_list
                    .filter(pub_date__gt=subscription.last_recipe_date)
                    .prefetch_related('tags', 'authors')
                    .order_by('pub_date'))
    for recipe in recipes_list:
        logger.debug(f"Sending recipe '{recipe}' to {subscription.chat.id}")
        if recipe.pub_date:
            bot.send_message(
                chat_id=subscription.chat.id,
                text=recipe_to_message(recipe),
            )
            subscription.last_recipe_date = recipe.pub_date
            subscription.save()


@shared_task
def fulfill_subscriptions() -> None:
    for tag_subscription in telegram.models.TagSubscription.objects.all():
        send_recipes_for_subscription.delay(tag_subscription)
    for author_subscription in telegram.models.AuthorSubscription.objects.all():
        send_recipes_for_subscription.delay(author_subscription)
