import datetime
import logging
import re
from typing import Optional, Union, List, Literal

import requests
import telebot
from django.conf import settings
from telebot.types import Message, CallbackQuery

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
SUBSCRIPTIONS_LIMIT = 50
BLOCKED_LIMIT = 50
CALLBACK_SEARCH_RECIPES = 'searchRecipes'
CALLBACK_LIKED_RECIPES = 'likedRecipes'


class TagNotFoundError(Exception):
    def __init__(self, *args, name: str, corrected_variant: Optional[Tag]):
        super().__init__(*args)
        self.tag_name = name
        self.corrected_variant = corrected_variant


class AuthorNotFoundError(Exception):
    def __init__(self, *args, name: str, corrected_variant: Optional[Author]):
        super().__init__(*args)
        self.author_name = name
        self.corrected_variant = corrected_variant


class NothingFoundError(Exception):
    def __init__(self, *args, corrected_tag_variant: Optional[Tag], corrected_author_variant: Optional[Author]):
        super().__init__(*args)
        self.corrected_tag_variant = corrected_tag_variant
        self.corrected_author_variant = corrected_author_variant


class AmbiguousCommandSubject(Exception):
    def __init__(self, *args, tag: Tag, author: Author):
        super().__init__(*args)
        self.tag = tag
        self.author = author


def _get_command_subject(args: str) -> Union[Tag, Author]:
    """Select a `Tag` or an `Author` instance mentioned in a command `args`.

    :param args: a command arguments string.
    :return: a `Tag` or an `Author`.
    """

    args = re.sub(r"\s+", ' ', args)

    # If `args` starts with 'tag' or '#' - look for tag
    if re.match(r"^tag\s|#.*$", args, flags=re.IGNORECASE):
        tag_name = re.sub(r"(^tag\s#?)|(\s)", '', args, flags=re.IGNORECASE)  # remove prefixes from tag's name
        tag_id = Tag.id_from_name(tag_name)
        try:
            return Tag.objects.get(id=tag_id)
        except Tag.DoesNotExist as exc:
            raise TagNotFoundError(
                name=tag_name,
                corrected_variant=Tag.fuzzy_search(tag_name),  # try to find correct tag in case of a typo
            ) from exc
    # If `args` starts with 'tag' or '#' - look for tag
    elif re.match(r"^author\s+.*$", args, flags=re.IGNORECASE):
        author_name = re.sub(r"^author\s+", '', args, flags=re.IGNORECASE)  # remove prefixes from author's name
        author_id = Author.id_from_name(author_name)
        try:
            return Author.objects.get(id=author_id)
        except Author.DoesNotExist as exc:
            raise AuthorNotFoundError(
                name=author_name,
                corrected_variant=Author.fuzzy_search(author_name),  # try to find correct author in case of a typo
            ) from exc
    # Try to find both tag and author
    else:
        try:
            author = Author.objects.get(id=Author.id_from_name(args))
        except Author.DoesNotExist:
            author = None
        try:
            tag = Tag.objects.get(id=Tag.id_from_name(args))
        except Tag.DoesNotExist:
            tag = None

        # Found both tag and author and is not able to choose between them
        if tag and author:
            raise AmbiguousCommandSubject(tag=tag, author=author)
        # Found a tag
        if tag:
            return tag
        # Found an author
        if author:
            return author
        # Nothing found - trying to propose correct variants
        raise NothingFoundError(
            corrected_tag_variant=Tag.fuzzy_search(Tag.normalize_name(args)),
            corrected_author_variant=Author.fuzzy_search(Author.normalize_name(args)),
        )


@bot.message_handler(commands=['subscribe', 'unsubscribe'])
def _cmd_subscription(message: Message) -> None:
    """Handler for bot commands /subscribe and /unsubscribe

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    cmd: Literal['subscribe', 'unsubscribe']
    if message.text.startswith('/subscribe'):
        cmd = 'subscribe'
    elif message.text.startswith('/unsubscribe'):
        cmd = 'unsubscribe'
    else:
        raise ValueError(f"Cannot get command from message text: {message.text}")

    args_match = re.search(r"^/(?:un)?subscribe\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if not args_match or args_match.group(1).casefold() == 'help':
        msg_text = (
            f"Subscribe to new recipes containing a tag or written by an author\\."
            f"\nUsage:"
            f"\n  /{cmd} *\\#hashtag*"
            f"\n  /{cmd} tag *\\#hashtag*"
            f"\n  /{cmd} *Author Name*"
            f"\n  /{cmd} author *Author Name*"
        )
        bot.reply_to(message, msg_text)
        return

    args = args_match.group(1)
    try:
        item = _get_command_subject(args)
    except TagNotFoundError as exc:
        msg_text = f"Tag *\\#{escape(exc.tag_name)}* does not exist\\."
        if exc.corrected_variant:
            msg_text += f"\nDid you mean *\\#{escape(exc.corrected_variant.name)}*?"
        bot.reply_to(message, msg_text)
        return
    except AuthorNotFoundError as exc:
        msg_text = f"Author *{escape(exc.author_name)}* does not exist\\."
        if exc.corrected_variant:
            msg_text += f"\nDid you mean *{escape(exc.corrected_variant.name)}*?"
        bot.reply_to(message, msg_text)
        return
    except NothingFoundError as exc:
        msg_text = f"Cannot find not author nor tag named *{escape(args)}*\\."
        corrected_variants: List[str] = []
        if exc.corrected_tag_variant:
            corrected_variants.append(f"*\\#{escape(exc.corrected_tag_variant.name)}*")
        if exc.corrected_author_variant:
            corrected_variants.append(f"*{escape(exc.corrected_author_variant.name)}*")
        if corrected_variants:
            msg_text += f"\nDid you mean {' or '.join(corrected_variants)}?"
        bot.reply_to(message, msg_text)
        return
    except AmbiguousCommandSubject as exc:
        msg_text = (
            f"Cannot decide between a tag and an author\\."
            f"\nPlease repeat your command and specify item type:"
            f"\n  /{cmd} tag *\\#{escape(exc.tag.name)}*"
            f"\n    or"
            f"\n  /{cmd} author *{escape(exc.author.name)}*"
        )
        bot.reply_to(message, msg_text)
        return

    if cmd == 'subscribe':
        subscriptions_count = \
            TagSubscription.objects.filter(chat=chat).count() + AuthorSubscription.objects.filter(chat=chat).count()
        if subscriptions_count >= SUBSCRIPTIONS_LIMIT:
            msg_text = (
                f"You have reached the subscriptions limit \\({SUBSCRIPTIONS_LIMIT}\\)\\."
                f" Please remove some with /unsubscribe commands first\\."
            )
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
    elif cmd == 'unsubscribe':
        if isinstance(item, Author):
            AuthorSubscription.objects.filter(chat=chat, author=item).delete()
            bot.reply_to(message, f"Unsubscribed from author *{escape(item.name)}*")
        elif isinstance(item, Tag):
            TagSubscription.objects.filter(chat=chat, tag=item).delete()
            bot.reply_to(message, f"Unsubscribed from tag *\\#{escape(item.name)}*")


@bot.message_handler(commands=['subscriptions'])
def _cmd_subscriptions_list(message: Message) -> None:
    """Handler for bot commands /subscriptions

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    args_match = re.search(r"^/subscriptions\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if args_match:
        msg_text = (
            'Show the list of your subscriptions\\.'
            '\nUsage:'
            '\n  /subscriptions'
        )
        bot.reply_to(message, msg_text)
        return

    msg_blocks: List[str] = []
    tag_subscriptions = TagSubscription.objects.filter(chat=chat).prefetch_related().order_by('tag__name')
    if tag_subscriptions:
        tags_list = (subscription.tag for subscription in tag_subscriptions)
        msg_blocks.append(
            '*Tags:*\n' + '\n'.join(f"  \\#{escape(tag.name)}" for tag in tags_list)
        )
    author_subscriptions = AuthorSubscription.objects.filter(chat=chat).prefetch_related().order_by('author__name')
    if author_subscriptions:
        authors_list = (subscription.author for subscription in author_subscriptions)
        msg_blocks.append(
            '*Authors:*\n' + '\n'.join(f"  {escape(author.name)}" for author in authors_list)
        )
    if not msg_blocks:
        msg_text = 'You don\'t have any subscriptions\\.' \
                   ' You can subscribe to tags and authors with /subscribe command\\.'
        bot.reply_to(message, msg_text)
        return
    bot.reply_to(message, '\n\n'.join(msg_blocks))


@bot.message_handler(commands=['block', 'unblock'])
def _cmd_block(message: Message) -> None:
    """Handler for bot commands /block and /unblock

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)

    cmd: Literal['block', 'unblock']
    if message.text.startswith('/block'):
        cmd = 'block'
    elif message.text.startswith('/unblock'):
        cmd = 'unblock'
    else:
        raise ValueError(f"Cannot get command from message text: {message.text}")

    args_match = re.search(r"^/(?:un)?block\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if not args_match or args_match.group(1).casefold() == 'help':
        msg_text = (
            f"Block recipes containing a tag or written by an author\\."
            f"\nUsage:"
            f"\n  /{cmd} *\\#hashtag*"
            f"\n  /{cmd} tag *\\#hashtag*"
            f"\n  /{cmd} *Author Name*"
            f"\n  /{cmd} author *Author Name*"
        )
        bot.reply_to(message, msg_text)
        return

    args = args_match.group(1)
    try:
        item = _get_command_subject(args)
    except TagNotFoundError as exc:
        msg_text = f"Tag *\\#{escape(exc.tag_name)}* does not exist\\."
        if exc.corrected_variant:
            msg_text += f"\nDid you mean *\\#{escape(exc.corrected_variant.name)}*?"
        bot.reply_to(message, msg_text)
        return
    except AuthorNotFoundError as exc:
        msg_text = f"Author *{escape(exc.author_name)}* does not exist\\."
        if exc.corrected_variant:
            msg_text += f"\nDid you mean *{escape(exc.corrected_variant.name)}*?"
        bot.reply_to(message, msg_text)
        return
    except NothingFoundError as exc:
        msg_text = f"Cannot find not author nor tag named *{escape(args)}*\\."
        corrected_variants: List[str] = []
        if exc.corrected_tag_variant:
            corrected_variants.append(f"*\\#{escape(exc.corrected_tag_variant.name)}*")
        if exc.corrected_author_variant:
            corrected_variants.append(f"*{escape(exc.corrected_author_variant.name)}*")
        if corrected_variants:
            msg_text += f"\nDid you mean {' or '.join(corrected_variants)}?"
        bot.reply_to(message, msg_text)
        return
    except AmbiguousCommandSubject as exc:
        msg_text = (
            f"Cannot decide between a tag and an author\\."
            f"\nPlease repeat your command and specify item type:"
            f"\n  /{cmd} tag *\\#{escape(exc.tag.name)}*"
            f"\n    or"
            f"\n  /{cmd} author *{escape(exc.author.name)}*"
        )
        bot.reply_to(message, msg_text)
        return

    if cmd == 'block':
        blocked_count = chat.blocked_tags.all().count() + chat.blocked_authors.all().count()
        if blocked_count >= BLOCKED_LIMIT:
            msg_text = (
                f"You have reached the blocked items limit \\({BLOCKED_LIMIT}\\)\\."
                f" Please remove some with /unblock commands first\\."
            )
            bot.reply_to(message, msg_text)
            return

        if isinstance(item, Author):
            chat.blocked_authors.add(item)
            bot.reply_to(message, f"Blocked author *{escape(item.name)}*")
        elif isinstance(item, Tag):
            chat.blocked_tags.add(item)
            bot.reply_to(message, f"Blocked tag *\\#{escape(item.name)}*")
    elif cmd == 'unblock':
        if isinstance(item, Author):
            chat.blocked_authors.remove(item)
            bot.reply_to(message, f"Unblocked author *{escape(item.name)}*")
        elif isinstance(item, Tag):
            chat.blocked_tags.remove(item)
            bot.reply_to(message, f"Unblocked tag *\\#{escape(item.name)}*")


@bot.message_handler(commands=['blocked'])
def _cmd_blocked_list(message: Message) -> None:
    """Handler for bot commands /blocked

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    args_match = re.search(r"^/blocked\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if args_match:
        msg_text = (
            'Show the list of your blocked items\\.'
            '\nUsage:'
            '\n  /blocked'
        )
        bot.reply_to(message, msg_text)
        return

    msg_blocks: List[str] = []
    blocked_tags = chat.blocked_tags.all().order_by('name')
    if blocked_tags:
        msg_blocks.append(
            '*Tags:*\n' + '\n'.join(f"  \\#{escape(tag.name)}" for tag in blocked_tags)
        )
    blocked_authors = chat.blocked_authors.all().order_by('name')
    if blocked_authors:
        msg_blocks.append(
            '*Authors:*\n' + '\n'.join(f"  {escape(author.name)}" for author in blocked_authors)
        )
    if not msg_blocks:
        msg_text = 'You don\'t have any blocked items\\.' \
                   ' You can block tags and authors with /block command\\.'
        bot.reply_to(message, msg_text)
        return
    bot.reply_to(message, '\n\n'.join(msg_blocks))


@bot.message_handler(commands=['search'])
def _cmd_search(message: Message) -> None:
    """Handler for bot command "/search"

    :param message: Telegram message
    """

    chat = Chat.update_from_message(message)
    args_match = re.search(r"^/search\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if not args_match or args_match.group(1).casefold() == 'help':
        msg_text = (
            'Search for recipes\\.'
            '\nUsage:'
            '\n  /search *italian pizza* \\- search for classic pizza recipes'
            '\n  /search *ingredients: pork or beef* \\- search for pork or beef recipes'
            '\n  /search *pizza, ingredients: \\-pineapple* \\- search for pizza without pineapple recipes'
        )
        bot.reply_to(message, msg_text)
        return

    args = args_match.group(1).casefold()
    try:
        recipe_query, ingredients_query = args.split('ingredients', maxsplit=1)
    except ValueError:
        recipe_query, ingredients_query = args, ''

    search_list_msg = SearchListMessage(
        chat=chat,
        recipe_query=recipe_query.strip('\n ,.:'),
        ingredients_query=ingredients_query.strip('\n ,.:'),
        page_n=0,
    )
    results_page = search_list_msg.current_page(page_size=SEARCH_PAGE_SIZE)
    if results_page:
        msg_text, msg_markup = format_recipes_list_msg(
            results=results_page,
            total_results_count=search_list_msg.total_results_count(),
            page_size=SEARCH_PAGE_SIZE,
            current_page_n=search_list_msg.page_n,
            callback_data_prefix=CALLBACK_SEARCH_RECIPES,
        )
        search_request_message = bot.reply_to(
            message=message,
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
    args_match = re.search(r"^/liked\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if args_match:
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
    results_page = liked_list_msg.current_page(page_size=LIKED_PAGE_SIZE)
    if results_page:
        msg_text, msg_markup = format_recipes_list_msg(
            results=results_page,
            total_results_count=liked_list_msg.total_results_count(),
            page_size=LIKED_PAGE_SIZE,
            current_page_n=liked_list_msg.page_n,
            callback_data_prefix=CALLBACK_LIKED_RECIPES,
        )
        liked_list_message = bot.reply_to(
            message=message,
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
    args_match = re.search(r"^/random\s+(.*?)\s*$", message.text, flags=re.IGNORECASE)
    if args_match:
        msg_text = (
            'Show a random recipe\\.'
            '\nUsage:'
            '\n  /random'
        )
        bot.reply_to(message, msg_text)
        return

    recipe = Recipe.objects \
        .all() \
        .exclude(tags=chat.blocked_tags) \
        .exclude(authors=chat.blocked_authors) \
        .order_by('?')[0]
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
    msg_text = (
        'You can control me by sending these commands:'
        '\n'
        '\n  /search \\- search for recipes'
        '\n  /liked \\- view your favorite recipes'
        '\n  /random \\- get a random recipe'
        '\n  /subscribe \\- subscribe to a tag or author'
        '\n  /unsubscribe \\- unsubscribe from a tag or author'
        '\n  /subscriptions \\- view your subscriptions'
        '\n  /block \\- block recipes containing a tag or written by an author'
        '\n  /unblock \\- remove a tag or an author from your blocked list'
        '\n  /blocked \\- view your blocked list'
    )
    bot.reply_to(message, msg_text)


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
            msg_text, msg_markup = format_recipes_list_msg(
                results=results_page,
                total_results_count=search_list_msg.total_results_count(),
                page_size=SEARCH_PAGE_SIZE,
                current_page_n=search_list_msg.page_n,
                callback_data_prefix=CALLBACK_SEARCH_RECIPES,
            )
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
            msg_text, msg_markup = format_recipes_list_msg(
                results=results_page,
                total_results_count=liked_list_msg.total_results_count(),
                page_size=LIKED_PAGE_SIZE,
                current_page_n=liked_list_msg.page_n,
                callback_data_prefix=CALLBACK_LIKED_RECIPES,
            )
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
