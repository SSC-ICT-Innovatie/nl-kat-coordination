FROM mcr.microsoft.com/playwright:v1.53.0-noble

RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common &&  \
    add-apt-repository ppa:deadsnakes/ppa -y &&  \
    apt-get update &&  \
    apt-get install -y --no-install-recommends python3.13 python3.13-venv && \
    python3.13 -m ensurepip --upgrade && \
    npx playwright install --with-deps chromium

ARG BOEFJES_API=http://boefje:8000
ENV BOEFJES_API=$BOEFJES_API
ENV PYTHONPATH=/app/boefje:/app

WORKDIR /app/boefje
RUN adduser --disabled-password --gecos '' nonroot
RUN --mount=type=cache,target=/root/.cache pip3 install --upgrade pip &&  \
    pip3 install httpx structlog pydantic jsonschema croniter click

USER nonroot

COPY ./boefjes/worker ./worker
COPY ./boefjes/logging.json logging.json

ENTRYPOINT ["/usr/bin/python3.13", "-m", "worker"]
CMD []

ARG OCI_IMAGE=ghcr.io/minvws/openkat/webpage-capture:latest
ENV OCI_IMAGE=$OCI_IMAGE
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY ./boefjes/plugins/kat_webpage_capture ./kat_webpage_capture
