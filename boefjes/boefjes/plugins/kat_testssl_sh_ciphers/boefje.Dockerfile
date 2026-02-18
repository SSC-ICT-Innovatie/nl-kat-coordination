FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/testssl-sh-ciphers:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
RUN apt-get update && apt-get install -y --no-install-recommends bsdmainutils procps git dnsutils
RUN git clone --depth 1 https://github.com/testssl/testssl.sh.git --branch v3.2.1 testssl
RUN ln -s /app/boefje/testssl/testssl.sh /usr/local/bin/testssl.sh
USER nonroot

COPY ./boefjes/plugins/kat_testssl_sh_ciphers ./kat_testssl_sh_ciphers
