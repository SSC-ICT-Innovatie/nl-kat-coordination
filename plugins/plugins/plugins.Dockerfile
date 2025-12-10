FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

LABEL openkat.api_version="v1"

ENV UV_NO_CACHE=1
ENV UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends jq
RUN uv pip install httpx==0.27.2 tldextract==5.3.0 dnspython==2.6.1 python-libnmap==0.7.3 polars==1.32.3 polars-iptools==0.1.10 sslyze==6.2.0 wellknown-securitytxt==0.9.8

COPY ./plugins/plugins/kat_dns/ ./kat_dns
COPY ./plugins/plugins/kat_nmap/ ./kat_nmap
COPY ./plugins/plugins/kat_rpki/ ./kat_rpki
COPY ./plugins/plugins/kat_dnssec/ ./kat_dnssec
COPY ./plugins/plugins/kat_nuclei/ ./kat_nuclei
COPY ./plugins/plugins/kat_sslyze/ ./kat_sslyze
COPY ./plugins/plugins/kat_securitytxt ./kat_securitytxt
COPY ./plugins/plugins/kat_scripts/ ./
