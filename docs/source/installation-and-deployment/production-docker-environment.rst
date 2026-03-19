================================
Production: Container deployment
================================

OpenKAT can be deployed using containers. We aim to support both simple docker /
docker compose setups and container orchestration systems like Kubernetes and
Nomad.

There is a docker-compose.release-example.yml in the root directory that can be
used as an example how to deploy using docker-compose.

Container images
================

The container images can be found here:

- https://github.com/minvws/nl-kat-boefjes/pkgs/container/nl-kat-boefjes
- https://github.com/minvws/nl-kat-bytes/pkgs/container/nl-kat-bytes
- https://github.com/minvws/nl-kat-mula/pkgs/container/nl-kat-mula
- https://github.com/minvws/nl-kat-octopoes/pkgs/container/nl-kat-octopoes
- https://github.com/minvws/nl-kat-rocky/pkgs/container/nl-kat-rocky

Setup
=====

To set up an installation with pre-built containers, you can pull the repository using:

```shell
git clone https://github.com/minvws/nl-kat-coordination.git
```

If this is your first install, and you do not have an .env file yet, you can create an `.env` file using the following command:

```shell
make env
```

This will create an `.env` file with the default values. You can edit this file to change the default values.
Make sure that you also add the keys and values from `.env-defaults` to your `.env` file, and modify them for production use where necessary.

Now you can pull and start the containers using the following command:

```shell
docker compose --env-file .env-prod -f docker-compose.release-example.yml up -d
```

The container image run the necessary database migration commands in the
entrypoint if DATABASE_MIGRATION is set. You manually need to run setup commands
in the rocky container to initialize everything. In the rocky container we first need to import the OOI database seed:

```shell
python3 manage.py loaddata OOI_database_seed.json
```

With docker compose you would run this as:

```shell
docker compose --env-file .env-prod -f docker-compose.release-example.yml exec rocky python3 manage.py loaddata OOI_database_seed.json
```

Next we need to create the superuser, this will prompt for the e-mail address and password:

```shell
python3 manage.py createsuperuser
```

With docker compose you would run this as:

```shell
docker compose --env-file .env-prod -f docker-compose.release-example.yml exec rocky python3 manage.py createsuperuser
```

We also need to create an organisation, this command will create a development organisation:

```shell
python3 manage.py setup_dev_account
```

With docker compose you would run this as:

```shell
docker compose --env-file .env-prod -f docker-compose.release-example.yml exec rocky python3 manage.py setup_dev_account
```

IPv6 support
============

In order to perform scans against IPv6 addresses you need to manually enable IPv6 support in Dockerized setups. Add the following snippet to the file `/etc/docker/daemon.json`. If this file doesn't exist yet, you can create it and save it with the following configuration:

.. code-block:: JSON

 {
    "experimental": true,
    "ip6tables": true
 }


Restart the Docker daemon for your changes to take effect.

```shell
$ sudo systemctl restart docker
```

By default OpenKAT has an IPv6 subnet configured. This configuration (step 4 and onwards from the official Docker documentation as listed below) can be found in the `docker-compose.yml` file. For more information on IPv6 support within Docker look at the `Docker documentation <https://docs.docker.com/config/daemon/ipv6/>`_.

Container commands
==================

We have three container images that are used to run multiple containers. What the container runs is be specified by overriding the CMD of the container.

| Container image | CMD         | Description                                                                       |
| --------------- | ----------- | --------------------------------------------------------------------------------- |
| rocky           | web         | Django web application                                                            |
| rocky           | worker      | Rocky reports runner                                                              |
| boefjes         | boefje      | Boefjes runtime                                                                   |
| boefjes         | normalizer  | Normalizers runtime                                                               |
| boefjes         | katalogus   | Katalogus API                                                                     |
| octopoes        | web         | Octopoes API                                                                      |
| octopoes        | worker-beat | Celery worker running beat. There must only be exactly one container of this type |
| octopoes        | worker      | Celery worker. Use this if you need to more than one work container for scaling   |

.. _Upgrading_Containers:

Upgrading
=========

When deploying new container images the database migrations are automatically
run in the entrypoint. The OOI_database_seed.json file needs to be loaded
manually using the following command:

```shell
python3 manage.py loaddata OOI_database_seed.json
```

With docker compose you would run this as:

```shell
docker compose --env-file .env-prod -f docker-compose.release-example.yml exec rocky python3 manage.py loaddata OOI_database_seed.json
```
