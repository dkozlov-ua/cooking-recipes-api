# Generated by Django 4.0.4 on 2022-05-21 15:27

import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.expressions
from django.db import migrations


def fill_essentials_tsvector_field(apps, schema_editor):
    Recipe = apps.get_model('recipes', 'Recipe')
    ts_vector = django.contrib.postgres.search.SearchVector(
        'title', 'short_description',
        config='english',
    )
    Recipe.objects.all().update(essentials_tsvector=ts_vector)


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0004_remove_recipe_main_tsvector_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipe',
            name='essentials_tsvector',
            field=django.contrib.postgres.search.SearchVectorField(null=True),
        ),
        migrations.RunPython(fill_essentials_tsvector_field),
        migrations.AlterField(
            model_name='recipe',
            name='essentials_tsvector',
            field=django.contrib.postgres.search.SearchVectorField(),
        ),
        migrations.AddIndex(
            model_name='recipe',
            index=django.contrib.postgres.indexes.GinIndex(django.db.models.expressions.F('essentials_tsvector'), name='essentials_tsvector_idx'),
        ),
    ]
