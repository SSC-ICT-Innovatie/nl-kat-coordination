FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]
ARG NODE_VERSION=20.11.1

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates xz-utils
RUN curl -fsSL https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz \
 | tar -xJ -C /usr/local --strip-components=1

RUN apt-get update && apt-get -y upgrade && \
    apt-get install -y --no-install-recommends \
    gettext devscripts debhelper equivs \
    python3-setuptools python3-pip python3-dev \
    libssl-dev dh-virtualenv libpq-dev libssl-dev \
    build-essential nodejs git openssh-client \
    libfreetype-dev zlib1g-dev libjpeg-dev libffi-dev
RUN corepack enable
