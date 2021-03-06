# Generated by Django 4.0.4 on 2022-05-18 18:00

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0002_alter_recipe_photo_url_alter_recipe_url'),
        ('telegram', '0003_tagsubscription_delete_subscription_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tagsubscription',
            name='chat',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tag_subscriptions', to='telegram.chat'),
        ),
        migrations.AlterField(
            model_name='tagsubscription',
            name='tag',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tag_subscriptions', to='recipes.tag'),
        ),
        migrations.CreateModel(
            name='AuthorSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_recipe_date', models.DateTimeField()),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='author_subscriptions', to='recipes.author')),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='author_subscriptions', to='telegram.chat')),
            ],
        ),
        migrations.AddConstraint(
            model_name='authorsubscription',
            constraint=models.UniqueConstraint(fields=('chat', 'author'), name='unique_author_subscription'),
        ),
    ]
