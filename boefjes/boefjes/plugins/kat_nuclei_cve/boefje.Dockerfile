FROM golang:1.24-alpine AS build
ARG NUCLEI_VERSION=v3.2.4

RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@${NUCLEI_VERSION}

FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/nuclei:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
COPY --from=build /go/bin/nuclei /usr/local/bin/
COPY ./boefjes/plugins/kat_nuclei_cve ./kat_nuclei_cve
