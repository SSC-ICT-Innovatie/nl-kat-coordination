#!/bin/bash
set -e

UPDATE_INTERVAL=${CVEAPI_UPDATE_INTERVAL:-86400}

# Start HTTP server immediately so CVEs already downloaded are available
cd /var/lib/kat-cveapi
python -m http.server 8080 &

# Initial download/update
cd /app
echo "Starting CVE download..."
python -c "from cveapi import run; run()"
echo "Initial CVE download complete"

# Update loop - fetch new/modified CVEs every hour (only delta)
while true; do
    echo "Next update in ${UPDATE_INTERVAL}s..."
    sleep "$UPDATE_INTERVAL"
    echo "Updating CVE database..."
    python -c "from cveapi import run; run()" || echo "Update failed, will retry next cycle"
done
