ARG PYTHON_VERSION=3.13
FROM python:$PYTHON_VERSION-bookworm AS dev

EXPOSE 8000

ARG USER_UID=1000
ARG USER_GID=1000

ENTRYPOINT ["/app/bytes/entrypoint.sh"]

RUN groupadd --gid "$USER_GID" bytes
RUN adduser --disabled-password --gecos '' --uid "$USER_UID" --gid "$USER_GID" bytes

WORKDIR /app/bytes
ENV PATH=/home/bytes/.local/bin:${PATH}

ENV BYTES_DATA_DIR=/data
RUN mkdir "$BYTES_DATA_DIR" && chown bytes: "$BYTES_DATA_DIR"
VOLUME /data

# Build with "docker build --build-arg ENVIRONMENT=dev" to install dev
# dependencies
ARG ENVIRONMENT

COPY requirements.txt requirements-dev.txt ./
RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$ENVIRONMENT" = "dev" ]; then pip install -r requirements-dev.txt; fi

USER bytes

FROM dev

COPY . .

CMD ["uvicorn", "bytes.api:app", "--host", "0.0.0.0", "--port", "8000"]
