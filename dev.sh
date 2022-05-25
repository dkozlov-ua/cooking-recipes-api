#!/usr/bin/env bash

ACTION=$1

if   [[ $ACTION == "makemigrations" ]]; then
     docker build --tag recipes:latest . \
  && docker-compose --env-file env.dev run --rm --entrypoint "./manage.py makemigrations" api
elif [[ $ACTION == "migrate" ]]; then
     docker build --tag recipes:latest . \
  && docker-compose --env-file env.dev run --rm --entrypoint "./manage.py migrate" api
elif [[ $ACTION == "start" ]]; then
     docker build --tag recipes:latest . \
  && docker-compose --env-file env.dev up --remove-orphans
elif [[ $ACTION == "stop" ]]; then
     docker-compose --env-file env.dev down --remove-orphans
else
  exit 2
fi
