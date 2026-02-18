FROM openkat/boefje-base:latest

ARG OCI_IMAGE=ghcr.io/minvws/openkat/masscan:latest
ENV OCI_IMAGE=$OCI_IMAGE

# Packages:
# git: get masscan source
# libpcap(-dev): run masscan
# libcap: set cap_net_raw permission for user nonroot
USER root

RUN apt-get update && apt-get install -y --no-install-recommends git libpcap-dev libcap2-bin make gcc

# Version pinning on specific commit. Tag in boefje.py may need an update when updating this hash.
RUN mkdir masscan \
    && cd masscan \
    && git init \
    && git remote add origin https://github.com/robertdavidgraham/masscan.git \
    && git fetch --dept 1 origin 9065684c52682d3e12a35559ef72cd0f07838bff \
    && git checkout FETCH_HEAD \
    && make -j \
    && chown -R nonroot:nonroot /app/boefje/masscan \
    && setcap cap_net_raw=eip /app/boefje/masscan/bin/masscan

USER nonroot

COPY ./boefjes/plugins/kat_masscan ./kat_masscan
