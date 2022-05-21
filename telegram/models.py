from django.db import models

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
