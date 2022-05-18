#!/usr/bin/env bash

ACTION=$1

if [[ $ACTION == "start" ]]
then
     docker build --tag recipes:latest . \
  && docker-compose --env-file env.dev run --rm --entrypoint "./manage.py makemigrations" api \
  && docker-compose --env-file env.dev run --rm --entrypoint "./manage.py migrate" api \
  && docker-compose --env-file env.dev up --remove-orphans
else
     docker-compose --env-file env.dev down --remove-orphans
fi
