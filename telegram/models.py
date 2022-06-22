from __future__ import annotations

from typing import List

from django.db import models
from telebot.types import Message

from recipes.models import Recipe, RecipeQuerySet, RecipeSearchFieldsets, Tag, Author


class Chat(models.Model):
    id = models.BigIntegerField(primary_key=True)
    username = models.TextField(null=True)
    first_name = models.TextField(null=True)
    last_name = models.TextField(null=True)
    last_seen_date = models.DateTimeField(auto_now=True)
    is_admin = models.BooleanField(default=False)
    liked_recipes = models.ManyToManyField(Recipe)
    blocked_tags = models.ManyToManyField(Tag)
    blocked_authors = models.ManyToManyField(Author)

    @classmethod
    def update_from_message(cls, message: Message) -> Chat:
        chat, _ = cls.objects.get_or_create(id=message.chat.id)
        chat.username = message.chat.username or None
        chat.first_name = message.chat.first_name or None
        chat.last_name = message.chat.last_name or None
        chat.save()
        return chat

    def __str__(self) -> str:
        return f"@{self.username} ({self.first_name} {self.last_name})"


class TagSubscription(models.Model):
    chat = models.ForeignKey(Chat, related_name='tag_subscriptions', on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, related_name='tag_subscriptions', on_delete=models.CASCADE)
    last_recipe_date = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('chat', 'tag'), name='unique_tag_subscription'),
        ]

    def __str__(self) -> str:
        return f"{self.chat_id} -> #{self.tag_id}"


class AuthorSubscription(models.Model):
    chat = models.ForeignKey(Chat, related_name='author_subscriptions', on_delete=models.CASCADE)
    author = models.ForeignKey(Author, related_name='author_subscriptions', on_delete=models.CASCADE)
    last_recipe_date = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('chat', 'author'), name='unique_author_subscription'),
        ]

    def __str__(self) -> str:
        return f"{self.chat_id} -> {self.author_id}"


class ListMessage(models.Model):
    message_id = models.BigIntegerField()
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    page_n = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def get_queryset(self) -> RecipeQuerySet:
        raise NotImplementedError

    def get_page(self, page_n: int, page_size: int) -> List[Recipe]:
        start_idx = page_size * page_n
        end_idx = page_size * (page_n + 1)
        return list(self.get_queryset()[start_idx:end_idx])

    def current_page(self, page_size: int) -> List[Recipe]:
        return self.get_page(self.page_n, page_size)

    def switch_to_previous_page(self, page_size: int) -> List[Recipe]:
        if self.page_n == 0:
            return []
        page = self.get_page(self.page_n - 1, page_size)
        if page:
            self.page_n -= 1
        return page

    def switch_to_next_page(self, page_size: int) -> List[Recipe]:
        page = self.get_page(self.page_n + 1, page_size)
        if page:
            self.page_n += 1
        return page

    def total_results_count(self) -> int:
        return self.get_queryset().count()


class SearchListMessage(ListMessage):
    recipe_query = models.TextField()
    ingredients_query = models.TextField()

    def get_queryset(self) -> RecipeQuerySet:
        qs = Recipe.objects.all()
        if self.recipe_query:
            qs = qs.text_filter(self.recipe_query, fieldset=RecipeSearchFieldsets.ESSENTIALS)
        if self.ingredients_query:
            qs = qs.text_filter(self.ingredients_query, fieldset=RecipeSearchFieldsets.INGREDIENTS)
        return (
            qs
            .exclude(tags=self.chat.blocked_tags)
            .exclude(authors=self.chat.blocked_authors)
            .prefetch_related()
            .order_by('-reviews_count', '-rating', '-pub_date')
        )


class LikedListMessage(ListMessage):
    def get_queryset(self) -> RecipeQuerySet:
        return Recipe.objects.all().filter().prefetch_related().order_by('title')
