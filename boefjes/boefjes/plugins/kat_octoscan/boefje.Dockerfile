FROM openkat/boefje-base:latest

COPY --from=golang:1.24 /usr/local/go/ /usr/local/go/

ARG OCI_IMAGE=ghcr.io/minvws/openkat/octoscan:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
RUN apt-get update && apt-get install -y git

RUN git clone https://github.com/synacktiv/octoscan /octoscan && \
    cd /octoscan && \
    /usr/local/go/bin/go mod tidy && \
    /usr/local/go/bin/go build

COPY ./boefjes/plugins/kat_octoscan ./kat_octoscan
