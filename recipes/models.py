import re

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import F


class Tag(models.Model):
    id = models.TextField(primary_key=True)
    name = models.TextField(null=True)

    class Meta:
        ordering = ['id']

    @staticmethod
    def id_from_name(name: str) -> str:
        return re.sub(r"[^\w]+", '', name).casefold()

    def __str__(self) -> str:
        return str(self.name or self.id)


class Author(models.Model):
    id = models.TextField(primary_key=True)
    name = models.TextField(null=True)

    class Meta:
        ordering = ['id']

    @staticmethod
    def id_from_name(name: str) -> str:
        return re.sub(r"[^\w]+", '', name).casefold()

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

    main_tsvector = SearchVectorField()

    class Meta:
        ordering = [F('pub_date').desc(nulls_last=True)]
        get_latest_by = 'pub_date'
        indexes = [
            models.Index(fields=['pub_date']),
            GinIndex('main_tsvector', name='main_tsvector_idx'),
        ]

    def __str__(self) -> str:
        return str(self.title)
