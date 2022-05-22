from typing import List

from django.db import models
from django.db.models import QuerySet

import recipes.models


class Chat(models.Model):
    id = models.BigIntegerField(primary_key=True)
    username = models.TextField()
    first_name = models.TextField()
    last_name = models.TextField()
    last_seen_date = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"@{self.username} ({self.first_name} {self.last_name})"


class TagSubscription(models.Model):
    chat = models.ForeignKey(Chat, related_name='tag_subscriptions', on_delete=models.CASCADE)
    tag = models.ForeignKey(recipes.models.Tag, related_name='tag_subscriptions', on_delete=models.CASCADE)
    last_recipe_date = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('chat', 'tag'), name='unique_tag_subscription'),
        ]

    def __str__(self) -> str:
        return f"{self.chat_id} -> #{self.tag_id}"


class AuthorSubscription(models.Model):
    chat = models.ForeignKey(Chat, related_name='author_subscriptions', on_delete=models.CASCADE)
    author = models.ForeignKey(recipes.models.Author, related_name='author_subscriptions', on_delete=models.CASCADE)
    last_recipe_date = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('chat', 'author'), name='unique_author_subscription'),
        ]

    def __str__(self) -> str:
        return f"{self.chat_id} -> {self.author_id}"


class SearchRequestMessage(models.Model):
    message_id = models.BigIntegerField()
    chat = models.ForeignKey(Chat, related_name='search_messages', on_delete=models.CASCADE)
    query = models.TextField()
    page_n = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def get_queryset(self) -> QuerySet[recipes.models.Recipe]:
        return recipes.models.Recipe.text_search(self.query).order_by('-reviews_count', '-rating', '-pub_date')

    def get_page(self, page_n: int, page_size: int) -> List[recipes.models.Recipe]:
        start_idx = page_size * page_n
        end_idx = page_size * (page_n + 1)
        return list(self.get_queryset()[start_idx:end_idx])

    def current_page(self, page_size: int) -> List[recipes.models.Recipe]:
        return self.get_page(self.page_n, page_size)

    def previous_page(self, page_size: int) -> List[recipes.models.Recipe]:
        if self.page_n == 0:
            return []
        page = self.get_page(self.page_n - 1, page_size)
        if page:
            self.page_n -= 1
        return page

    def next_page(self, page_size: int) -> List[recipes.models.Recipe]:
        page = self.get_page(self.page_n + 1, page_size)
        if page:
            self.page_n += 1
        return page
