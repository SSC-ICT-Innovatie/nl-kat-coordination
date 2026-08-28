ARG PYTHON_VERSION=3.13
FROM python:$PYTHON_VERSION-bookworm AS dev

EXPOSE 8000

ARG USER_UID=1000
ARG USER_GID=1000

WORKDIR /app/octopoes

ENTRYPOINT ["/app/octopoes/entrypoint.sh"]

RUN groupadd --gid "$USER_GID" octopoes
RUN adduser --disabled-password --gecos '' --uid "$USER_UID" --gid "$USER_GID" octopoes

ENV PATH=/home/octopoes/.local/bin:${PATH}

# Build with "docker build --build-arg ENVIRONMENT=dev" to install dev
# dependencies
ARG ENVIRONMENT

COPY requirements.txt requirements-dev.txt ./
RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$ENVIRONMENT" = "dev" ]; then pip install -r requirements-dev.txt; fi

USER octopoes

FROM dev

COPY . .

CMD ["uvicorn", "octopoes.api.api:app", "--host", "0.0.0.0", "--port", "8000"]
