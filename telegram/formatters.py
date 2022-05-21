from typing import Literal, Dict

import recipes.models


def escape(text: str, entity_type: Literal['link', 'code', 'text'] = 'text') -> str:
    if entity_type == 'link':
        escaped_symbols = '\\)'
    elif entity_type == 'code':
        escaped_symbols = '\\`'
    elif entity_type == 'text':
        escaped_symbols = '\\_*[]()~`>#+-=|{}.!'
    else:
        raise ValueError(f"Unknown entity_type: {entity_type}")

    for symbol in escaped_symbols:
        text = text.replace(symbol, f"\\{symbol}")
    return text


def _format_ingredient_group(group: Dict) -> str:
    header = f"*{escape(group['title'])}:*\n" if group['title'] else ''
    body = '\n'.join(f" \\- {escape(ingredient)}" for ingredient in group['ingredients'])
    return header + body


def recipe_to_message(recipe: recipes.models.Recipe) -> str:
    url = escape(recipe.url, 'link')
    title = escape(recipe.title)
    description = escape(recipe.description.replace('\n', '\n\n'))
    ingredients_list = '\n\n'.join(
        _format_ingredient_group(ingredient_group) for ingredient_group in recipe.ingredient_groups
    )

    if recipe.authors:
        authors_str = 'By ' + ', '.join(f"_{escape(author.name or author.id)}_" for author in recipe.authors.all())
    else:
        authors_str = ''

    if recipe.tags:
        tags_str = ' '.join(f"\\#{escape(tag.name or tag.id)}" for tag in recipe.tags.all())
    else:
        tags_str = ''

    return (
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


def recipe_to_search_result(recipe: recipes.models.Recipe) -> str:
    url = escape(recipe.url, 'link')
    title = escape(recipe.title)
    rating = escape(f"{recipe.rating:.1f}/{5.0:.1f}")
    reviews_count = escape(f"{recipe.reviews_count}")
    return f"[{title}]({url}) \\({rating}, {reviews_count} reviews\\)"
