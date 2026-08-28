ARG PYTHON_VERSION=3.13
FROM python:$PYTHON_VERSION-bookworm AS dev

EXPOSE 8000

ARG USER_UID=1000
ARG USER_GID=1000

ENTRYPOINT ["/app/scheduler/entrypoint.sh"]

RUN groupadd --gid "$USER_GID" scheduler
RUN adduser --disabled-password --gecos '' --uid "$USER_UID" --gid "$USER_GID" scheduler

WORKDIR /app/scheduler
ENV PATH=/home/scheduler/.local/bin:${PATH}

# Build with "docker build --build-arg ENVIRONMENT=dev" to install dev
# dependencies
ARG ENVIRONMENT

COPY requirements.txt requirements-dev.txt ./
RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$ENVIRONMENT" = "dev" ]; then pip install -r requirements-dev.txt; fi

USER scheduler

CMD ["python", "-m", "scheduler"]

FROM dev

COPY . /app/scheduler
