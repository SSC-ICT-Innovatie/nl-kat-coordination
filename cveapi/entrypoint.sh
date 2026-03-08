#!/bin/bash
set -e

UPDATE_INTERVAL=${CVEAPI_UPDATE_INTERVAL:-86400}

# /var/lib/kat-cveapi is a persistent volume mount (cveapi-data).
# cveapi.py uses lastupdate.json to track the last download timestamp,
# so restarts only fetch delta updates from NVD, not a full re-download.

# Start HTTP server immediately so cached CVEs are available right away
cd /var/lib/kat-cveapi
python -m http.server 8080 &

# Download/update (skips already downloaded CVEs via lastupdate.json)
cd /app
echo "Starting CVE download..."
python -c "from cveapi import run; run()"
echo "CVE download complete"

# Update loop - fetch new/modified CVEs (only delta)
while true; do
    echo "Next update in ${UPDATE_INTERVAL}s..."
    sleep "$UPDATE_INTERVAL"
    echo "Updating CVE database..."
    python -c "from cveapi import run; run()" || echo "Update failed, will retry next cycle"
done
