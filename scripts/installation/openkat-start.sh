#!/bin/bash

echo "Starting openKAT..."
sudo systemctl start xtdb-http-multinode kat-rocky kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

# Kat-rocky-worker service was introduced in OpenKAT 1.18
if [ -f /usr/lib/systemd/system/kat-rocky-worker.service ]; then
    sudo systemctl start kat-rocky-worker
fi

# Kat-octopoes-scanlevels service was introduced in OpenKAT 1.23
if [ -f /usr/lib/systemd/system/kat-octopoes-scanlevels.service ]; then
    sudo systemctl start kat-octopoes-scanlevels
fi
