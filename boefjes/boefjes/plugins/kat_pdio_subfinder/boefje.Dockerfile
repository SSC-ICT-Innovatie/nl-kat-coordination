FROM golang:1.24-alpine AS build
ARG SUBFINDER_VERSION=v2.6.6

RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@${SUBFINDER_VERSION}

FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/pdio-subfinder:latest
ENV OCI_IMAGE=$OCI_IMAGE

COPY --from=build /go/bin/subfinder /usr/local/bin/

COPY ./boefjes/plugins/kat_pdio_subfinder ./kat_pdio_subfinder
