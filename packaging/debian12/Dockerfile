FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg && mkdir -p /etc/apt/keyrings && \
    curl --proto "=https" -sL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list

RUN apt-get update && apt-get -y upgrade && \
    apt-get install -y --no-install-recommends \
    gettext devscripts debhelper equivs \
    python3-setuptools python3-pip python3-dev \
    dh-sequence-python3 pybuild-plugin-pyproject python3-poetry \
    libssl-dev dh-virtualenv libpq-dev libssl-dev \
    build-essential nodejs git openssh-client \
    libfreetype-dev zlib1g-dev libjpeg-dev libffi-dev
RUN corepack enable
