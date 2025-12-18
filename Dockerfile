# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14
FROM node:24-trixie AS node_builder

WORKDIR /app

COPY package.json yarn.lock .
COPY assets assets
COPY components components

RUN yarn --ignore-engines && yarn build


FROM golang:1.24-alpine AS entrypoint_builder

WORKDIR /app
COPY plugins/plugins/entrypoint.go .
RUN go build -o entrypoint entrypoint.go


FROM python:$PYTHON_VERSION-trixie AS dev

ENV GRANIAN_WORKERS=2
ENV GRANIAN_THREADS=4
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/usr/local

ARG USER_UID=1000
ARG USER_GID=1000

ENTRYPOINT ["/app/openkat/entrypoint.sh"]

RUN groupadd --gid "$USER_GID" openkat
RUN adduser --disabled-password --gecos '' --uid "$USER_UID" --gid "$USER_GID" openkat

WORKDIR /app/openkat

RUN --mount=type=cache,target=/var/cache/apt \
  apt-get update \
  && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends gettext=0.23.1-2 netcat-openbsd \
  && rm -rf /var/lib/apt/lists/*

COPY --from=entrypoint_builder /app/entrypoint /plugin/
VOLUME /plugin

# Build with "docker build --build-arg ENVIRONMENT=dev" to install dev dependencies
ARG ENVIRONMENT

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    if [ "$ENVIRONMENT" = "dev" ]; then uv sync --locked --dev; else uv sync --locked --no-dev; fi

COPY . .

FROM dev

# These files need to be available when we run collectstatic
COPY --link --from=node_builder /app/assets/dist assets/dist

# The secret key isn't used by the commands, but Django won't work without it

RUN export SECRET_KEY="secret" && python manage.py collectstatic -l && python manage.py compilemessages

RUN mkdir media && chown -R openkat media
RUN rm -rf tests *.lock package.json openkat.egg-info setup.py pyproject.toml

USER openkat

CMD ["granian", "--interface", "wsgi", "openkat.wsgi:application", "--host", "0.0.0.0"]
