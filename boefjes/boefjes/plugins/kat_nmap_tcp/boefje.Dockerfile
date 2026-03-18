FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/nmap:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
RUN apt-get update && apt-get install -y --no-install-recommends nmap

COPY ./boefjes/plugins/kat_nmap_tcp ./kat_nmap_tcp
