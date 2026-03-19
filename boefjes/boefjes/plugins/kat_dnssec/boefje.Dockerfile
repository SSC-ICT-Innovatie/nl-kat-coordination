FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/dns-sec:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
RUN apt-get update && apt-get install -y --no-install-recommends ldnsutils dnsutils dns-root-data
USER nonroot

COPY ./boefjes/plugins/kat_dnssec ./kat_dnssec
