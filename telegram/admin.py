from django.contrib import admin

from telegram import models


class SubscriptionAdminInline(admin.TabularInline):
    model = models.Subscription
    fields = ['title', 'last_recipe_pub_date']
    readonly_fields = ['title', 'last_recipe_pub_date']
    extra = 0

    @staticmethod
    @admin.display(description='Title')
    def title(obj: models.Subscription) -> str:
        return str(obj)


@admin.register(models.Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'first_name', 'last_name', 'last_seen_date']
    fields = ['id', 'username', ('first_name', 'last_name'), 'last_seen_date']
    sortable_by = 'id'
    readonly_fields = ['last_seen_date']
    view_on_site = False
    inlines = [SubscriptionAdminInline]


@admin.register(models.Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'last_recipe_pub_date']
    list_select_related = True
    readonly_fields = ['chat', 'tag', 'author']
    view_on_site = False
