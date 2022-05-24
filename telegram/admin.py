from django.contrib import admin

from telegram import models


class TagSubscriptionAdminInline(admin.TabularInline):
    model = models.TagSubscription
    fields = ['tag', 'last_recipe_date']
    readonly_fields = ['tag', 'last_recipe_date']
    extra = 0


class AuthorSubscriptionAdminInline(admin.TabularInline):
    model = models.AuthorSubscription
    fields = ['author', 'last_recipe_date']
    readonly_fields = ['author', 'last_recipe_date']
    extra = 0


@admin.register(models.Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'first_name', 'last_name', 'last_seen_date']
    fields = ['id', 'username', ('first_name', 'last_name'), 'last_seen_date']
    sortable_by = ['id', 'username', 'last_seen_date']
    readonly_fields = ['last_seen_date']
    view_on_site = False
    inlines = [TagSubscriptionAdminInline, AuthorSubscriptionAdminInline]


@admin.register(models.TagSubscription)
class TagSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['chat', 'tag', 'last_recipe_date']
    list_filter = ['chat', 'tag']
    list_select_related = True
    readonly_fields = ['chat', 'tag']
    view_on_site = False


@admin.register(models.AuthorSubscription)
class AuthorSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['chat', 'author', 'last_recipe_date']
    list_filter = ('chat', "author")
    list_select_related = True
    readonly_fields = ['chat', 'author']
    view_on_site = False
