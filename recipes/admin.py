from typing import Tuple

from django.contrib import admin
from django.contrib.postgres.search import SearchQuery
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.safestring import SafeString, mark_safe

from recipes import models


@admin.register(models.Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['title', 'short_description', 'pub_date', 'reviews_count', 'rating']
    list_filter = ['tags', 'authors']
    search_fields = ['short_description']
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
            'fields': ['tags', 'authors'],
        }),
    ]
    filter_horizontal = ['tags', 'authors']
    readonly_fields = ['ingredient_groups_pretty']

    date_hierarchy = 'pub_date'
    sortable_by = ['pub_date', 'reviews_count', 'rating']

    view_on_site = False

    @staticmethod
    @admin.display(description='Ingredient groups (formatted)')
    def ingredient_groups_pretty(obj: models.Recipe) -> SafeString:
        """Generates HTML representation for a recipe's ingredients list.

        Works OK with Grappelli, might need correction for the vanilla Django admin widgets.

        :param obj: a target recipe.
        :return: an HTML-formatted ingredients list.
        """

        ingredients_repr = ''
        for group in obj.ingredient_groups:
            if group['title']:
                ingredients_repr += f"<b>{group['title'].capitalize()}</b></br>"
            for ingredient in group['ingredients']:
                ingredients_repr += f"&nbsp;-&nbsp;{ingredient}</br>"
            ingredients_repr += '</br>'
        # Remove dangling </br> tag if the group hasn't got a title
        ingredients_repr = ingredients_repr.removesuffix('</br>')
        return mark_safe(ingredients_repr)

    def get_search_results(self, request: HttpRequest, queryset: QuerySet, search_term: str) -> Tuple[QuerySet, bool]:
        """Performs full text search for recipes.

        :param request: an original HttpRequest object.
        :param queryset: a queryset to be filtered with full text search.
        :param search_term: a text to be searched in recipes.
        :return: a tuple containing a queryset to implement the search
                 and a boolean indicating if the results may contain duplicates.
        """
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        query = SearchQuery(search_term, config='english', search_type='websearch')
        queryset |= self.model.objects.filter(essentials_tsvector=query)
        return queryset, may_have_duplicates


@admin.register(models.Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['__str__']
    view_on_site = False


@admin.register(models.Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['__str__']
    view_on_site = False
