import re

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
    url = models.URLField()
    pub_date = models.DateTimeField(null=True)
    name = models.TextField()
    title = models.TextField()
    description = models.TextField()
    short_description = models.TextField()
    rating = models.FloatField()
    reviews_count = models.IntegerField()
    wma_count = models.IntegerField()
    photo_url = models.URLField(null=True)
    ingredient_groups = models.JSONField()
    tags = models.ManyToManyField(Tag, related_name='recipes')
    authors = models.ManyToManyField(Author, related_name='recipes')

    class Meta:
        ordering = [F('pub_date').desc(nulls_last=True)]
        get_latest_by = 'pub_date'
        indexes = [
            models.Index(fields=['pub_date']),
        ]

    def __str__(self) -> str:
        return str(self.title)
