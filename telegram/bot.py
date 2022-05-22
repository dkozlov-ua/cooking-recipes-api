# pylint: disable=wrong-import-position
import datetime
import logging
import re

import django
import requests
import telebot
from telebot.types import Message, CallbackQuery

django.setup()

from django.conf import settings
from telegram.message import format_recipe_msg, format_recipes_list_msg
from telegram.utils import escape
import recipes.models
import telegram.models

session = requests.Session()
bot = telebot.TeleBot(
    token=settings.TELEGRAM_BOT_TOKEN,
    parse_mode='MarkdownV2',
    threaded=True,
)
logger = logging.getLogger(__name__)

PAGE_SIZE = 10
CALLBACK_SEARCH_RECIPES = 'searchRecipes'


def _update_chat(message: Message) -> telegram.models.Chat:
    chat, _ = telegram.models.Chat.objects.get_or_create(id=message.chat.id)
    chat.username = message.chat.username
    chat.first_name = message.chat.first_name
    chat.last_name = message.chat.last_name
    chat.save()
    return chat


@bot.message_handler(commands=['start'])
def _cmd_start(message: Message) -> None:
    _update_chat(message)
    bot.reply_to(message, escape('You have been registered'))


_subscribe_tag_regex = re.compile(r"^/subscribe\s+.*tag\s+#?(\w+)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_subscribe_tag_regex.pattern)
def _cmd_subscribe_tag(message: Message) -> None:
    chat = _update_chat(message)

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
def _cmd_unsubscribe_tag(message: Message) -> None:
    chat = _update_chat(message)

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
def _cmd_subscribe_author(message: Message) -> None:
    chat = _update_chat(message)

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
def _cmd_unsubscribe_author(message: Message) -> None:
    chat = _update_chat(message)

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


_search_recipe_regex = re.compile(r"^/search\s+(.*)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_search_recipe_regex.pattern)
def _cmd_search_recipes(message: Message) -> None:
    chat = _update_chat(message)

    value_match = _search_recipe_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_search_recipe_regex} in text '{message.text}'")
    value = value_match.group(1)

    search_request = telegram.models.SearchRequestMessage(
        chat=chat,
        query=value.casefold(),
        page_n=0,
    )
    results_page = search_request.current_page(page_size=PAGE_SIZE)
    if results_page:
        msg_text, msg_markup = format_recipes_list_msg(results_page, callback_data_prefix=CALLBACK_SEARCH_RECIPES)
        result_message = bot.send_message(
            chat_id=message.chat.id,
            text=msg_text,
            reply_markup=msg_markup,
            disable_web_page_preview=True,
        )
        search_request.message_id = result_message.message_id
        search_request.save()
    else:
        bot.reply_to(message, 'Recipes not found')


@bot.message_handler(commands=['random'])
def _cmd_random_recipe(message: Message) -> None:
    chat = _update_chat(message)
    recipe = recipes.models.Recipe.objects.all().order_by('?')[0]
    msg_text, msg_markup = format_recipe_msg(recipe)
    bot.send_message(
        chat_id=chat.id,
        text=msg_text,
        reply_markup=msg_markup,
    )


@bot.message_handler()
def _cmd_unknown(message: Message) -> None:
    bot.reply_to(message, escape('Command not recognized'))


@bot.callback_query_handler(func=lambda cb_query: cb_query.data.startswith(f"{CALLBACK_SEARCH_RECIPES}/"))
def _cb_search_recipe(cb_query: CallbackQuery) -> None:
    chat = _update_chat(cb_query.message)
    _, cmd = cb_query.data.split('/')
    search_request = telegram.models.SearchRequestMessage.objects.get(message_id=cb_query.message.message_id, chat=chat)
    if cmd == 'delete':
        bot.delete_message(
            chat_id=chat.id,
            message_id=search_request.message_id,
        )
        search_request.is_deleted = True
    elif cmd in ('previousPage', 'nextPage'):
        if cmd == 'previousPage':
            results_page = search_request.previous_page(page_size=PAGE_SIZE)
        elif cmd == 'nextPage':
            results_page = search_request.next_page(page_size=PAGE_SIZE)
        else:
            raise ValueError(f"Unknown cmd: {cmd}")
        if results_page:
            msg_text, msg_markup = format_recipes_list_msg(results_page, callback_data_prefix=CALLBACK_SEARCH_RECIPES)
            bot.edit_message_text(
                chat_id=cb_query.message.chat.id,
                message_id=cb_query.message.message_id,
                text=msg_text,
                reply_markup=msg_markup,
                disable_web_page_preview=True,
            )
        else:
            bot.answer_callback_query(cb_query.id, 'Recipes not found')
    else:
        raise ValueError(f"Unknown cmd: {cmd}")
    search_request.save()


@bot.callback_query_handler(func=lambda cb_query: cb_query.data.startswith('recipe/'))
def _cb_recipe(cb_query: CallbackQuery) -> None:
    chat = _update_chat(cb_query.message)
    _, recipe_id, cmd = cb_query.data.split('/')
    if cmd == 'show':
        recipe = recipes.models.Recipe.objects.get(id=recipe_id)
        msg_text, msg_markup = format_recipe_msg(recipe)
        bot.send_message(
            chat_id=chat.id,
            text=msg_text,
            reply_markup=msg_markup,
        )
    elif cmd == 'delete':
        bot.delete_message(
            chat_id=cb_query.message.chat.id,
            message_id=cb_query.message.message_id,
        )
