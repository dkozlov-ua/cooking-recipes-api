# Generated by Django 4.0.4 on 2022-05-28 09:45

import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import migrations


def fill_ingredients_tsvector_field(apps, schema_editor):
    Recipe = apps.get_model('recipes', 'Recipe')
    ts_vector = django.contrib.postgres.search.SearchVector(
        'ingredient_groups',
        config='english',
    )
    Recipe.objects.all().update(_ingredients_tsvector=ts_vector)


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0010_remove_recipe_recipes_rec_pub_dat_caa7fa_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipe',
            name='_ingredients_tsvector',
            field=django.contrib.postgres.search.SearchVectorField(null=True),
        ),
        migrations.RunPython(fill_ingredients_tsvector_field),
        migrations.AlterField(
            model_name='recipe',
            name='_ingredients_tsvector',
            field=django.contrib.postgres.search.SearchVectorField(),
        ),
        migrations.AddIndex(
            model_name='recipe',
            index=django.contrib.postgres.indexes.GinIndex(fields=['_ingredients_tsvector'], name='recipe_ingredients_tsv_idx'),
        ),
    ]
