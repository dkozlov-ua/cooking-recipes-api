# pylint: disable=wrong-import-position
import datetime
import logging
import re
from typing import List, Tuple

import django
import requests
import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

django.setup()

from django.db.models import QuerySet
from django.conf import settings
from telegram.formatters import escape, recipe_to_message, recipe_to_search_result
import recipes.models
import telegram.models

session = requests.Session()
bot = telebot.TeleBot(
    token=settings.TELEGRAM_BOT_TOKEN,
    parse_mode='MarkdownV2',
    threaded=True,
)
logger = logging.getLogger(__name__)

SEARCH_RESULTS_PAGE_SIZE = 10


def _update_chat(message: Message) -> telegram.models.Chat:
    chat = telegram.models.Chat(
        id=message.chat.id,
        username=message.chat.username,
        first_name=message.chat.first_name,
        last_name=message.chat.last_name,
    )
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


@bot.message_handler(commands=['random'])
def _cmd_random_recipe(message: Message) -> None:
    chat = _update_chat(message)
    recipe = recipes.models.Recipe.objects.all().order_by('?')[0]
    bot.send_message(
        chat_id=chat.id,
        text=recipe_to_message(recipe),
    )


def _get_search_recipes_queryset(query: str) -> QuerySet[recipes.models.Recipe]:
    return recipes.models.Recipe.text_search(query).order_by('-reviews_count', '-rating', '-pub_date')


def _format_search_recipes_msg(results: List[recipes.models.Recipe]) -> Tuple[str, InlineKeyboardMarkup]:
    result_message_rows: List[str] = []
    result_message_markup_rows: List[List[InlineKeyboardButton]] = [[], []]
    for i, recipe in enumerate(results, start=1):
        result_message_rows.append(
            f"{i}\\. {recipe_to_search_result(recipe)}"
        )
        button = InlineKeyboardButton(text=str(i), callback_data=f"showRecipe/{recipe.id}")
        if i <= 5:
            result_message_markup_rows[0].append(button)
        else:
            result_message_markup_rows[1].append(button)
    result_message_text = '\n'.join(result_message_rows)

    result_message_markup = InlineKeyboardMarkup(row_width=5)
    if result_message_markup_rows[0]:
        result_message_markup.row(*result_message_markup_rows[0])
    if result_message_markup_rows[1]:
        result_message_markup.row(*result_message_markup_rows[1])
    result_message_markup.row(
        InlineKeyboardButton(text='⬅', callback_data='searchRecipe/previousPage'),
        InlineKeyboardButton(text='❌', callback_data='searchRecipe/delete'),
        InlineKeyboardButton(text='➡', callback_data='searchRecipe/nextPage'),
    )

    return result_message_text, result_message_markup


_search_recipe_regex = re.compile(r"^/search\s+(.*)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_search_recipe_regex.pattern)
def _cmd_search_recipes(message: Message) -> None:
    chat = _update_chat(message)

    value_match = _search_recipe_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_search_recipe_regex} in text '{message.text}'")
    value = value_match.group(1)
    query = value.casefold()
    results_page = list(_get_search_recipes_queryset(query)[:SEARCH_RESULTS_PAGE_SIZE])
    if results_page:
        msg_text, msg_markup = _format_search_recipes_msg(results_page)
        result_message = bot.send_message(
            chat_id=message.chat.id,
            text=msg_text,
            reply_markup=msg_markup,
            disable_web_page_preview=True,
        )
        telegram.models.SearchRequestMessage.objects.create(
            message_id=result_message.message_id,
            chat=chat,
            query=query,
            page_n=0,
        )
    else:
        bot.reply_to(message, 'Recipes not found')


@bot.callback_query_handler(func=lambda cb_query: cb_query.data.startswith('searchRecipe/'))
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
        if cmd == 'previousPage' and search_request.page_n == 0:
            bot.answer_callback_query(cb_query.id, 'Recipes not found')
        else:
            if cmd == 'previousPage':
                next_page_n = search_request.page_n - 1
            elif cmd == 'nextPage':
                next_page_n = search_request.page_n + 1
            else:
                raise ValueError(f"Unknown cmd: {cmd}")
            start_idx = SEARCH_RESULTS_PAGE_SIZE * next_page_n
            end_idx = SEARCH_RESULTS_PAGE_SIZE * (next_page_n + 1)

            results_page = list(_get_search_recipes_queryset(search_request.query)[start_idx:end_idx])
            if results_page:
                msg_text, msg_markup = _format_search_recipes_msg(results_page)
                bot.edit_message_text(
                    chat_id=cb_query.message.chat.id,
                    message_id=cb_query.message.message_id,
                    text=msg_text,
                    reply_markup=msg_markup,
                    disable_web_page_preview=True,
                )
                search_request.page_n = next_page_n
            else:
                bot.answer_callback_query(cb_query.id, 'Recipes not found')
    else:
        raise ValueError(f"Unknown cmd: {cmd}")
    search_request.save()


@bot.callback_query_handler(func=lambda cb_query: cb_query.data.startswith('showRecipe/'))
def _cb_show_recipe(cb_query: CallbackQuery) -> None:
    chat = _update_chat(cb_query.message)
    _, recipe_id = cb_query.data.split('/')
    recipe = recipes.models.Recipe.objects.get(id=recipe_id)
    bot.send_message(
        chat_id=chat.id,
        text=recipe_to_message(recipe),
    )


@bot.message_handler()
def _cmd_unknown(message: Message) -> None:
    bot.reply_to(message, escape('Command not recognized'))
