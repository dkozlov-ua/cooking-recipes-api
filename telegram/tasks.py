from collections import Counter

import telebot
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet

from recipes.models import Recipe
from telegram.message import format_recipe_msg
from telegram.models import Chat

bot = telebot.TeleBot(
    token=settings.TELEGRAM_BOT_TOKEN,
    parse_mode='MarkdownV2',
    threaded=False,
)
logger = get_task_logger(__name__)


@shared_task
def fulfill_subscriptions() -> None:
    sent_messages_counter: Counter = Counter()
    for chat in Chat.objects.all():
        # Combine recipes for all subscriptions of the chat into a deduplicated queryset
        recipes_to_send: QuerySet[Recipe] = Recipe.objects.none()
        for tag_subscription in chat.tag_subscriptions.all().select_related('tag'):
            new_recipes = tag_subscription.tag.recipes \
                .filter(pub_date__gt=tag_subscription.last_recipe_date) \
                .prefetch_related('tags', 'authors')
            recipes_to_send = recipes_to_send.union(new_recipes)
        for author_subscription in chat.author_subscriptions.all().select_related('author'):
            new_recipes = author_subscription.author.recipes \
                .filter(pub_date__gt=author_subscription.last_recipe_date) \
                .prefetch_related('tags', 'authors')
            recipes_to_send = recipes_to_send.union(new_recipes)
        recipes_to_send = recipes_to_send.order_by('pub_date')

        # Send recipes to the chat
        for recipe in recipes_to_send:
            sent_messages_counter[chat.id] += 1
            msg_text, msg_markup = format_recipe_msg(recipe)
            bot.send_message(
                chat_id=chat.id,
                text=msg_text,
                reply_markup=msg_markup,
            )
            if recipe.pub_date:
                # Update all subscriptions to ensure each recipe is sent at most once
                # (still possible if the update has failed)
                with transaction.atomic():
                    chat.tag_subscriptions.update(last_recipe_date=recipe.pub_date)
                    chat.author_subscriptions.update(last_recipe_date=recipe.pub_date)
        if sent_messages_counter[chat.id]:
            logger.debug(f"Chat {chat}: sent {sent_messages_counter[chat.id]} recipes")
    logger.info(f"Sent {sent_messages_counter.total()} recipes to {len(sent_messages_counter)} chats")
