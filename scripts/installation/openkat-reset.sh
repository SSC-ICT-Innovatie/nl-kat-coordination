#!/bin/bash

set -e

source /etc/os-release

if [ "$ID" != "debian" ]; then
    echo "The installation script is only supported on Debian"
    exit 1
fi

# Check Debian version
if [ "$VERSION_ID" != "12" ]; then
    echo "Only Debian version 12 is supported"
    exit 1
fi

if [ $# -gt 1 ]; then
    echo "Usage: $0 [no_super_user]"
    exit 1
fi

read -p "This script will delete all OpenKAT data. Are you sure? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

pushd /

echo "Stop OpenKAT"
sudo systemctl stop xtdb-http-multinode kat-rocky kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

# Kat-rocky-worker service was introduced in OpenKAT 1.18
if [ -f /usr/lib/systemd/system/kat-rocky-worker.service ]; then
    sudo systemctl stop kat-rocky-worker
fi

echo "Delete XTDB databases"
sudo rm -rf /var/lib/xtdb/*

echo "Delete bytes data"
sudo rm -rf /var/lib/kat-bytes/*

echo "Drop rocky_db..."
sudo -u postgres dropdb rocky_db
echo "Create rocky_db..."
sudo -u postgres createdb rocky_db
echo "Grant database rocky_db to rocky user..."
sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO rocky;' rocky_db

echo "Drop katalogus_db..."
sudo -u postgres dropdb katalogus_db
echo "Create katalogus_db..."
sudo -u postgres createdb katalogus_db
echo "Grant database katalogus_db to katalogus user..."
sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO katalogus;' katalogus_db

echo "Drop bytes_db..."
sudo -u postgres dropdb bytes_db
echo "Create bytes_db..."
sudo -u postgres createdb bytes_db
echo "Grant database bytes_db to bytes user..."
sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO bytes;' bytes_db

echo "Drop mula_db..."
sudo -u postgres dropdb mula_db
echo "Create mula_db..."
sudo -u postgres createdb mula_db
echo "Grant database muladb to mula user..."
sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO mula;' mula_db

echo "Delete vhost kat from rabbitmq"
sudo rabbitmqctl delete_vhost kat
echo "Add vhost kat to rabbitmq"
sudo rabbitmqctl add_vhost kat
echo "Set permissions for kat vhost"
sudo rabbitmqctl set_permissions -p "kat" "kat" ".*" ".*" ".*"

echo "Migrate databases"
sudo -u kat rocky-cli migrate
sudo -u kat rocky-cli loaddata /usr/share/kat-rocky/OOI_database_seed.json
sudo -u kat rocky-cli setup_dev_account
sudo -u kat update-bytes-db
sudo -u kat update-katalogus-db
sudo -u kat update-mula-db

if [[ ${1} != "no_super_user" ]]; then
    echo "Create Superuser"
    sudo -u kat rocky-cli createsuperuser
fi

echo "Start OpenKAT"
sudo systemctl start xtdb-http-multinode kat-rocky kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

# Kat-rocky-worker service was introduced in OpenKAT 1.18
if [ -f /usr/lib/systemd/system/kat-rocky-worker.service ]; then
    sudo systemctl start kat-rocky-worker
fi

popd
