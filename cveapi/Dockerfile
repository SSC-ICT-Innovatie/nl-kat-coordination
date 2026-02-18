FROM python:3.13-slim

RUN pip install --no-cache-dir httpx

RUN mkdir -p /app /var/lib/kat-cveapi/v1

COPY cveapi.py /app/cveapi.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /app
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
