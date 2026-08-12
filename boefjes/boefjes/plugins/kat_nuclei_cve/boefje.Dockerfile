FROM golang:1.25-alpine AS build
ARG NUCLEI_VERSION=v3.9.0
# Templates are pinned and baked into the image. Nuclei's runtime
# `-update-templates` exits 0 without installing anything when the download
# fails, leaving a scan with no templates and no error to explain it. Pinning
# also keeps builds reproducible and lets the boefje run without internet
# access to GitHub.
ARG NUCLEI_TEMPLATES_VERSION=v10.4.7

RUN apk add --no-cache git
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@${NUCLEI_VERSION}
RUN git clone --depth 1 --branch ${NUCLEI_TEMPLATES_VERSION} \
    https://github.com/projectdiscovery/nuclei-templates.git /nuclei-templates \
 && rm -rf /nuclei-templates/.git

FROM openkat/boefje-base:latest

ARG OCI_IMAGE=docker.underdark.nl/librekat/openkat-nuclei:latest
ENV OCI_IMAGE=$OCI_IMAGE

USER root
COPY --from=build /go/bin/nuclei /usr/local/bin/
COPY --from=build /nuclei-templates /root/nuclei-templates
COPY ./boefjes/plugins/kat_nuclei_cve ./kat_nuclei_cve
