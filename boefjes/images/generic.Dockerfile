FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/generic:latest
ENV OCI_IMAGE=$OCI_IMAGE

ENV PATH=/home/nonroot/.local/bin:${PATH}

ENV OPENKAT_CACHE_PATH=/home/nonroot/openkat_cache
RUN mkdir "$OPENKAT_CACHE_PATH" && chown nonroot: "$OPENKAT_CACHE_PATH"
VOLUME /home/nonroot/openkat_cache

COPY --chown=nonroot boefjes/plugins/kat_adr_finding_types boefjes/plugins/kat_adr_finding_types
COPY --chown=nonroot boefjes/plugins/kat_binaryedge boefjes/plugins/kat_binaryedge
COPY --chown=nonroot boefjes/plugins/kat_censys boefjes/plugins/kat_censys
COPY --chown=nonroot boefjes/plugins/kat_crt_sh boefjes/plugins/kat_crt_sh
COPY --chown=nonroot boefjes/plugins/kat_cve_2023_34039 boefjes/plugins/kat_cve_2023_34039
COPY --chown=nonroot boefjes/plugins/kat_cve_2023_35078 boefjes/plugins/kat_cve_2023_35078
COPY --chown=nonroot boefjes/plugins/kat_cve_finding_types boefjes/plugins/kat_cve_finding_types
COPY --chown=nonroot boefjes/plugins/kat_cwe_finding_types boefjes/plugins/kat_cwe_finding_types
COPY --chown=nonroot boefjes/plugins/kat_dicom boefjes/plugins/kat_dicom
COPY --chown=nonroot boefjes/plugins/kat_dns boefjes/plugins/kat_dns
COPY --chown=nonroot boefjes/plugins/kat_dns_version boefjes/plugins/kat_dns_version
COPY --chown=nonroot boefjes/plugins/kat_dns_zone boefjes/plugins/kat_dns_zone
COPY --chown=nonroot boefjes/plugins/kat_external_db boefjes/plugins/kat_external_db
COPY --chown=nonroot boefjes/plugins/kat_fierce boefjes/plugins/kat_fierce
COPY --chown=nonroot boefjes/plugins/kat_green_hosting boefjes/plugins/kat_green_hosting
COPY --chown=nonroot boefjes/plugins/kat_kat_finding_types boefjes/plugins/kat_kat_finding_types
COPY --chown=nonroot boefjes/plugins/kat_leakix boefjes/plugins/kat_leakix
COPY --chown=nonroot boefjes/plugins/kat_rdns boefjes/plugins/kat_rdns
COPY --chown=nonroot boefjes/plugins/kat_retirejs_finding_types boefjes/plugins/kat_retirejs_finding_types
COPY --chown=nonroot boefjes/plugins/kat_rpki boefjes/plugins/kat_rpki
COPY --chown=nonroot boefjes/plugins/kat_security_txt_downloader boefjes/plugins/kat_security_txt_downloader
COPY --chown=nonroot boefjes/plugins/kat_service_banner boefjes/plugins/kat_service_banner
COPY --chown=nonroot boefjes/plugins/kat_shodan boefjes/plugins/kat_shodan
COPY --chown=nonroot boefjes/plugins/kat_snyk boefjes/plugins/kat_snyk
COPY --chown=nonroot boefjes/plugins/kat_snyk_finding_types boefjes/plugins/kat_snyk_finding_types
COPY --chown=nonroot boefjes/plugins/kat_webpage_analysis boefjes/plugins/kat_webpage_analysis
COPY --chown=nonroot boefjes/plugins/__init__.py boefjes/plugins/__init__.py
COPY --chown=nonroot boefjes/__init__.py boefjes/__init__.py

RUN find ./boefjes -name 'requirements.txt' -execdir sh -c "cat {} && echo" \; | sort -u > /tmp/boefjes-requirements.txt
RUN --mount=type=cache,target=/root/.cache pip install setuptools==78.1.0 && pip install -r /tmp/boefjes-requirements.txt
