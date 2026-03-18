FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/ssl-certificates:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
RUN apt-get update;\
    apt-get install -y --no-install-recommends wget build-essential libfindbin-libs-perl; \
    wget -O - https://github.com/openssl/openssl/releases/download/openssl-3.5.0/openssl-3.5.0.tar.gz | tar zxf -; \
    cd openssl-3.5.0; \
    ./config --prefix=/usr/local
USER nonroot

COPY ./boefjes/plugins/kat_ssl_certificates ./kat_ssl_certificates
