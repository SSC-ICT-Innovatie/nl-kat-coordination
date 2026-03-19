FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/export-http:latest
ENV OCI_IMAGE=$OCI_IMAGE

COPY ./boefjes/plugins/kat_export_http ./kat_export_http
