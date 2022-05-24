from rest_framework import serializers

from recipes import models


class RecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Recipe
        fields = [
            'id',
            'url',
            'pub_date',
            'name', 'title',
            'description',
            'short_description',
            'rating',
            'reviews_count',
            'wma_count',
            'photo_url',
            'ingredient_groups',
            'tags',
            'authors',
        ]
