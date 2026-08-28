#!/bin/bash

# Installation script for Debian. The script matches the instructions on
# https://docs.openkat.nl/installation_and_deployment/debianinstall.html

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

# Checking if we don't have too many parameters
if [ $# -gt 2 ]; then
    echo "Usage: $0 [openKAT version] [no_super_user]"
    exit 1
fi

debian_version=$VERSION_ID

echo "Step 0 - Preparations"

echo "Step 0.1 - Removing old install/upgrade files, update system and install curl & sudo when needed..."
rm -f kat-*.deb kat-debian1[12]-*.tar.gz xtdb-*.deb

echo "Step 0.2 - Update OS and get needed tools"
if ! command -v sudo; then
    if [ "$EUID" -ne 0 ]; then
        echo "Sudo could not be found, please first install sudo as root"
        exit 1
    fi
    apt -y update
    apt -y install sudo
fi

sudo apt -y update
sudo apt -y install curl

echo "Step 1 - Determine latest xtdb-http-multinode and OpenKAT versions"

# The URL of the latest xtdb-http-multinode release
xtdb_url='https://github.com/underdarknl/xtdb-http-multinode/releases/latest'

# The URL of the latest OpenKAT release
openkat_url='https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/releases/latest'

xtdb_version=$(curl -sL $xtdb_url | grep -m 1 -Po "(?<=tag\/)v[0-9\.]*(?=\")" | sed 's/^v//')

if [ $# -eq 0 ]; then
    # Get the latest version of OpenKAT if no version is specified
    openkat_version=$(curl -sL $openkat_url | grep -m 1 -Po "(?<=tag\/)v[0-9\.]*(?=\")" | sed 's/^v//')
else
    openkat_version=$1
fi

echo "Step 2 - Download OpenKAT and xtdb-http-multinode"

echo "Step 2.1 - Downloading xtdb-http-multinode version $xtdb_version..."
curl -LO "https://github.com/underdarknl/xtdb-http-multinode/releases/download/v${xtdb_version}/xtdb-http-multinode_${xtdb_version}_all.deb"

echo "Step 2.2 - Downloading OpenKAT version $openkat_version..."
curl -LO "https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/releases/download/v${openkat_version}/kat-debian${debian_version}-${openkat_version}.tar.gz"

echo "Step 3 - Install OpenKAT and xtdb"
tar zvxf kat-*.tar.gz
sudo apt install -y --no-install-recommends ./kat-*_amd64.deb ./xtdb-http-multinode_*_all.deb

echo "Step 4 - Setup postgres databases"
sudo apt -y install postgresql

sudo systemctl start postgresql

echo "Step 4.1 - Generating Passwords"
ROCKY_DB_PASSWORD=$(tr -dc A-Za-z0-9 < /dev/urandom | head -c 20)
export ROCKY_DB_PASSWORD
KATALOGUSDB_PASSWORD=$(tr -dc A-Za-z0-9 < /dev/urandom | head -c 20)
export KATALOGUSDB_PASSWORD
BYTESDB_PASSWORD=$(tr -dc A-Za-z0-9 < /dev/urandom | head -c 20)
export BYTESDB_PASSWORD
RABBITMQ_PASSWORD=$(tr -dc A-Za-z0-9 < /dev/urandom | head -c 20)
export RABBITMQ_PASSWORD
MULADB_PASSWORD=$(tr -dc A-Za-z0-9 < /dev/urandom | head -c 20)
export MULADB_PASSWORD

echo "Step 4.2 - Saving Passwords to passwords.txt"
umask=$(umask)
umask 0077

cat > passwords.txt << EOF
ROCKY_DB_PASSWORD=${ROCKY_DB_PASSWORD}
KATALOGUSDB_PASSWORD=${KATALOGUSDB_PASSWORD}
BYTESDB_PASSWORD=${BYTESDB_PASSWORD}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
MULADB_PASSWORD=${MULADB_PASSWORD}
EOF

# restore umask
umask "${umask}"

# This will prevent "could not change directory" errors due to permissions when
# using sudo
pushd /

echo "Step 4.3 - Rocky DB"
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -q rocky_db; then
    echo "Create rocky_db..."
    sudo -u postgres createdb rocky_db
fi

if [ ! "$(sudo -u postgres psql -qtAc "SELECT 1 FROM pg_roles WHERE rolname='rocky'")" ]; then
    echo "Create rocky user with password ${ROCKY_DB_PASSWORD}..."
    sudo -u postgres psql -c "CREATE USER rocky WITH PASSWORD '${ROCKY_DB_PASSWORD}';"

    echo "Grant database rocky_db to rocky user..."
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO rocky;' rocky_db
else
    echo "Change password rocky user to ${ROCKY_DB_PASSWORD}..."
    sudo -u postgres psql -c "ALTER USER rocky WITH PASSWORD '${ROCKY_DB_PASSWORD}';"
fi

echo "Step 4.4 - KAT-alogus DB"
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -q katalogus_db; then
    echo "Create katalogus_db..."
    sudo -u postgres createdb katalogus_db
fi

if [ ! "$(sudo -u postgres psql -qtAc "SELECT 1 FROM pg_roles WHERE rolname='katalogus'")" ]; then
    echo "Create katalogus user with password ${KATALOGUSDB_PASSWORD}..."
    sudo -u postgres psql -c "CREATE USER katalogus WITH PASSWORD '${KATALOGUSDB_PASSWORD}';"

    echo "Grant database katalogus_db to katalogus user..."
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO katalogus;' katalogus_db
else
    echo "Change password katalogus user to ${KATALOGUSDB_PASSWORD}..."
    sudo -u postgres psql -c "ALTER USER katalogus WITH PASSWORD '${KATALOGUSDB_PASSWORD}';"
fi

echo "Step 4.5 - Bytes DB"
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -q bytes_db; then
    echo "Create bytes_db..."
    sudo -u postgres createdb bytes_db
fi

if [ ! "$(sudo -u postgres psql -qtAc "SELECT 1 FROM pg_roles WHERE rolname='bytes'")" ]; then
    echo "Create bytes user with password ${BYTESDB_PASSWORD}..."
    sudo -u postgres psql -c "CREATE USER bytes WITH PASSWORD '${BYTESDB_PASSWORD}';"

    echo "Grant database bytes_db to bytes user..."
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO bytes;' bytes_db
else
    echo "Change password bytes user to ${BYTESDB_PASSWORD}..."
    sudo -u postgres psql -c "ALTER USER bytes WITH PASSWORD '${BYTESDB_PASSWORD}';"
fi

echo "Step 4.5b - Mula DB"
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -q mula_db; then
    echo "Create mula_db..."
    sudo -u postgres createdb mula_db
fi

if [ ! "$(sudo -u postgres psql -qtAc "SELECT 1 FROM pg_roles WHERE rolname='mula'")" ]; then
    echo "Create mula user with password ${MULADB_PASSWORD}..."
    sudo -u postgres psql -c "CREATE USER mula WITH PASSWORD '${MULADB_PASSWORD}';"

    echo "Grant database muladb to mula user..."
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO mula;' mula_db
else
    echo "Change password mula user to ${MULADB_PASSWORD}..."
    sudo -u postgres psql -c "ALTER USER mula WITH PASSWORD '${MULADB_PASSWORD}';"
fi

popd

echo Step 4.6 - Update configs
echo "Step 4.6.1 - Update ROCKY_DB_PASSWORD in /etc/kat/rocky.conf to ${ROCKY_DB_PASSWORD}"
sudo sed -i "/ROCKY_DB_PASSWORD=/s/.*/ROCKY_DB_PASSWORD=${ROCKY_DB_PASSWORD}/" /etc/kat/rocky.conf

echo "Step 4.6.2 - Update BYTES_PASSWORD in /etc/kat/bytes.conf, /etc/kat/boefjes.conf, /etc/kat/mula.conf and /etc/kat/rocky.conf to ${BYTESDB_PASSWORD}"
sudo sed -i "/BYTES_PASSWORD=/s/.*/BYTES_PASSWORD=${BYTESDB_PASSWORD}/" /etc/kat/bytes.conf
sudo sed -i "/BYTES_PASSWORD=/s/.*/BYTES_PASSWORD=${BYTESDB_PASSWORD}/" /etc/kat/boefjes.conf
sudo sed -i "/BYTES_PASSWORD=/s/.*/BYTES_PASSWORD=${BYTESDB_PASSWORD}/" /etc/kat/mula.conf
sudo sed -i "/BYTES_PASSWORD=/s/.*/BYTES_PASSWORD=${BYTESDB_PASSWORD}/" /etc/kat/rocky.conf

echo "Step 4.6.3 - Update BYTES_DB_URI in /etc/kat/bytes.conf to ${BYTESDB_PASSWORD}"
sudo sed -i "/BYTES_DB_URI=/s/.*/BYTES_DB_URI=postgresql:\/\/bytes:${BYTESDB_PASSWORD}@localhost\/bytes_db/" /etc/kat/bytes.conf

echo "Step 4.6.4 - Update KATALOGUS_DB_URI in /etc/kat/boefjes.conf to ${KATALOGUSDB_PASSWORD}"
sudo sed -i "/KATALOGUS_DB_URI=/s/.*/KATALOGUS_DB_URI=postgresql:\/\/katalogus:${KATALOGUSDB_PASSWORD}@localhost\/katalogus_db/" /etc/kat/boefjes.conf

echo "Step 4.6.5 - Update SCHEDULER_DB_URI in /etc/kat/mula.conf to ${MULADB_PASSWORD}"
sudo sed -i "/SCHEDULER_DB_URI=/s/.*/SCHEDULER_DB_URI=postgresql:\/\/mula:${MULADB_PASSWORD}@localhost\/mula_db/" /etc/kat/mula.conf

echo "Step 4.6.6 - Update QUEUE_URI in bytes.conf, boefjes.conf, mula.conf, octopoes.conf to ${RABBITMQ_PASSWORD}"
sudo sed -i "/QUEUE_URI=/s/.*/QUEUE_URI=amqp:\/\/kat:${RABBITMQ_PASSWORD}@127.0.0.1:5672\/kat/" /etc/kat/bytes.conf
sudo sed -i "/QUEUE_URI=/s/.*/QUEUE_URI=amqp:\/\/kat:${RABBITMQ_PASSWORD}@127.0.0.1:5672\/kat/" /etc/kat/boefjes.conf
sudo sed -i "/QUEUE_URI=/s/.*/QUEUE_URI=amqp:\/\/kat:${RABBITMQ_PASSWORD}@127.0.0.1:5672\/kat/" /etc/kat/octopoes.conf
sudo sed -i "/QUEUE_URI=/s/.*/QUEUE_URI=amqp:\/\/kat:${RABBITMQ_PASSWORD}@127.0.0.1:5672\/kat/" /etc/kat/mula.conf

echo "<v1.11 Backwards compatibility for Mula environment variables (if they exist)"

echo "Step 4.6.7B - Update SCHEDULER_RABBITMQ_DSN in /etc/kat/mula.conf to ${RABBITMQ_PASSWORD}"
sudo sed -i "/SCHEDULER_RABBITMQ_DSN=/s/.*/SCHEDULER_RABBITMQ_DSN=amqp:\/\/kat:${RABBITMQ_PASSWORD}@127.0.0.1:5672\/kat/" /etc/kat/mula.conf

echo "Step 4.6.8B - Update SCHEDULER_DB_DSN in /etc/kat/mula.conf to ${MULADB_PASSWORD}"
sudo sed -i "/SCHEDULER_DB_DSN=/s/.*/SCHEDULER_DB_DSN=postgresql:\/\/mula:${MULADB_PASSWORD}@localhost\/mula_db/" /etc/kat/mula.conf

echo "Step 4.7 - Initialize databases"

echo "Setp 4.7.1 - Migrating database"
sudo -u kat rocky-cli migrate

echo "Step 4.7.2 - Load data..."
sudo -u kat rocky-cli loaddata /usr/share/kat-rocky/OOI_database_seed.json

echo "Step 4.7.3 - Run migrations bytes_db..."
sudo -u kat update-bytes-db

echo "Step 4.7.4 - Run migrations katalogus_db..."
sudo -u kat update-katalogus-db

echo "Step 4.7.5 - Run migrations mula_db..."
sudo -u kat update-mula-db

if [[ ${2} != "no_super_user" ]]; then
    echo "Step 5 - Create Superuser & dev account"
    sudo -u kat rocky-cli createsuperuser
    sudo -u kat rocky-cli setup_dev_account
else
    echo "Step 5 - Option no_super_user passed; skipping creating superuser & dev account"
fi

echo "Step 6 - RabbitMQ-server setup"

echo "Step 6.1 - Install rabbitmq-server"
sudo apt -y install rabbitmq-server

echo "Step 6.2 - Stop rabbitmq-server"
sudo systemctl stop rabbitmq-server

echo "Step 6.3 - Kill epmd"
sudo epmd -kill

echo "Step 6.4 - Add listeners to /etc/rabbitmq/rabbitmq.conf"
sudo su -c "echo listeners.tcp.local = 127.0.0.1:5672 > /etc/rabbitmq/rabbitmq.conf"

echo "Step 6.5 - Add ERL_EPMD_ADDRESS to /etc/rabbitmq/rabbitmq-env.conf"
sudo su -c "echo export ERL_EPMD_ADDRESS=127.0.0.1 > /etc/rabbitmq/rabbitmq-env.conf"

echo "Step 6.6 - Add NODENAME to /etc/rabbitmq/rabbitmq-env.conf"
sudo su -c "echo export NODENAME=rabbit@localhost >> /etc/rabbitmq/rabbitmq-env.conf"

echo "Step 6.7 - Add inet info to /etc/rabbitmq/advanced.conf"
sudo su -c "sudo cat > /etc/rabbitmq/advanced.conf << 'EOF'
[
    {kernel,[
        {inet_dist_use_interface,{127,0,0,1}}
    ]}
].
EOF"

echo "Step 6.8 - Restart rabbitmq-server"
sudo systemctl restart rabbitmq-server

echo "Step 6.9 - Add or change kat user to rabbitmq and set password to ${RABBITMQ_PASSWORD}"
if ! sudo rabbitmqctl list_users | grep -q kat; then
    echo "Create kat user in rabbitmq with password ${RABBITMQ_PASSWORD}"
    sudo rabbitmqctl add_user kat "${RABBITMQ_PASSWORD}"
else
    echo "Change password for existing kat user to ${RABBITMQ_PASSWORD} to ensure it is set correctly"
    sudo rabbitmqctl change_password kat "${RABBITMQ_PASSWORD}"
fi

echo "Step 6.10 - Add vhost kat to rabbitmq"
sudo rabbitmqctl add_vhost kat

echo "Step 6.11 - Set kat permissions in rabbitmq"
sudo rabbitmqctl set_permissions -p "kat" "kat" ".*" ".*" ".*"

echo "Step 7 - Configure start at system boot"
sudo systemctl enable kat-rocky kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

# Kat-rocky-worker service was introduced in OpenKAT 1.18
if [ -f /usr/lib/systemd/system/kat-rocky-worker.service ]; then
    sudo systemctl enable kat-rocky-worker
fi

echo "Step 8 - Restart OpenKAT"
sudo systemctl restart kat-rocky kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

# Kat-rocky-worker service was introduced in OpenKAT 1.18
if [ -f /usr/lib/systemd/system/kat-rocky-worker.service ]; then
    sudo systemctl restart kat-rocky-worker
fi

echo "Step 9 - End of OpenKAT install script"
