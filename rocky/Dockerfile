# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.13
FROM node:20-bookworm AS node_builder

WORKDIR /app

COPY rocky/package.json rocky/yarn.lock .
COPY rocky/assets assets
COPY rocky/components components

RUN yarn --ignore-engines && yarn build

FROM python:$PYTHON_VERSION-bookworm AS dev

ENV GRANIAN_WORKERS=2
ENV GRANIAN_THREADS=4

ARG USER_UID=1000
ARG USER_GID=1000

ENTRYPOINT ["/app/rocky/entrypoint.sh"]

RUN groupadd --gid "$USER_GID" rocky
RUN adduser --disabled-password --gecos '' --uid "$USER_UID" --gid "$USER_GID" rocky

WORKDIR /app/rocky

RUN --mount=type=cache,target=/var/cache/apt \
  apt-get update \
  && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends gettext netcat-openbsd \
  && rm -rf /var/lib/apt/lists/*

# Build with "docker build --build-arg ENVIRONMENT=dev" to install dev
# dependencies
ARG ENVIRONMENT

# This works around https://github.com/pypa/pip/issues/6469 by installing the git
# requirements separately
COPY rocky/requirements*.txt .
RUN --mount=type=cache,target=/root/.cache \
    pip install --upgrade pip \
    && if [ "$ENVIRONMENT" = "dev" ]; \
    then \
    grep -v git+https:// requirements-dev.txt | pip install -r /dev/stdin && \
    grep git+https:// requirements-dev.txt | pip install -r /dev/stdin ; \
    else \
    grep -v git+https:// requirements.txt | pip install -r /dev/stdin && \
    grep git+https:// requirements.txt | pip install -r /dev/stdin ; \
    fi

FROM dev

COPY octopoes/ /tmp/octopoes
RUN pip install setuptools && cd /tmp/octopoes && python setup.py bdist_wheel
RUN pip install /tmp/octopoes/dist/octopoes*.whl

COPY rocky .

# These files need to be available when we run collectstatic
COPY --link --from=node_builder /app/assets/dist assets/dist

# The secret key isn't used by the commands, but Django won't work do anything
# without it

RUN export SECRET_KEY="secret" BYTES_API="http://bytes:8000" BYTES_PASSWORD="password" \
    BYTES_USERNAME="username" KATALOGUS_API="http://katalogus:8000" \
    OCTOPOES_API="http://octopoes_api:80" SCHEDULER_API="http://scheduler:8000" \
    && python manage.py collectstatic -l && python manage.py compress && python manage.py compilemessages

USER rocky

CMD ["granian", "--interface", "wsgi", "rocky.wsgi:application", "--host", "0.0.0.0"]
