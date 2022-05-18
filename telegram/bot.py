# pylint: disable=wrong-import-position
import datetime
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


_subscribe_tag_regex = re.compile(r"^/subscribe\s+.*tag\s+#?(\w+)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_subscribe_tag_regex.pattern)
def cmd_subscribe_tag(message: Message) -> None:
    chat = update_chat(message)
    value_match = _subscribe_tag_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_subscribe_tag_regex} in text '{message.text}'")
    value = value_match.group(1)
    tag_id = recipes.models.Tag.id_from_name(value)
    try:
        tag = recipes.models.Tag.objects.get(pk=tag_id)
    except recipes.models.Tag.DoesNotExist:
        bot.reply_to(message, escape(f"Tag #{value} does not exist"))
    else:
        telegram.models.TagSubscription.objects.get_or_create(
            chat=chat,
            tag=tag,
            defaults={'last_recipe_date': datetime.datetime.utcnow()},
        )
        bot.reply_to(message, escape(f"Subscribed to tag #{tag.name}"))


_unsubscribe_tag_regex = re.compile(r"^/unsubscribe\s+.*tag\s+#?(\w+)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_unsubscribe_tag_regex.pattern)
def cmd_unsubscribe_tag(message: Message) -> None:
    chat = update_chat(message)
    value_match = _unsubscribe_tag_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_unsubscribe_tag_regex} in text '{message.text}'")
    value = value_match.group(1)
    tag_id = recipes.models.Tag.id_from_name(value)
    try:
        tag = recipes.models.Tag.objects.get(pk=tag_id)
    except recipes.models.Tag.DoesNotExist:
        bot.reply_to(message, escape(f"Tag #{value} does not exist"))
    else:
        telegram.models.TagSubscription.objects.filter(chat=chat, tag=tag).delete()
        bot.reply_to(message, escape(f"Unsubscribed from tag #{tag.name}"))


_subscribe_author_regex = re.compile(r"^/subscribe\s+.*author\s+(.*)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_subscribe_author_regex.pattern)
def cmd_subscribe_author(message: Message) -> None:
    chat = update_chat(message)
    value_match = _subscribe_author_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_subscribe_author_regex} in text '{message.text}'")
    value = value_match.group(1)
    author_id = recipes.models.Author.id_from_name(value)
    try:
        author = recipes.models.Author.objects.get(pk=author_id)
    except recipes.models.Author.DoesNotExist:
        bot.reply_to(message, escape(f"Author '{value}' does not exist"))
    else:
        telegram.models.AuthorSubscription.objects.get_or_create(
            chat=chat,
            author=author,
            defaults={'last_recipe_date': datetime.datetime.utcnow()},
        )
        bot.reply_to(message, escape(f"Subscribed to {author.name}"))


_unsubscribe_author_regex = re.compile(r"^/unsubscribe\s+.*author\s+(.*)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_unsubscribe_author_regex.pattern)
def cmd_unsubscribe_author(message: Message) -> None:
    chat = update_chat(message)
    value_match = _unsubscribe_author_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_unsubscribe_author_regex} in text '{message.text}'")
    value = value_match.group(1)
    author_id = recipes.models.Author.id_from_name(value)
    try:
        author = recipes.models.Author.objects.get(pk=author_id)
    except recipes.models.Author.DoesNotExist:
        bot.reply_to(message, escape(f"Author '{value}' does not exist"))
    else:
        telegram.models.AuthorSubscription.objects.filter(chat=chat, author=author).delete()
        bot.reply_to(message, escape(f"Unsubscribed from {author.name}"))


@bot.message_handler(commands=['random'])
def cmd_random(message: Message) -> None:
    chat = update_chat(message)
    recipe = recipes.models.Recipe.objects.all().order_by('?')[0]
    bot.send_message(
        chat_id=chat.id,
        text=recipe_to_message(recipe),
    )


@bot.message_handler()
def cmd_unknown(message: Message) -> None:
    bot.reply_to(message, escape('Command not recognized'))
