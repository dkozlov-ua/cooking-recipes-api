# pylint: disable=wrong-import-position
import datetime
import logging
import re
from typing import Optional, Union

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


class TagNotFoundError(Exception):
    def __init__(self, name: str, *args):
        super().__init__(*args)
        self.tag_name = name

    def __str__(self) -> str:
        return self.tag_name


class AuthorNotFoundError(Exception):
    def __init__(self, name: str, *args):
        super().__init__(*args)
        self.author_name = name

    def __str__(self) -> str:
        return self.author_name


class AmbiguousCommandSubject(Exception):
    def __init__(self, tag: Tag, author: Author, *args):
        super().__init__(*args)
        self.tag = tag
        self.author = author

    def __str__(self) -> str:
        return f"{self.tag} or {self.author}"


def _get_command_subject(params: str) -> Union[Tag, Author, None]:
    tag: Optional[Tag]
    author: Optional[Author]
    if re.match(r"^tag\s+|#.*$", params, flags=re.IGNORECASE):
        tag_name = re.sub(r"(^tag\s+#?)|(\s+)", '', params, flags=re.IGNORECASE)
        try:
            return Tag.objects.get(id=Tag.id_from_name(tag_name))
        except Tag.DoesNotExist as exc:
            raise TagNotFoundError(name=tag_name) from exc
    elif re.match(r"^author\s+.*$", params, flags=re.IGNORECASE):
        author_name = re.sub(r"^author\s+", '', params, flags=re.IGNORECASE)
        try:
            return Author.objects.get(id=Author.id_from_name(author_name))
        except Author.DoesNotExist as exc:
            raise AuthorNotFoundError(name=author_name) from exc
    else:
        try:
            author = Author.objects.get(id=Author.id_from_name(params))
        except Author.DoesNotExist:
            author = None
        try:
            tag = Tag.objects.get(id=Tag.id_from_name(params))
        except Tag.DoesNotExist:
            tag = None
        if tag and author:
            raise AmbiguousCommandSubject(tag=tag, author=author)
        return tag or author


@bot.message_handler(commands=['subscribe'])
def _cmd_subscribe(message: Message) -> None:
    """Handler for bot command "/subscribe"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    params_match = re.search(r"^/subscribe\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if not params_match or params_match.group(1).casefold() == 'help':
        msg_text = (
            'Subscribe to new recipes containing a tag or written by an author\\.'
            '\nUsage:'
            '\n  /subscribe *\\#hashtag*'
            '\n  /subscribe tag *\\#hashtag*'
            '\n  /subscribe *Author Name*'
            '\n  /subscribe author *Author Name*'
        )
        bot.reply_to(message, msg_text)
        return

    params = params_match.group(1)
    try:
        item = _get_command_subject(params)
    except TagNotFoundError as exc:
        msg_text = f"Tag *\\#{escape(exc.tag_name)}* does not exist"
        bot.reply_to(message, msg_text)
        return
    except AuthorNotFoundError as exc:
        msg_text = f"Author *{escape(exc.author_name)}* does not exist"
        bot.reply_to(message, msg_text)
        return
    except AmbiguousCommandSubject as exc:
        msg_text = (
            f"Cannot decide between a tag and an author\\."
            f"\nPlease repeat your command and specify item type:"
            f"\n  /subscribe tag *\\#{escape(exc.tag.name)}*"
            f"\n    or"
            f"\n  /subscribe author *{escape(exc.author.name)}*"
        )
        bot.reply_to(message, msg_text)
        return

    if not item:
        msg_text = f"Cannot find not author nor tag named *{escape(params)}*"
        bot.reply_to(message, msg_text)
        return

    if isinstance(item, Author):
        AuthorSubscription.objects.get_or_create(
            chat=chat,
            author=item,
            defaults={'last_recipe_date': datetime.datetime.utcnow()},
        )
        bot.reply_to(message, f"Subscribed to author *{escape(item.name)}*")
    elif isinstance(item, Tag):
        TagSubscription.objects.get_or_create(
            chat=chat,
            tag=item,
            defaults={'last_recipe_date': datetime.datetime.utcnow()},
        )
        bot.reply_to(message, f"Subscribed to tag *\\#{escape(item.name)}*")


@bot.message_handler(commands=['unsubscribe'])
def _cmd_unsubscribe(message: Message) -> None:
    """Handler for bot command "/unsubscribe"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    params_match = re.search(r"^/subscribe\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if not params_match or params_match.group(1).casefold() == 'help':
        msg_text = (
            'Remove created subscription\\.'
            '\nUsage:'
            '\n  /unsubscribe *\\#hashtag*'
            '\n  /unsubscribe tag *\\#hashtag*'
            '\n  /unsubscribe *Author Name*'
            '\n  /unsubscribe author *Author Name*'
        )
        bot.reply_to(message, msg_text)
        return

    params = params_match.group(1)
    try:
        item = _get_command_subject(params)
    except TagNotFoundError as exc:
        msg_text = f"Tag *\\#{escape(exc.tag_name)}* does not exist"
        bot.reply_to(message, msg_text)
        return
    except AuthorNotFoundError as exc:
        msg_text = f"Author *{escape(exc.author_name)}* does not exist"
        bot.reply_to(message, msg_text)
        return
    except AmbiguousCommandSubject as exc:
        msg_text = (
            f"Cannot decide between a tag and an author\\."
            f"\nPlease repeat your command and specify item type:"
            f"\n  /unsubscribe tag *\\#{escape(exc.tag.name)}*"
            f"\n    or"
            f"\n  /unsubscribe author *{escape(exc.author.name)}*"
        )
        bot.reply_to(message, msg_text)
        return

    if not item:
        msg_text = f"Cannot find not author nor tag named *{escape(params)}*"
        bot.reply_to(message, msg_text)
        return

    if isinstance(item, Author):
        AuthorSubscription.objects.filter(chat=chat, author=item).delete()
        bot.reply_to(message, f"Unsubscribed from author *{escape(item.name)}*")
    elif isinstance(item, Tag):
        TagSubscription.objects.filter(chat=chat, tag=item).delete()
        bot.reply_to(message, f"Unsubscribed from tag *\\#{escape(item.name)}*")


@bot.message_handler(commands=['search'])
def _cmd_search(message: Message) -> None:
    """Handler for bot command "/search"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    params_match = re.search(r"^/search\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if not params_match or params_match.group(1).casefold() == 'help':
        msg_text = (
            'Show the list of your favorite recipes\\.'
            '\nUsage:'
            '\n  /search *italian pizza* \\- search for classic pizza recipes'
            '\n  /search *chicken or beef* \\- search for chicken or beef recipes'
            '\n  /search *pizza \\-pineapple* \\- search for pizza without pineapple recipes'
        )
        bot.reply_to(message, msg_text)
        return

    search_list_msg = SearchListMessage(
        chat=chat,
        query=params_match.group(1).casefold(),
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
def _cmd_liked(message: Message) -> None:
    """Handler for bot command "/liked"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    params_match = re.search(r"^/liked\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if params_match:
        msg_text = (
            'Show the list of your favorite recipes\\.'
            '\nUsage:'
            '\n  /liked'
        )
        bot.reply_to(message, msg_text)
        return

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
def _cmd_random(message: Message) -> None:
    """Handler for bot command "/random"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    params_match = re.search(r"^/random\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if params_match:
        msg_text = (
            'Show a random recipe\\.'
            '\nUsage:'
            '\n  /random'
        )
        bot.reply_to(message, msg_text)
        return

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
    help_text = (
        'You can control me by sending these commands:'
        '\n'
        '\n  /search \\- search for recipes'
        '\n  /liked \\- view your favorite recipes'
        '\n  /random \\- get a random recipe'
        '\n  /subscribe \\- subscribe to a tag or author'
        '\n  /unsubscribe \\- unsubscribe from a tag or author'
    )
    bot.reply_to(message, help_text)


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
