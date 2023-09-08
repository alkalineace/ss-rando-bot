FROM python:3.10-alpine

WORKDIR /ss-rando-bot

RUN apk add git

COPY setup.py randobot .

RUN pip install -e .