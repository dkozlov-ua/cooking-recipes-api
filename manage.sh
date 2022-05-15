#!/usr/bin/env bash

docker exec -it "${PWD##*/}_api_1" ./manage.py "${@:1}"
