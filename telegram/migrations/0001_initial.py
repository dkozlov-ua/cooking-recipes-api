# Generated by Django 4.0.4 on 2022-05-15 16:19

import django.db.models.functions.comparison
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('recipes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Chat',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('username', models.TextField()),
                ('first_name', models.TextField()),
                ('last_name', models.TextField()),
                ('last_seen_date', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_recipe_pub_date', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='recipes.author')),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='telegram.chat')),
                ('tag', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='recipes.tag')),
            ],
        ),
        migrations.AddConstraint(
            model_name='subscription',
            constraint=models.UniqueConstraint(django.db.models.functions.comparison.Coalesce('tag', 'author'), django.db.models.functions.comparison.Coalesce('author', 'tag'), django.db.models.expressions.F('chat'), name='unique_subscription'),
        ),
        migrations.AddConstraint(
            model_name='subscription',
            constraint=models.CheckConstraint(check=models.Q(('tag__isnull', False), ('author__isnull', False), _connector='OR'), name='tag_or_author_not_null'),
        ),
    ]
