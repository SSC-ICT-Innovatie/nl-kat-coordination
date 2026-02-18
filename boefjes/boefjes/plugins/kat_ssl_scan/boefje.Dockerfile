FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/ssl-scan:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
RUN apt-get update && apt-get install -y --no-install-recommends git zlib1g-dev make gcc curl unzip ;\
    git clone --depth 1 https://github.com/rbsec/sslscan.git --branch 2.2.0 && cd sslscan;\
    make static && make install
USER nonroot

COPY ./boefjes/plugins/kat_ssl_scan ./kat_ssl_scan
