from django.contrib import admin

from telegram import models

admin.site.register(models.Chat)
admin.site.register(models.Subscription)
