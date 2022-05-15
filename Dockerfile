FROM python:3-alpine

RUN apk add bash

WORKDIR /usr/src/app

# install python modules
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -U -r /tmp/requirements.txt

# copy application files
COPY . .
ENV DJANGO_SETTINGS_MODULE=backend.settings
