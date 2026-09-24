# PLAYWRIGHT_VERSION pins the Playwright npm package and, via `playwright install`
# below, the browser it downloads. The base image is pinned by tag + digest so it
# is immutable and Dependabot-trackable (a plain tag can't be, see #3261). The
# digest is authoritative (Docker ignores the tag when a digest is present), so on
# a version bump update the base tag, the digest and PLAYWRIGHT_VERSION together.
ARG PLAYWRIGHT_VERSION=1.63.0
FROM mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27

# Redeclare so the RUN below (a new build stage scope) can use it.
ARG PLAYWRIGHT_VERSION

# Install browsers into the path the runtime reads, not root's cache. Set before
# `playwright install` so a bumped PLAYWRIGHT_VERSION downloads the matching
# browser where capture actually looks for it, independent of what the base baked.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common &&  \
    add-apt-repository ppa:deadsnakes/ppa -y &&  \
    apt-get update &&  \
    apt-get install -y --no-install-recommends python3.13 python3.13-venv && \
    python3.13 -m ensurepip --upgrade && \
    # Install the pinned Playwright and let IT fetch the exactly-matching browser.
    # Never use `npx playwright` at runtime: with no local package installed it
    # fetches the LATEST Playwright, which then wants a browser revision the image
    # never baked, so every capture fails on the next Playwright release (#3916).
    npm install -g "playwright@${PLAYWRIGHT_VERSION}" && \
    playwright install --with-deps chromium && \
    # Build-time guardrail (this image is built in CI): fail the build if the
    # installed Playwright is not the pinned version. -F: match a fixed string.
    playwright --version | grep -qF "Version ${PLAYWRIGHT_VERSION}" && \
    # Immutability (#5440): remove every package manager so nothing inside the
    # container can fetch or upgrade code at runtime — `npx playwright` pulling
    # the latest unpinned release is exactly how #3916 broke. The boefje only
    # needs `node` (playwright's shebang); keep /usr/lib/node_modules/playwright.
    rm -f /usr/bin/npm /usr/bin/npx /usr/bin/yarn /usr/bin/yarnpkg /usr/bin/corepack && \
    rm -rf /usr/lib/node_modules/npm /usr/lib/node_modules/yarn /usr/lib/node_modules/corepack /root/.npm && \
    # The base image ships /ms-playwright world-writable so any user can install
    # browsers — strip the write bits so the nonroot runtime cannot download or
    # replace browser binaries either.
    chmod -R a-w /ms-playwright

ARG BOEFJES_API=http://boefje:8000
ENV BOEFJES_API=$BOEFJES_API
ENV PYTHONPATH=/app/boefje:/app

WORKDIR /app/boefje
RUN adduser --disabled-password --gecos '' nonroot
# Pinned to the versions boefjes/uv.lock resolves so rebuilds stay reproducible
# (#5440); bump them together with the lockfile.
RUN --mount=type=cache,target=/root/.cache pip3 install "pip==25.2" &&  \
    pip3 install "httpx==0.28.1" "structlog==25.5.0" "pydantic==2.13.0" "jsonschema==4.26.0" "croniter==6.2.2" "click==8.3.2"

USER nonroot

# Regression guard for #3916: launch the pinned browser exactly as the boefje
# runs it (as nonroot, from /ms-playwright) and take a real screenshot. A version
# drift, a browser installed to the wrong path, or a sandbox/permission problem
# fails the image build here instead of every capture at runtime. about:blank
# needs no network. The webpage-capture image is built in containerized_boefjes,
# so this runs in CI (its pull_request paths include this plugin).
RUN playwright screenshot about:blank /tmp/smoke.png && rm -f /tmp/smoke.png

COPY ./boefjes/worker ./worker
COPY ./boefjes/logging.json logging.json

ENTRYPOINT ["/usr/bin/python3.13", "-m", "worker"]
CMD []

ARG OCI_IMAGE=docker.underdark.nl/librekat/openkat-webpage-capture:latest
ENV OCI_IMAGE=$OCI_IMAGE

COPY ./boefjes/plugins/kat_webpage_capture ./kat_webpage_capture
