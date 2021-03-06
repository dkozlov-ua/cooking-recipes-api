# Generated by Django 4.0.4 on 2022-05-24 08:24

import django.contrib.postgres.indexes
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0005_recipe_essentials_tsvector_and_more'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='recipe',
            name='full_text_tsvector_idx',
        ),
        migrations.RemoveIndex(
            model_name='recipe',
            name='essentials_tsvector_idx',
        ),
        migrations.AddIndex(
            model_name='recipe',
            index=django.contrib.postgres.indexes.GinIndex(fields=['full_text_tsvector'], name='recipes_rec_full_te_1f199b_gin'),
        ),
        migrations.AddIndex(
            model_name='recipe',
            index=django.contrib.postgres.indexes.GinIndex(fields=['essentials_tsvector'], name='recipes_rec_essenti_999a14_gin'),
        ),
    ]
