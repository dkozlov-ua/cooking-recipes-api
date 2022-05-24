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
from recipes.models import Tag, Author, Recipe
from telegram.message import format_recipe_msg, format_recipes_list_msg
from telegram.models import Chat, TagSubscription, AuthorSubscription, SearchListMessage, LikedListMessage
from telegram.utils import escape

session = requests.Session()
bot = telebot.TeleBot(
    token=settings.TELEGRAM_BOT_TOKEN,
    parse_mode='MarkdownV2',
    threaded=True,
)
logger = logging.getLogger(__name__)

SEARCH_PAGE_SIZE = 10
LIKED_PAGE_SIZE = 10
CALLBACK_SEARCH_RECIPES = 'searchRecipes'
CALLBACK_LIKED_RECIPES = 'likedRecipes'


_subscribe_tag_regex = re.compile(r"^/subscribe\s+.*tag\s+#?(\w+)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_subscribe_tag_regex.pattern)
def _cmd_subscribe_tag(message: Message) -> None:
    """Handler for bot command "subscribe to the tag"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    value_match = _subscribe_tag_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_subscribe_tag_regex} in text '{message.text}'")
    value = value_match.group(1)

    tag_id = Tag.id_from_name(value)
    try:
        tag = Tag.objects.get(pk=tag_id)
    except Tag.DoesNotExist:
        bot.reply_to(message, escape(f"Tag #{value} does not exist"))
    else:
        TagSubscription.objects.get_or_create(
            chat=chat,
            tag=tag,
            defaults={'last_recipe_date': datetime.datetime.utcnow()},
        )
        bot.reply_to(message, escape(f"Subscribed to tag #{tag.name}"))


_unsubscribe_tag_regex = re.compile(r"^/unsubscribe\s+.*tag\s+#?(\w+)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_unsubscribe_tag_regex.pattern)
def _cmd_unsubscribe_tag(message: Message) -> None:
    """Handler for bot command "unsubscribe from the tag"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    value_match = _unsubscribe_tag_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_unsubscribe_tag_regex} in text '{message.text}'")
    value = value_match.group(1)

    tag_id = Tag.id_from_name(value)
    try:
        tag = Tag.objects.get(pk=tag_id)
    except Tag.DoesNotExist:
        bot.reply_to(message, escape(f"Tag #{value} does not exist"))
    else:
        TagSubscription.objects.filter(chat=chat, tag=tag).delete()
        bot.reply_to(message, escape(f"Unsubscribed from tag #{tag.name}"))


_subscribe_author_regex = re.compile(r"^/subscribe\s+.*author\s+(.*)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_subscribe_author_regex.pattern)
def _cmd_subscribe_author(message: Message) -> None:
    """Handler for bot command "subscribe to the author"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    value_match = _subscribe_author_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_subscribe_author_regex} in text '{message.text}'")

    value = value_match.group(1)
    author_id = Author.id_from_name(value)
    try:
        author = Author.objects.get(pk=author_id)
    except Author.DoesNotExist:
        bot.reply_to(message, escape(f"Author '{value}' does not exist"))
    else:
        AuthorSubscription.objects.get_or_create(
            chat=chat,
            author=author,
            defaults={'last_recipe_date': datetime.datetime.utcnow()},
        )
        bot.reply_to(message, escape(f"Subscribed to {author.name}"))


_unsubscribe_author_regex = re.compile(r"^/unsubscribe\s+.*author\s+(.*)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_unsubscribe_author_regex.pattern)
def _cmd_unsubscribe_author(message: Message) -> None:
    """Handler for bot command "unsubscribe from the author"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    value_match = _unsubscribe_author_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_unsubscribe_author_regex} in text '{message.text}'")

    value = value_match.group(1)
    author_id = Author.id_from_name(value)
    try:
        author = Author.objects.get(pk=author_id)
    except Author.DoesNotExist:
        bot.reply_to(message, escape(f"Author '{value}' does not exist"))
    else:
        AuthorSubscription.objects.filter(chat=chat, author=author).delete()
        bot.reply_to(message, escape(f"Unsubscribed from {author.name}"))


_search_recipe_regex = re.compile(r"^/search\s+(.*)\s*$", flags=re.IGNORECASE)


@bot.message_handler(regexp=_search_recipe_regex.pattern)
def _cmd_search_recipes(message: Message) -> None:
    """Handler for bot command "search for recipes"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    value_match = _search_recipe_regex.search(message.text)
    if not value_match:
        raise ValueError(f"Cannot find matches for regex {_search_recipe_regex} in text '{message.text}'")
    value = value_match.group(1)

    search_list_msg = SearchListMessage(
        chat=chat,
        query=value.casefold(),
        page_n=0,
    )
    page = search_list_msg.current_page(page_size=SEARCH_PAGE_SIZE)
    if page:
        msg_text, msg_markup = format_recipes_list_msg(page, callback_data_prefix=CALLBACK_SEARCH_RECIPES)
        search_request_message = bot.send_message(
            chat_id=message.chat.id,
            text=msg_text,
            reply_markup=msg_markup,
            disable_web_page_preview=True,
        )
        search_list_msg.message_id = search_request_message.message_id
        search_list_msg.save()
    else:
        bot.reply_to(message, 'Recipes not found')


@bot.message_handler(commands=['liked'])
def _cmd_liked_recipes(message: Message) -> None:
    """Handler for bot command "show my liked recipes"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    liked_list_msg = LikedListMessage(
        chat=chat,
        page_n=0,
    )
    page = liked_list_msg.current_page(page_size=LIKED_PAGE_SIZE)
    if page:
        msg_text, msg_markup = format_recipes_list_msg(page, callback_data_prefix=CALLBACK_LIKED_RECIPES)
        liked_list_message = bot.send_message(
            chat_id=message.chat.id,
            text=msg_text,
            reply_markup=msg_markup,
            disable_web_page_preview=True,
        )
        liked_list_msg.message_id = liked_list_message.message_id
        liked_list_msg.save()
    else:
        bot.reply_to(message, 'Recipes not found')


@bot.message_handler(commands=['random'])
def _cmd_random_recipe(message: Message) -> None:
    """Handler for bot command "show a random recipe"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    recipe = Recipe.objects.all().order_by('?')[0]
    msg_text, msg_markup = format_recipe_msg(recipe)
    bot.send_message(
        chat_id=chat.id,
        text=msg_text,
        reply_markup=msg_markup,
    )


@bot.message_handler()
def _cmd_unknown(message: Message) -> None:
    """Handler for unknown or invalid commands

    :param message: Telegram message
    """

    Chat.update_from_message(message)
    bot.reply_to(message, escape('Command not recognized'))


@bot.callback_query_handler(func=lambda cb_query: cb_query.data.startswith(f"{CALLBACK_SEARCH_RECIPES}/"))
def _cb_search_list(cb_query: CallbackQuery) -> None:
    """Callback handler for search results messages

    :param cb_query: Telegram callback query
    """

    chat = Chat.update_from_message(cb_query.message)
    _, cmd = cb_query.data.split('/')
    search_list_msg = SearchListMessage.objects.get(message_id=cb_query.message.message_id, chat=chat)

    if cmd == 'delete':
        bot.delete_message(
            chat_id=chat.id,
            message_id=search_list_msg.message_id,
        )
        search_list_msg.is_deleted = True
    elif cmd in ('previousPage', 'nextPage'):
        if cmd == 'previousPage':
            results_page = search_list_msg.previous_page(page_size=SEARCH_PAGE_SIZE)
        elif cmd == 'nextPage':
            results_page = search_list_msg.next_page(page_size=SEARCH_PAGE_SIZE)
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
    search_list_msg.save()


@bot.callback_query_handler(func=lambda cb_query: cb_query.data.startswith(f"{CALLBACK_LIKED_RECIPES}/"))
def _cb_liked_recipes(cb_query: CallbackQuery) -> None:
    """Callback handler for liked recipes list messages

    :param cb_query: Telegram callback query
    """

    chat = Chat.update_from_message(cb_query.message)
    _, cmd = cb_query.data.split('/')
    liked_list_msg = LikedListMessage.objects.get(message_id=cb_query.message.message_id, chat=chat)

    if cmd == 'delete':
        bot.delete_message(
            chat_id=chat.id,
            message_id=liked_list_msg.message_id,
        )
        liked_list_msg.is_deleted = True
    elif cmd in ('previousPage', 'nextPage'):
        if cmd == 'previousPage':
            results_page = liked_list_msg.previous_page(page_size=LIKED_PAGE_SIZE)
        elif cmd == 'nextPage':
            results_page = liked_list_msg.next_page(page_size=LIKED_PAGE_SIZE)
        else:
            raise ValueError(f"Unknown cmd: {cmd}")
        if results_page:
            msg_text, msg_markup = format_recipes_list_msg(results_page, callback_data_prefix=CALLBACK_LIKED_RECIPES)
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
    liked_list_msg.save()


@bot.callback_query_handler(func=lambda cb_query: cb_query.data.startswith('recipe/'))
def _cb_recipe(cb_query: CallbackQuery) -> None:
    """Callback handler for recipe messages

    :param cb_query: Telegram callback query
    """

    chat = Chat.update_from_message(cb_query.message)
    _, recipe_id, cmd = cb_query.data.split('/')

    if cmd == 'show':
        recipe = Recipe.objects.get(id=recipe_id)
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
    elif cmd == 'like':
        recipe = Recipe.objects.get(id=recipe_id)
        if recipe in chat.liked_recipes.all():
            chat.liked_recipes.remove(recipe)
            bot.answer_callback_query(cb_query.id, 'Removed from liked recipes')
        else:
            chat.liked_recipes.add(recipe)
            bot.answer_callback_query(cb_query.id, 'Added to liked recipes')
