import datetime
import logging
import random
import re
import time
from itertools import count, chain
from typing import List, Tuple, Optional, Dict, Union

import dateparser
import requests
from django.db import transaction

from recipes.models import Recipe, Tag, Author

logger = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
             'Chrome/100.0.4896.127 Safari/537.36'

_html_tags_regex = re.compile(r"<.*?>")
_encoded_symbols_regex = re.compile(r"&#(\d+);")


def _clean_text(text: str) -> str:
    """Removes HTML tags and decodes amp-encoded symbols in a text.

    :param text: a text to be cleaned.
    :return: a cleaned text.
    """

    text = text.replace('&amp;', '&')
    text = _html_tags_regex.sub('', text)
    text = _encoded_symbols_regex.sub(lambda symbol: chr(int(symbol.group(1))), text)
    text = text.replace('—', ' — ')
    return text


BA_API_BASE_URL = 'https://www.bonappetit.com'
BA_ASSETS_BASE_URL = 'https://assets.bonappetit.com'


def _parse_ba_recipe(data: Dict) -> Tuple[Recipe, List[Tag], List[Author]]:
    """Parses raw Bon Appétit recipe.

    Returned `Recipe` instance is not saved to the database.
    Returned `Tag` and `Author` instances must be saved and added to recipe's tags and authors.

    :param data: a raw recipe data.
    :return: a tuple containing a recipe, a list of recipe's tags and a list of recipe's authors.
    """

    ingredient_groups = []
    for ingredient_group in data['ingredientGroups']:
        ingredient_groups.append({
            'title': _clean_text(ingredient_group['hed']).rstrip('.').capitalize(),
            'ingredients': [_clean_text(ingredient['description']) for ingredient in ingredient_group['ingredients']],
        })

    if data['photos']:
        photo_id = data['photos']['tout'][0]['id']
        photo_filename = data['photos']['tout'][0]['filename']
        photo_url = f"{BA_ASSETS_BASE_URL}/photos/{photo_id}/{photo_filename}"
    else:
        photo_url = None

    recipe = Recipe(
        id=data['id'],
        source=Recipe.Sources.BON_APPETIT,
        url=f"{BA_API_BASE_URL}{data['url']}",
        pub_date=dateparser.parse(data['pubDate']),
        name=_clean_text(data['hed']),
        title=_clean_text(data['socialTitle']),
        description=_clean_text(data['dek']),
        short_description=_clean_text(data['socialDescription']),
        rating=data['aggregateRating'],
        reviews_count=data.get('reviewsCount', 0),
        wma_count=data.get('willMakeAgainPct', 0),
        ingredient_groups=ingredient_groups,
        photo_url=photo_url,
    )

    tags: List[Tag] = []
    for tag_name in data['cneTags']:
        # Ignore internal tags
        if tag_name.startswith('_'):
            continue
        tag = Tag(
            id=Tag.id_from_name(tag_name),
            name=Tag.normalize_name(tag_name),
        )
        tags.append(tag)

    source_tag_name = 'FromBonAppétit'
    source_tag = Tag(
        id=Tag.id_from_name(source_tag_name),
        name=Tag.normalize_name(source_tag_name),
    )
    tags.append(source_tag)

    authors: List[Author] = []
    if data['contributors']:
        for author_row in chain(
                data['contributors'].get('author') or [],
                data['contributors'].get('chef') or [],
        ):
            authors_names = author_row['name'].strip().split(' & ')
            for author_name in authors_names:
                author_name = author_name.strip()
                # Ignore addresses, empty values and other junk
                if (
                        not author_name
                        or ',' in author_name
                        or (len(author_name.split()) > 3 and author_name != 'The Bon Appétit Test Kitchen')
                ):
                    continue
                author = Author(
                    id=Author.id_from_name(author_name),
                    name=Author.normalize_name(author_name),
                )
                authors.append(author)

    return recipe, tags, authors


def _load_ba_page(session: requests.Session, page_n: int) -> Dict:
    """Loads a search results page from the Bon Appétit internal API.

    :param session: a `Session` object to make requests.
    :param page_n: a target page number.
    :return: internal API response.
    """

    ba_url = f"{BA_API_BASE_URL}/api/search"
    params: Dict[str, Union[str, int]] = {
        'content': 'recipe',
        'sort': 'newest',
        'page': page_n,
    }
    attempt_n = 1
    while True:
        try:
            logger.debug(f"Page {page_n}: loading")
            resp = session.get(url=ba_url, params=params)
            resp.raise_for_status()
        except (requests.HTTPError, requests.JSONDecodeError) as exc:
            logger.warning(f"Page {page_n}: error (attempt {attempt_n}/{3}): {type(exc).__name__}: {str(exc)}")
            if attempt_n >= 3:
                raise
            time.sleep(random.uniform(0.85, 1.15) * 3.0)
            attempt_n += 1
        else:
            return resp.json()


def bonappetit(from_date: Optional[datetime.datetime], from_page: int = 1) -> Tuple[int, Optional[datetime.datetime]]:
    """Scrapes and saves to the database recipes from the Bon Appétit internal API.

    Recipes always fetched from newer to older.
    Saves only recipes with pub_date > from_date.

    :param from_date: a datetime indicating when to stop scraping.
    :param from_page: a number of a page to start from.
    :return: a tuple containing a number of saved recipes
             and a datetime of the latest found (not necessarily saved) recipe.
    """

    session = requests.session()
    saved_items_count = 0
    latest_item_date: Optional[datetime.datetime] = None
    oldest_item_date: Optional[datetime.datetime] = None
    for page_n in count(start=from_page):
        data = _load_ba_page(session, page_n)

        # An empty page indicates the end of results
        if not data['items']:
            logger.info(f"Page {page_n}: stopping: page is empty")
            break

        logger.debug(f"Page {page_n}: fetching items")
        with transaction.atomic():
            for row in data['items']:
                # Ignore sponsored recipes
                # Usually they have non-standard structure and/or zero culinary value
                if '/sponsored/' in row['url'] or row['template'] == 'sponsored':
                    continue
                pub_date = dateparser.parse(row['pubDate'])
                if pub_date:
                    if not oldest_item_date or pub_date < oldest_item_date:
                        oldest_item_date = pub_date
                    if not latest_item_date or pub_date > latest_item_date:
                        latest_item_date = pub_date
                    if from_date and pub_date <= from_date:
                        continue
                saved_items_count += 1

                recipe, tags, authors = _parse_ba_recipe(row)
                recipe.save()
                # Saving recipe's tags and authors before adding them to corresponding sets.
                Tag.objects.bulk_create(tags, ignore_conflicts=True)
                Author.objects.bulk_create(authors, ignore_conflicts=True)
                recipe.tags.set(tags)
                recipe.authors.set(authors)

        logger.info(f"Page {page_n}: fetched {len(data['items'])} items ({saved_items_count} total)")
        if oldest_item_date:
            logger.info(f"Page {page_n}: fetched from {oldest_item_date.isoformat()}")
        if from_date and oldest_item_date and oldest_item_date <= from_date:
            logger.info(f"Page {page_n}: stopping: reached target date")
            break

        # Small pause between requests
        time.sleep(random.uniform(0.85, 1.15) * 3.0)

    return saved_items_count, latest_item_date
