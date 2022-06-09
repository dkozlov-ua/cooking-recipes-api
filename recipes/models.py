from __future__ import annotations

import re
from typing import Optional, Literal, Iterable

import unicodedata
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField, SearchQuery, SearchVector, TrigramSimilarity
from django.db import models
from django.db.models import F, QuerySet, Manager


class Tag(models.Model):
    id = models.TextField(primary_key=True)
    name = models.TextField()

    class Meta:
        ordering = ['id']
        indexes = [
            GinIndex(fields=['name'], opclasses=['gin_trgm_ops'], name='tag_name_gin_trgm_idx'),
        ]

    @staticmethod
    def id_from_name(name: str) -> str:
        """Generates a normalized id value from a verbose name.

        :param name: a tag's name.
        :return: a normalized id value.
        """

        item_id = name.casefold()
        item_id = unicodedata.normalize('NFKC', item_id)
        item_id = re.sub(r"'s", '', item_id)
        item_id = re.sub(r"\W+", '', item_id)
        return item_id

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalizes a tag's name

        :param name: a verbose tag's name.
        :return: a normalized verbose tag's name.
        """

        name = unicodedata.normalize('NFKC', name)
        name = re.sub(r"'s", '', name)
        name = re.sub(r"\W+", '', name)
        return name

    @classmethod
    def fuzzy_search(cls, name: str) -> Optional[Tag]:
        """Find a `Tag` object using fuzzy search technics.

        :param name: a verbose tag's name.
        :return: a `Tag` object or None.
        """

        try:
            return cls.objects \
                .annotate(similarity=TrigramSimilarity('name', name)) \
                .filter(similarity__gt=0.3) \
                .order_by('-similarity')[0]
        except IndexError:
            return None

    def __str__(self) -> str:
        return str(self.name or self.id)


class Author(models.Model):
    id = models.TextField(primary_key=True)
    name = models.TextField()

    class Meta:
        ordering = ['id']
        indexes = [
            GinIndex(fields=['name'], opclasses=['gin_trgm_ops'], name='author_name_gin_trgm_idx'),
        ]

    @staticmethod
    def id_from_name(name: str) -> str:
        """Generates a normalized id value from a verbose name.

        :param name: an author's name.
        :return: a normalized id value.
        """

        item_id = name.casefold()
        item_id = unicodedata.normalize('NFKC', item_id)
        item_id = re.sub(r"'s", '', item_id)
        item_id = re.sub(r"\W+", '', item_id)
        return item_id

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalizes an author's name

        :param name: a verbose author's name.
        :return: a normalized verbose author's name.
        """

        name = unicodedata.normalize('NFKC', name)
        name = re.sub(r"\s+", ' ', name)
        return name

    @classmethod
    def fuzzy_search(cls, name: str) -> Optional[Author]:
        """Find an `Author` object using fuzzy search technics.

        :param name: a verbose tag's name.
        :return: a `Author` object or None.
        """

        try:
            return cls.objects \
                .annotate(similarity=TrigramSimilarity('name', name)) \
                .filter(similarity__gt=0.3) \
                .order_by('-similarity')[0]
        except IndexError:
            return None

    def __str__(self) -> str:
        return str(self.name or self.id)


class RecipeSearchFieldsets(models.TextChoices):
    FULL_TEXT = 'Full text'
    ESSENTIALS = 'Essentials'
    INGREDIENTS = 'Ingredients'


class RecipeQuerySet(QuerySet):
    def text_filter(
            self,
            query: str,
            *,
            fieldset: RecipeSearchFieldsets = RecipeSearchFieldsets.ESSENTIALS,
            query_type: Literal['websearch', 'plain', 'raw', 'phrase'] = 'websearch',
    ) -> RecipeQuerySet:
        """Filter recipes with Postgres Full Text Search.

        :param query: a text to be searched.
        :param fieldset: a set of fields where the query will be searched.
        :param query_type: a search query parser.
        :return: a filtered queryset.
        """
        if not query:
            return self
        tsquery = SearchQuery(query, config='english', search_type=query_type)
        if fieldset == RecipeSearchFieldsets.FULL_TEXT:
            return self.filter(_full_text_tsvector=tsquery)
        if fieldset == RecipeSearchFieldsets.ESSENTIALS:
            return self.filter(_essentials_tsvector=tsquery)
        if fieldset == RecipeSearchFieldsets.INGREDIENTS:
            return self.filter(_ingredients_tsvector=tsquery)
        raise ValueError(f"Unknown fieldset: {fieldset}")


class RecipeManager(Manager):
    def get_queryset(self) -> RecipeQuerySet:
        return RecipeQuerySet(self.model, using=self._db)

    def text_filter(
            self,
            query: str,
            *,
            fieldset: RecipeSearchFieldsets = RecipeSearchFieldsets.ESSENTIALS,
            query_type: Literal['websearch', 'plain', 'raw', 'phrase'] = 'websearch',
    ) -> RecipeQuerySet:
        return self.get_queryset().text_filter(query=query, fieldset=fieldset, query_type=query_type)

    def all(self) -> RecipeQuerySet:
        return self.get_queryset()


class Recipe(models.Model):
    class Sources(models.TextChoices):
        BON_APPETIT = 'Bon Appétit'

    id = models.TextField(primary_key=True)
    source = models.TextField(choices=Sources.choices)
    url = models.URLField(max_length=1000)
    pub_date = models.DateTimeField(null=True)
    name = models.TextField()
    title = models.TextField()
    description = models.TextField()
    short_description = models.TextField()
    rating = models.FloatField()
    reviews_count = models.IntegerField()
    wma_count = models.IntegerField()
    photo_url = models.URLField(null=True, max_length=1000)
    ingredient_groups = models.JSONField()
    tags = models.ManyToManyField(Tag, related_name='recipes')
    authors = models.ManyToManyField(Author, related_name='recipes')

    # Includes: 'name', 'title', 'description', 'short_description', 'ingredient_groups'
    _full_text_tsvector = SearchVectorField()
    # Includes: 'title', 'short_description'
    _essentials_tsvector = SearchVectorField()
    # Includes: 'ingredient_groups'
    _ingredients_tsvector = SearchVectorField()

    objects = RecipeManager()

    class Meta:
        ordering = [F('pub_date').desc(nulls_last=True)]
        get_latest_by = 'pub_date'
        indexes = [
            models.Index(fields=['pub_date'], name='recipe_pub_date_idx'),
            GinIndex(fields=['_full_text_tsvector'], name='recipe_full_text_tsv_idx'),
            GinIndex(fields=['_essentials_tsvector'], name='recipe_essentials_tsv_idx'),
            GinIndex(fields=['_ingredients_tsvector'], name='recipe_ingredients_tsv_idx'),
        ]

    def save(
            self,
            force_insert: bool = False,
            force_update: bool = False,
            using: Optional[str] = None,
            update_fields: Optional[Iterable[str]] = None,
    ) -> None:
        # Updating tsvector fields manually as Django is lacking support for Postgres generated columns
        super().save(force_insert, force_update, using, update_fields)
        self._full_text_tsvector = SearchVector(
            'name', 'title', 'description', 'short_description', 'ingredient_groups',
            config='english',
        )
        self._essentials_tsvector = SearchVector(
            'title', 'short_description',
            config='english',
        )
        self._ingredients_tsvector = SearchVector(
            'ingredient_groups',
            config='english',
        )
        update_fields = ('_full_text_tsvector', '_essentials_tsvector', '_ingredients_tsvector')
        super().save(force_insert, force_update, using, update_fields)

    def __str__(self) -> str:
        return str(self.title)
