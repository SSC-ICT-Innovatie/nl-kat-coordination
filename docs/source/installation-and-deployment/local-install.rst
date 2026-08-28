=====================
Development: make kat
=====================

**Important:** The version of OpenKAT you are about to install is a **development environment**, which is used by the developers to build OpenKAT. This is not a version that would be used in a production environment, and it requires some knowledge about Linux, compiling software, and Docker.

make kat
========

Install OpenKAT on your own machine with ``make kat``. If you want to deploy OpenKAT in a production environment use the hardening settings as well.

Requirements
------------

You need the following things to install OpenKAT:

- A computer with a Linux installation. In this document we use Ubuntu, but on many other distributions it works in a similar way. Later we will also add instructions for macOS.
- Docker. If you don't already have this, install it first.
- OpenKAT's `GitHub repository <https://github.com/minvws/nl-kat-coordination/>`_.

Before installing
-----------------

Install Docker
**************

OpenKAT is installed in Docker, and therefore Docker must be installed first. The preferred method of installation is through a repository. However, OpenKAT requires a newer version of Docker than what is available in the default ubuntu and debian repositories. That is why you should always use Docker's repository.

On the `Docker Engine installation overview <https://docs.docker.com/engine/install/>`_ page you can find links to installation pages for all major Linux distributions. For a specific example using the Docker repository on Debian, see `Debian install using the repository <https://docs.docker.com/engine/install/debian/#install-using-the-repository>`_. The installation pages for the other Linux distributions contain similar instructions.

**Important:** Please follow the post-installation steps as well! You can find them here: `Docker Engine post-installation steps <https://docs.docker.com/engine/install/linux-postinstall/>`_.

Install dependencies
********************

Dependencies are packages required for OpenKAT to work. Run the following commands to install them:

*Debian based systems:*


.. code-block:: sh

	$ curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
	$ sudo apt-get install -y nodejs gcc g++ make python3-pip
	$ curl -sL https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --dearmor | sudo tee /usr/share/keyrings/yarnkey.gpg >/dev/null
	$ echo "deb [signed-by=/usr/share/keyrings/yarnkey.gpg] https://dl.yarnpkg.com/debian stable main" | sudo tee /etc/apt/sources.list.d/yarn.list
	$ sudo apt-get update && sudo apt-get install yarn

After installing Docker from the Docker repository it might be necessary to create a symlink for the command `docker-compose` as the latest version now uses a space instead of a dash. You can do this with the following command:

.. code-block:: sh

	$ ln -s /usr/libexec/docker/cli/plugins/compose /usr/bin/docker-compose

*RHEL based systems:*

.. code-block:: sh

    $ sudo dnf install openssl -y
    $ sudo dnf install https://rpm.nodesource.com/pub_18.x/nodistro/repo/nodesource-release-nodistro-1.noarch.rpm -y
    $ sudo dnf install nodejs -y --setopt=nodesource-nodejs.module_hotfixes=1
    $ sudo dnf install -y nodejs gcc g++ make python3-pip docker-compose
    $ curl --silent --location https://dl.yarnpkg.com/rpm/yarn.repo | sudo tee /etc/yum.repos.d/yarn.repo
    $ sudo dnf install yarn -y

Getting Started
---------------

Now the installation of OpenKAT can begin. We do this via git.

Default installation
*********************

- Clone the repository:

.. code-block:: sh

	$ git clone https://github.com/minvws/nl-kat-coordination.git

- Go to the folder:

.. code-block:: sh

	$ cd nl-kat-coordination

- Make KAT:

.. code-block:: sh

	$ make env
	$ make kat

Currently, the ``make kat`` command only works for the first user on a ``*nix`` system. This is a known problem which will be solved soon. The current user must be user 1000. You can check this by executing `id`.

In some cases this may not work because Docker does not yet know your user name. You solve this with the following commands, entering your user name instead of $USER:

.. code-block:: sh

	$ sudo gpasswd -a $USER docker
	$ newgrp docker

Then OpenKAT is built, including all the parts such as Octopoes and Rocky.

Front end
*********

Find the frontend of your OpenKAT install at port 8000 (http) of your localhost and follow the 'onboarding flow' to test your setup and start using your development setup of OpenKAT.

By default a superuser account is created with email address ``superuser@localhost``. The password can be found as ``DJANGO_SUPERUSER_PASSWORD`` in the .env file.

Using http works only when connecting to localhost due to the security flags on the session and xsrf cookies. Localhost is whitelisted to allow secure cookies over an insecure connection. Connecting to any other IP over http results in these cookies being disregarded, resulting in XSRF warnings when logging in.

Specific builds
***************

If you want to create a specific build, you have a number of options. You can also look in the `Makefile <https://github.com/minvws/nl-kat-coordination/blob/main/Makefile>`_.

Updates
-------

Updating an existing installation can be done with the ``make update``.

Go to the directory containing openkat:

.. code-block:: sh

	$ cd nl-kat-coordination
	$ make update

Clean reinstallation
--------------------

If you to start over with a clean slate, you can do so with the following commands:

.. code-block:: sh

	$ cd nl-kat-coordination
	$ make reset

This removes all Docker containers and volumes, and then brings up the containers again.

Optionally, first remove the ``.env`` file (``rm .env``) before running ``make env`` and ``make reset`` to also reset all configuration in environment variables. This should also resolve issues such as database authentication errors (``password authentication failed``).

Observability
=============

OpenTelemetry
-------------

OpenTelemetry is a way to trace requests through the system. It is used to find out where a request is going wrong and to instrument performance problems. OpenTelemetry is not enabled by default, but can be enabled by uncommenting the environment variable ``SPAN_EXPORT_GRPC_ENDPOINT`` in the ``.env`` file.

Jaeger: Distributed Tracing
---------------------------

The `Jaeger <https://www.jaegertracing.io>`_ tracing system is used to view the traces. It can be enabled by enabling the `Docker Compose profile <https://docs.docker.com/compose/profiles/#enable-profiles>`_, for example by running ``docker-compose --profile jaeger up -d`` or using ``export COMPOSE_PROFILES=jaeger`` and then running Make as usual. The Jaeger UI can then be found at http://localhost:16686.

Pyroscope: Continuous Profiling
-------------------------------

Pyroscope is a continuous profiling tool that helps you understand the performance of your applications. It collects and visualizes profiling data, allowing you to identify performance bottlenecks and optimize resource usage. You'll be able to see how much CPU time is spent in different parts of your code, which functions are taking the most time, and how memory is being used over time.

1. Start openkat
2. ``docker compose --profile monitoring up -d``
3. Check http://localhost:4040/ for pyroscope to see if it is working
4. Check http://localhost:4000/a/grafana-pyroscope-app/explore to see if it is working
