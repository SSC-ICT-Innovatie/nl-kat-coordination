FROM python:3.13-slim AS base

ARG BOEFJES_API=http://boefje:8000
ENV BOEFJES_API=$BOEFJES_API
ENV PYTHONPATH=/app/boefje:/app

WORKDIR /app/boefje
RUN adduser --disabled-password --gecos '' nonroot

COPY ./images/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip && pip install -r requirements.txt

USER nonroot

COPY ./boefjes/worker ./worker
COPY ./boefjes/logging.json logging.json

ENTRYPOINT ["/usr/local/bin/python", "-m", "worker"]
CMD []

FROM base AS builder

ARG BOEFJE_PATH

COPY $BOEFJE_PATH/requirements.txt* .
RUN if test -f requirements.txt; then pip install -r requirements.txt; fi

COPY $BOEFJE_PATH .

FROM base
