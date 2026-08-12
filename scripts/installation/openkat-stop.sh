#!/bin/bash

echo "Stopping openKAT..."
sudo systemctl stop xtdb-http-multinode kat-rocky kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

# Kat-rocky-worker service was introduced in OpenKAT 1.18
if [ -f /usr/lib/systemd/system/kat-rocky-worker.service ]; then
    sudo systemctl stop kat-rocky-worker
fi
