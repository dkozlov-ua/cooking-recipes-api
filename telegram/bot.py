# pylint: disable=wrong-import-position

import re

import django
import requests
import telebot
from telebot.types import Message

django.setup()

from django.conf import settings
from telegram.formatters import escape, recipe_to_message
import recipes.models
import telegram.models

session = requests.Session()
bot = telebot.TeleBot(
    token=settings.TELEGRAM_BOT_TOKEN,
    parse_mode='MarkdownV2',
    threaded=True,
)


def update_chat(message: Message) -> telegram.models.Chat:
    chat = telegram.models.Chat(
        id=message.chat.id,
        username=message.chat.username,
        first_name=message.chat.first_name,
        last_name=message.chat.last_name,
    )
    chat.save()
    return chat


@bot.message_handler(commands=['start'])
def cmd_start(message: Message) -> None:
    update_chat(message)
    bot.reply_to(message, escape('You have been registered'))


@bot.message_handler(commands=['subscribe'])
def cmd_subscribe(message: Message) -> None:
    chat = update_chat(message)
    value_match = re.search(r"^/subscribe\s*(.*)", message.text)
    if not value_match:
        return

    value = value_match.group(1).strip()
    if value.startswith('#'):
        tag_id = recipes.models.Tag.id_from_name(value)
        tag, _ = recipes.models.Tag.objects.get_or_create(pk=tag_id)
        telegram.models.Subscription.objects.get_or_create(chat=chat, tag=tag, author=None)
        msg = f"Subscribed to #{tag.name or value}"
    else:
        author_id = recipes.models.Author.id_from_name(value)
        author, _ = recipes.models.Author.objects.get_or_create(pk=author_id)
        telegram.models.Subscription.objects.get_or_create(chat=chat, tag=None, author=author)
        msg = f"Subscribed to {author.name or value}"
    bot.reply_to(message, escape(msg))


@bot.message_handler(commands=['unsubscribe'])
def cmd_unsubscribe(message: Message) -> None:
    chat = update_chat(message)
    value_match = re.search(r"^/unsubscribe\s*(.*)", message.text)
    if not value_match:
        return

    value = value_match.group(1).strip()
    if value.startswith('#'):
        tag_id = recipes.models.Tag.id_from_name(value)
        tag, _ = recipes.models.Tag.objects.get_or_create(pk=tag_id)
        telegram.models.Subscription.objects.filter(chat=chat, tag=tag, author=None).delete()
        msg = f"Unsubscribed from #{tag.name or value}"
    else:
        author_id = recipes.models.Author.id_from_name(value)
        author, _ = recipes.models.Author.objects.get_or_create(pk=author_id)
        telegram.models.Subscription.objects.filter(chat=chat, tag=None, author=author).delete()
        msg = f"Unsubscribed from {author.name or value}"
    bot.reply_to(message, escape(msg))


@bot.message_handler(commands=['random'])
def cmd_random(message: Message) -> None:
    chat = update_chat(message)
    recipe = recipes.models.Recipe.objects.all().order_by('?')[0]
    bot.send_message(
        chat_id=chat.id,
        text=recipe_to_message(recipe),
    )
