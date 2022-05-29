from typing import Dict, Tuple, List

from more_itertools import chunked_even
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import recipes.models
from telegram.utils import escape


def _format_ingredient_group(group: Dict) -> str:
    header = f"*{escape(group['title'].capitalize())}:*\n" if group['title'] else ''
    body = '\n'.join(f" \\- {escape(ingredient)}" for ingredient in group['ingredients'])
    return header + body


def _recipe_to_list_item_str(recipe: recipes.models.Recipe) -> str:
    url = escape(recipe.url, 'link')
    title = escape(recipe.title)
    rating = escape(f"{recipe.rating:.1f}/{5.0:.1f}")
    reviews_count = escape(f"{recipe.reviews_count}")

    authors_list: Tuple[recipes.models.Author, ...] = tuple(recipe.authors.all())
    if authors_list:
        authors_str = ', '.join(f"_{escape(author.name or author.id)}_" for author in authors_list)
    else:
        authors_str = ''

    if authors_str:
        return f"[{title}]({url}) by {authors_str} \\({rating}, {reviews_count} reviews\\)"
    return f"[{title}]({url}) \\({rating}, {reviews_count} reviews\\)"


def format_recipe_msg(recipe: recipes.models.Recipe) -> Tuple[str, InlineKeyboardMarkup]:
    url = escape(recipe.url, 'link')
    title = escape(recipe.title)
    description = escape(recipe.description.replace('\n', '\n\n'))
    ingredients_list = '\n\n'.join(
        _format_ingredient_group(ingredient_group) for ingredient_group in recipe.ingredient_groups
    )

    authors_list: Tuple[recipes.models.Author, ...] = tuple(recipe.authors.all())
    if authors_list:
        authors_str = 'By ' + ', '.join(f"_{escape(author.name or author.id)}_" for author in authors_list)
    else:
        authors_str = ''

    tags_list: Tuple[recipes.models.Tag, ...] = tuple(recipe.tags.all())
    if tags_list:
        tags_str = ' '.join(f"\\#{escape(tag.name or tag.id)}" for tag in tags_list)
    else:
        tags_str = ''

    msg_text = (
        f"*[{title}]({url})*"
        f"\n\n"
        f"{description}"
        f"\n\n"
        f"{ingredients_list}"
        f"\n\n"
        f"{authors_str}"
        f"\n\n"
        f"{tags_str}"
    ).replace('\n\n\n\n', '\n\n')

    msg_markup = InlineKeyboardMarkup()
    msg_markup.row(
        InlineKeyboardButton(text='❤', callback_data=f"recipe/{recipe.id}/like"),
        InlineKeyboardButton(text='❌', callback_data=f"recipe/{recipe.id}/delete"),
    )
    return msg_text, msg_markup


def format_recipes_list_msg(
        results: List[recipes.models.Recipe],
        *,
        callback_data_prefix: str,
) -> Tuple[str, InlineKeyboardMarkup]:
    msg_text_rows: List[str] = []
    msg_markup_buttons: List[InlineKeyboardButton] = []
    for i, recipe in enumerate(results, start=1):
        msg_text_rows.append(
            f"{i}\\. {_recipe_to_list_item_str(recipe)}"
        )
        msg_markup_buttons.append(
            InlineKeyboardButton(text=str(i), callback_data=f"recipe/{recipe.id}/show")
        )
    msg_text = '\n'.join(msg_text_rows)

    msg_markup = InlineKeyboardMarkup()
    for buttons_row in chunked_even(msg_markup_buttons, n=5):
        msg_markup.row(*buttons_row)
    msg_markup.row(
        InlineKeyboardButton(text='⬅', callback_data=f"{callback_data_prefix}/previousPage"),
        InlineKeyboardButton(text='❌', callback_data=f"{callback_data_prefix}/delete"),
        InlineKeyboardButton(text='➡', callback_data=f"{callback_data_prefix}/nextPage"),
    )

    return msg_text, msg_markup
