import datetime
import logging
import random
import re
import time
from itertools import count, chain
from typing import List, Tuple, Optional, Dict, Union

import dateparser
import requests
from django.contrib.postgres.search import SearchVector
from django.db import transaction

from recipes.models import Recipe, Tag, Author

logger = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
             'Chrome/100.0.4896.127 Safari/537.36'

_html_tags_regex = re.compile(r"<.*?>")
_encoded_symbols_regex = re.compile(r"&#(\d+);")


def _clean_text(text: str) -> str:
    text = text.replace('&amp;', '&')
    text = _html_tags_regex.sub('', text)
    text = _encoded_symbols_regex.sub(lambda symbol: chr(int(symbol.group(1))), text)
    text = text.replace('—', ' — ')
    return text


BA_API_BASE_URL = 'https://www.bonappetit.com'
BA_ASSETS_BASE_URL = 'https://assets.bonappetit.com'


def _parse_ba_recipe(data: Dict) -> Tuple[Recipe, List[Tag], List[Author]]:
    ingredient_groups = []
    for ingredient_group in data['ingredientGroups']:
        ingredient_groups.append({
            'title': _clean_text(ingredient_group['hed']).rstrip('.'),
            'ingredients': [_clean_text(ingredient['description'])
                            for ingredient in ingredient_group['ingredients']],
        })

    if data['photos']:
        photo_id = data['photos']['tout'][0]['id']
        photo_filename = data['photos']['tout'][0]['filename']
        photo_url = f"{BA_ASSETS_BASE_URL}/photos/{photo_id}/{photo_filename}"
    else:
        photo_url = None

    recipe = Recipe(
        id=data['id'],
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
        if tag_name.startswith('_'):
            continue
        tag = Tag(
            id=Tag.id_from_name(tag_name),
            name=tag_name.replace(' ', '').replace('-', ''),
        )
        tags.append(tag)
    default_tag = Tag(
        id='bonappetit',
        name='BonAppetit',
    )
    tags.append(default_tag)

    authors: List[Author] = []
    if data['contributors']:
        for author_row in chain(
                data['contributors'].get('author') or [],
                data['contributors'].get('chef') or [],
        ):
            for author_name in author_row['name'].strip().split(' & '):
                author_name = author_name.strip()
                if (
                        not author_name
                        or ',' in author_name
                        or len(author_name.split()) > 3
                ):
                    continue
                author = Author(
                    id=Author.id_from_name(author_name),
                    name=author_name,
                )
                authors.append(author)

    return recipe, tags, authors


def _load_ba_page(session: requests.Session, page_n: int) -> Dict:
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
    session = requests.session()
    saved_items_count = 0
    latest_item_date: Optional[datetime.datetime] = None
    oldest_item_date: Optional[datetime.datetime] = None
    for page_n in count(start=from_page):
        data = _load_ba_page(session, page_n)

        if not data['items']:
            logger.info(f"Page {page_n}: stopping: page is empty")
            break

        logger.debug(f"Page {page_n}: fetching items")
        with transaction.atomic():
            for row in data['items']:
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
                recipe.main_tsvector=SearchVector(
                    'name', 'title', 'description', 'short_description', 'ingredient_groups',
                    config='english',
                )
                recipe.save()
                for tag in tags:
                    tag.save()
                recipe.tags.set(tags)
                for author in authors:
                    author.save()
                recipe.authors.set(authors)

        logger.info(f"Page {page_n}: fetched {len(data['items'])} items ({saved_items_count} total)")
        if oldest_item_date:
            logger.info(f"Page {page_n}: fetched from {oldest_item_date.isoformat()}")
        if from_date and oldest_item_date and oldest_item_date <= from_date:
            logger.info(f"Page {page_n}: stopping: reached target date")
            break

        time.sleep(random.uniform(0.85, 1.15) * 3.0)

    return saved_items_count, latest_item_date
