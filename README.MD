![Lint status](https://github.com/dkozlov-ua/cooking-recipes/actions/workflows/lint.yml/badge.svg?branch=master)
![Build status](https://github.com/dkozlov-ua/cooking-recipes/actions/workflows/build.yml/badge.svg?branch=master)

# <p align="center"> Cooking Recipes API
## Getting Started

This project allows you to deploy an API to a database of cooking recipes.
Additionally, it contains a scraper to fill the database and a Telegram bot
to access recipes and updates via the user-friendly interface.

Bot demo available here: [@bonappetit_recipes_bot](https://t.me/bonappetit_recipes_bot)

## Local deployment
### Configure Telegram bot
```shell
export TELEGRAM_BOT_ENABLED="1"
export TELEGRAM_BOT_TOKEN="XXXXXX"
```
or set values in `env.dev` file.

### Migrations
```shell
bash dev.sh stop makemigrations
bash dev.sh migrate
```

### Start
```shell
bash dev.sh start
```
Check Django admin at [http://localhost:8080/admin](http://localhost:8080/admin).

### Manage
```shell
bash manage.sh createsuperuser <USERNAME>
bash manage.sh drf_create_token <USERNAME>
```

### Stop
```shell
bash dev.sh stop
```

### Lint
```shell
pylint --django-settings-module=backend.settings --verbose -j0 backend recipes telegram
mypy backend recipes telegram
```

### Start scrapper
```shell
export DJANGO_REST_TOKEN="<DJANGO_REST_TOKEN>"
curl --location --request POST \
  "http://localhost:8080/recipes/scrape/?from_date=2020-01-01" \
  --header "Authorization: Bearer ${DJANGO_REST_TOKEN}"
```
