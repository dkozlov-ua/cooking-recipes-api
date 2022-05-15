from django.contrib import admin

from recipes import models

admin.site.register(models.Recipe)
admin.site.register(models.Tag)
admin.site.register(models.Author)
