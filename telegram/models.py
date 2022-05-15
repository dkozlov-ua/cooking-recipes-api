from django.db import models
from django.db.models.functions import Coalesce
from django.db.models.query import Q

import recipes.models


class Chat(models.Model):
    id = models.BigIntegerField(primary_key=True)
    username = models.TextField()
    first_name = models.TextField()
    last_name = models.TextField()
    last_seen_date = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"@{self.username} ({self.first_name} {self.last_name})"


class Subscription(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    tag = models.ForeignKey(recipes.models.Tag, on_delete=models.CASCADE, null=True)
    author = models.ForeignKey(recipes.models.Author, on_delete=models.CASCADE, null=True)
    last_recipe_pub_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Coalesce('tag', 'author'),
                Coalesce('author', 'tag'),
                'chat',
                name='unique_subscription',
            ),
            models.CheckConstraint(
                check=Q(tag__isnull=False) | Q(author__isnull=False),
                name='tag_or_author_not_null',
            ),
        ]

    def __str__(self) -> str:
        if self.tag:
            return f"{self.chat_id} -> #{self.tag_id}"
        return f"{self.chat_id} -> {self.author_id}"
