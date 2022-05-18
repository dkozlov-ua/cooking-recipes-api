from django.contrib import admin

from backend.utils import pretty_json
from recipes import models


@admin.register(models.Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['title', 'short_description', 'pub_date', 'reviews_count', 'rating']
    fieldsets = [
        (None, {
            'fields': ['id', 'url', 'photo_url', 'pub_date', 'name', 'title'],
        }),
        ('Recipe', {
            'fields': ['description', 'short_description', 'ingredient_groups', 'ingredient_groups_pretty'],
        }),
        ('Rating', {
            'fields': [('rating', 'reviews_count', 'wma_count')],
        }),
        ('Search', {
            'fields': [('tags', 'authors')],
        }),
    ]
    filter_horizontal = ['tags', 'authors']
    readonly_fields = ['ingredient_groups_pretty']

    date_hierarchy = 'pub_date'
    sortable_by = ['pub_date', 'reviews_count', 'rating']

    view_on_site = False

    @staticmethod
    @admin.display(description='Ingredient groups (formatted)')
    def ingredient_groups_pretty(obj: models.Recipe) -> str:
        return pretty_json(obj.ingredient_groups)


@admin.register(models.Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['__str__']
    view_on_site = False


@admin.register(models.Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['__str__']
    view_on_site = False
