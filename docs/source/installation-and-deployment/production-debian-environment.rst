.. _debian-install:

===========================
Production: Debian packages
===========================

OpenKAT has Debian packages available. In the near future we will have an apt
repository that will allow you to keep your installation up-to-date using apt.
An installation of KAT can be done on a single machine or spread out on several
machines for a high availability setup. This guide will take you through the
steps for installing it on a single machine. There are also :doc:`/installation-and-deployment/scripts`
available if you don't want to do this by hand.

Supported distributions
=======================

We provide Debian packages for Debian and Ubuntu. We support only Debian stable
and Ubuntu LTS releases and stop supporting the previous version 6 months after
the release. Currently this means we support Debian 11 (bullseye) and 12
(bookworm) and Ubuntu 22.04. Debian 12 has been released on 10th of June so we
will stop providing packages for Debian 11 in December 2023. After Ubuntu 24.04
is released we will provide Ubuntu 22.02 packages until October 2024.

Prerequisites
=============

We will be using ``sudo`` in this guide, so make sure you have ``sudo`` installed on
your system.

The packages are built with Ubuntu 22.04 and Debian 11 in mind.
They may or may not work on other versions or distributions.

Downloading and installing
==========================

Download the packages for all the components of KAT from `GitHub
<https://github.com/minvws/nl-kat-coordination/releases/latest>`__. Also download the XTDB
multinode package from `GitHub
<https://github.com/dekkers/xtdb-http-multinode/releases/latest>`__.

After downloading they can be installed as follows:

.. code-block:: sh

    tar zvxf kat-*.tar.gz
    sudo apt install --no-install-recommends ./kat-*_amd64.deb ./xtdb-http-multinode_*_all.deb

Set up RabbitMQ
===============

Installation
------------

Use the following steps to set up RabbitMQ and allow kat to use it.

Start by installing RabbitMQ:

.. code-block:: sh

    sudo apt install rabbitmq-server

By default RabbitMQ will listen on all interfaces. For a single node setup this is not what we want.
To prevent RabbitMQ from being accessed from the internet add the following lines to ``/etc/rabbitmq/rabbitmq-env.conf``:

.. code-block:: sh

    export ERL_EPMD_ADDRESS=127.0.0.1
    export NODENAME=rabbit@localhost

Stop RabbitMQ and epmd:

.. code-block:: sh

    sudo systemctl stop rabbitmq-server
    sudo epmd -kill

Create a new file ``/etc/rabbitmq/rabbitmq.conf`` and add the following lines:

.. code-block:: unixconfig

    listeners.tcp.local = 127.0.0.1:5672

Create a new file ``/etc/rabbitmq/advanced.conf`` and add the following lines:

.. code-block:: erlang

    [
        {kernel,[
            {inet_dist_use_interface,{127,0,0,1}}
        ]}
    ].

Now start RabbitMQ again and check if it only listens on localhost for ports 5672 and 25672:

.. code-block:: sh

    systemctl start rabbitmq-server

Add the 'kat' vhost
-------------------

Generate a safe password for the KAT user in rabbitmq. You can use the /dev/urandom method again and put it in a shell variable to use it later:

.. code-block:: sh

    rabbitmq_pass=$(tr -dc A-Za-z0-9 < /dev/urandom | head -c 20)

Now create a KAT user for RabbitMQ, create the virtual host and set the permissions:

.. code-block:: sh

    sudo rabbitmqctl add_user kat ${rabbitmq_pass}
    sudo rabbitmqctl add_vhost kat
    sudo rabbitmqctl set_permissions -p "kat" "kat" ".*" ".*" ".*"

Now configure KAT to use the vhost we created and with the kat user. To do this, update ``QUEUE_URI`` in the following files:

 * ``/etc/kat/mula.conf``
 * ``/etc/kat/rocky.conf``
 * ``/etc/kat/bytes.conf``
 * ``/etc/kat/boefjes.conf``
 * ``/etc/kat/octopoes.conf``

.. code-block:: sh

    QUEUE_URI=amqp://kat:<password>@127.0.0.1:5672/kat

Or use this command to do it for you:

.. code-block:: sh

    sudo sed -i "s|QUEUE_URI= *\$|QUEUE_URI=amqp://kat:${rabbitmq_pass}@127.0.0.1:5672/kat|" /etc/kat/*.conf

Set up the databases
====================

OpenKAT needs three databases for its components. One for rocky, KAT-alogus and bytes. The following steps will guide you through the creation of these databases.

If you will be running the database on the same machine as KAT, you can install Postgres:

.. code-block:: sh

    sudo apt install postgresql

Rocky DB
--------

Generate a secure password for the Rocky database user, as an example we'll use ``/dev/urandom``:

.. code-block:: sh

    echo $(tr -dc A-Za-z0-9 < /dev/urandom | head -c 20)

To configure rocky to use this password, open ``/etc/kat/rocky.conf`` and fill in this password for ``ROCKY_DB_PASSWORD``.

Create the database and user for Rocky in Postgres:

.. code-block:: sh

    sudo -u postgres createdb rocky_db
    sudo -u postgres createuser rocky -P
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO rocky;' rocky_db

Now use rocky-cli to initialize the database:

.. code-block:: sh

    sudo -u kat rocky-cli migrate
    sudo -u kat rocky-cli loaddata /usr/share/kat-rocky/OOI_database_seed.json

The steps for creating the other databases will be similar, but we'll explain them anyway for completeness.

KAT-alogus DB
-------------

Generate a unique secure password for the KAT-alogus database user. You can use the same method we used for generating the Rocky database user password.

Insert this password into the connection string for the KAT-alogus DB in ``/etc/kat/boefjes.conf``. For example:

.. code-block:: sh

    KATALOGUS_DB_URI=postgresql://katalogus:<password>@localhost/katalogus_db

Create a new database and user for KAT-alogus:

.. code-block:: sh

    sudo -u postgres createdb katalogus_db
    sudo -u postgres createuser katalogus -P
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO katalogus;' katalogus_db

Initialize the database using the update-katalogus-db tool:

.. code-block:: sh

    sudo -u kat update-katalogus-db

Bytes DB
--------

Generate a unique password for the Bytes database user. Insert this password
into the connection string for the Bytes DB in ``/etc/kat/bytes.conf``. For
example:

.. code-block:: sh

    BYTES_DB_URI=postgresql://bytes:<password>@localhost/bytes_db

Create a new database and user for Bytes:

.. code-block:: sh

    sudo -u postgres createdb bytes_db
    sudo -u postgres createuser bytes -P
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO bytes;' bytes_db

Initialize the Bytes database:

.. code-block:: sh

    sudo -u kat update-bytes-db

Mula DB
--------

Generate a unique password for the Mula database user. Insert this password into
the connection string for the Mula DB in ``/etc/kat/mula.conf``. For example:

.. code-block:: sh

    SCHEDULER_DB_URI=postgresql://mula:<password>@localhost/mula_db

Create a new database and user for Mula:

.. code-block:: sh

    sudo -u postgres createdb mula_db
    sudo -u postgres createuser mula -P
    sudo -u postgres psql -c 'GRANT ALL ON SCHEMA public TO mula;' mula_db

Initialize the Mula database:

.. code-block:: sh

    sudo -u kat update-mula-db

Create Rocky superuser and set up default groups and permissions
================================================================

Create an admin user for OpenKAT

.. code-block:: sh

    sudo -u kat rocky-cli createsuperuser

Create the default groups and permissions for KAT:

.. code-block:: sh

    sudo -u kat rocky-cli setup_dev_account

Configure Bytes credentials
===========================

copy the value of ``BYTES_PASSWORD`` in ``/etc/kat/bytes.conf`` to the setting with the same name in the following files:

- ``/etc/kat/rocky.conf``
- ``/etc/kat/boefjes.conf``
- ``/etc/kat/mula.conf``

This oneliner will do it for you, executed as root:

.. code-block:: sh

    sudo sed -i "s/BYTES_PASSWORD= *\$/BYTES_PASSWORD=$(grep BYTES_PASSWORD /etc/kat/bytes.conf | awk -F'=' '{ print $2 }')/" /etc/kat/*.conf

Configure hostname in Rocky
===========================

The ``DJANGO_ALLOWED_HOSTS`` and ``DJANGO_CSRF_TRUSTED_ORIGINS`` variables in
``/etc/kat/rocky.conf`` need to be configured with the hostname (or hostnames separated by commas) that will be used
to access OpenKAT. If ``openkat.example.org`` is used to access OpenKAT the
configuration should be:

.. code-block:: sh

    DJANGO_ALLOWED_HOSTS="openkat.example.org"
    DJANGO_CSRF_TRUSTED_ORIGINS="https://openkat.example.org"

Restart KAT
===========

After finishing these steps, you should restart KAT to load the new configuration:

.. code-block:: sh

    sudo systemctl restart kat-rocky kat-rocky-worker kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

Start KAT on system boot
========================

To start KAT when the system boots, enable all KAT services:

.. code-block:: sh

    sudo systemctl enable kat-rocky kat-rocky-worker kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker

.. _debian_prod_configure_reverse_proxy:

Configure reverse proxy
=======================

OpenKAT listens on 127.0.0.1 port 8000 by default. We recommend that you access
OpenKAT through a reverse proxy. If you already have a reverse proxy on a
different host then you need to change ``GRANIAN_HOST`` in rocky.conf to be able
to access OpenKAT from the reverse proxy:

.. code-block:: sh

    GRANIAN_HOST=0.0.0.0

If you want to use https between the reverse proxy and OpenKAT you can do that
by setting also setting ``GRANIAN_PORT``, ``GRANIAN_SSL_KEYFILE`` and
``GRANIAN_SSL_CERTIFICATE`` in rocky.conf:

.. code-block:: sh

    GRANIAN_HOST=0.0.0.0
    GRANIAN_PORT=8443
    GRANIAN_SSL_KEYFILE=/path/to/key
    GRANIAN_SSL_CERTIFICATE=/path/to/cert

See also the `Granian documentation
<https://github.com/emmett-framework/granian/blob/master/README.md>`_ for more
information.

If you aren't already running a reverse proxy, we recommend installing Caddy:

.. code-block:: sh

    apt install caddy

Caddy is a webserver written in Go that can automatically request letsencrypt
certificates or generate its own Certificate Authority and certificates. If you
want to have OpenKAT be available on 192.0.2.1 using certificates generated by
Caddy you can create the following configuration in ``/etc/caddy/Caddyfile``:

.. code-block::

    192.0.2.1 {
        header Strict-Transport-Security max-age=31536000;
        reverse_proxy 127.0.0.1:8000
    }

The CA certificate Caddy creates can be found in
``/usr/local/share/ca-certificates``. If you want to have OpenKAT available on
example.com using letsencrypt certificates, make sure that example.com points to
your server and configure the following in ``/etc/caddy/Caddyfile``:

.. code-block::

    example.com {
        header Strict-Transport-Security max-age=31536000;
        reverse_proxy 127.0.0.1:8000
    }

This will use http ACME challenge by default but can also be configured to use
the DNS challenge. For more information see the `Caddy documentation
<https://caddyserver.com/docs/automatic-https>`_.

Note that we don't recommend exposing OpenKAT directly to the internet and
recommend that you make sure only authorised persons can access OpenKAT.


Start using OpenKAT
===================

By default OpenKAT will be accessible in your browser through ``https://<server IP>:8443`` (http://<server IP>:8000 for docker based installs). There, Rocky will take you through the steps of setting up your account and running your first boefjes.

.. _Upgrading Debian:

Upgrading OpenKAT
=================

You can upgrade OpenKAT by installing the newer packages. Make a backup of your files, download the packages and remove the old ones if needed:

.. code-block:: sh

    tar zvxf kat-*.tar.gz
    sudo apt install --no-install-recommends ./kat-*_amd64.deb

If a newer version of the xtdb multinode is available install it as well:

.. code-block:: sh

    apt install --no-install-recommends ./xtdb-http-multinode_*_all.deb

After installation you need to run the database migrations and load fixture again. For Rocky DB:

.. code-block:: sh

    sudo -u kat rocky-cli migrate
    sudo -u kat rocky-cli loaddata /usr/share/kat-rocky/OOI_database_seed.json

When running "sudo -u kat rocky-cli migrate" you might get the warning "Your models in app(s): 'password_history', 'two_factor' have changes that are not yet reflected in a migration, and so won't be applied." This can be ignored.

For KAT-alogus DB

.. code-block:: sh

    sudo -u kat update-katalogus-db

For Bytes DB:

.. code-block:: sh

    sudo -u kat update-bytes-db

For Mula DB:

.. code-block:: sh

    sudo -u kat update-mula-db

Restart all processes:

.. code-block:: sh

    sudo systemctl restart kat-rocky kat-rocky-worker kat-mula kat-bytes kat-boefjes kat-normalizers kat-katalogus kat-octopoes kat-octopoes-worker
