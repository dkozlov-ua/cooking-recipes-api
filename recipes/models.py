from __future__ import annotations

import re
import unicodedata
from typing import Optional, Literal

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField, SearchQuery, SearchVector, TrigramSimilarity
from django.db import models
from django.db.models import F, QuerySet


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
        name = re.sub(r"\s+", ' ', name)
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


class Recipe(models.Model):
    id = models.TextField(primary_key=True)
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
    full_text_tsvector = SearchVectorField()
    # Includes: 'title', 'short_description'
    essentials_tsvector = SearchVectorField()

    class Meta:
        ordering = [F('pub_date').desc(nulls_last=True)]
        get_latest_by = 'pub_date'
        indexes = [
            models.Index(fields=['pub_date']),
            GinIndex(fields=['full_text_tsvector']),
            GinIndex(fields=['essentials_tsvector']),
        ]

    def update_tsvector_fields(self) -> None:
        """Sets values for tsvector fields for the recipe.

        Object must already be in the database.
        Does not save changes to the database (need to call save() after update_tsvector_fields()).
        """

        self.full_text_tsvector = SearchVector(
            'name', 'title', 'description', 'short_description', 'ingredient_groups',
            config='english',
        )
        self.essentials_tsvector = SearchVector(
            'title', 'short_description',
            config='english',
        )

    @classmethod
    def text_search(
            cls,
            query: str,
            fieldset: Literal['full_text', 'essentials'] = 'essentials',
            queryset: Optional[QuerySet[Recipe]] = None,
    ) -> QuerySet[Recipe]:
        """Search recipes among provided queryset or all recipes with Postgres FTS.

        :param query: a text to be searched.
        :param fieldset: a set of fields where the query will be searched.
        :param queryset: an initial queryset.
        :return: a filtered queryset.
        """

        # Search among all recipes if the queryset hasn't been provided
        if queryset is None:
            queryset = cls.objects.all()
        tsquery = SearchQuery(query, config='english', search_type='websearch')
        if fieldset == 'full_text':
            queryset = queryset.filter(main_tsvector=tsquery)
        elif fieldset == 'essentials':
            queryset = queryset.filter(essentials_tsvector=tsquery)
        else:
            raise ValueError(f"Unknown fieldset: {fieldset}")
        return queryset

    def __str__(self) -> str:
        return str(self.title)
