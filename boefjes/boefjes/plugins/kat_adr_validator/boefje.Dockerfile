FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/dns-sec:latest
ENV OCI_IMAGE=$OCI_IMAGE

COPY --from=registry.gitlab.com/commonground/don/adr-validator:0.2.0 /usr/local/bin/adr-validator /usr/local/bin/

COPY ./boefjes/plugins/kat_adr_validator ./kat_adr_validator
