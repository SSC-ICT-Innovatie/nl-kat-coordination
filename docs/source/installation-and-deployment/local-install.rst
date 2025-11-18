=====================
Local Installation
=====================

This guide covers installing OpenKAT v2 on your local machine for development, testing, or evaluation.

Quick Start
===========

The simplest way to get OpenKAT running locally is:

.. code-block:: bash

   $ git clone https://github.com/minvws/nl-kat-coordination.git
   $ cd nl-kat-coordination
   $ make kat

This single command sets up a complete development environment. See :doc:`developer-environment` for full details.

What is `make kat`?
===================

The ``make kat`` command is an all-in-one installer that:

1. Generates random credentials in ``.env``
2. Builds Docker images
3. Starts all containers (Django, PostgreSQL, XTDB, Redis, Celery worker)
4. Runs database migrations
5. Creates a superuser account
6. Seeds initial data

After 5-10 minutes (first run), OpenKAT will be running at http://localhost:8000.

System Requirements
===================

Minimum requirements for local installation:

- **CPU**: 2 cores
- **RAM**: 8 GB
- **Disk**: 25 GB free space
- **OS**: Linux, macOS, or Windows with WSL2
- **Docker**: 20.10+ with Docker Compose 2.0+

See :doc:`install` for detailed requirements.

Prerequisites
=============

Linux (Ubuntu/Debian)
*********************

.. code-block:: bash

   # Install Docker (use official repository, not Ubuntu's)
   $ curl -fsSL https://get.docker.com -o get-docker.sh
   $ sudo sh get-docker.sh

   # Add user to docker group
   $ sudo usermod -aG docker $USER
   $ newgrp docker

   # Install make and git
   $ sudo apt install make git

macOS
*****

1. Install Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Install Homebrew (if needed): https://brew.sh
3. Install make and git:

   .. code-block:: bash

      $ brew install make git

Windows
*******

1. Enable WSL2: https://docs.microsoft.com/en-us/windows/wsl/install
2. Install Docker Desktop for Windows: https://www.docker.com/products/docker-desktop/
3. Inside WSL2 terminal:

   .. code-block:: bash

      $ sudo apt install make git

Installation Steps
==================

1. Clone Repository
*******************

.. code-block:: bash

   $ git clone https://github.com/minvws/nl-kat-coordination.git
   $ cd nl-kat-coordination

2. Run Installation
*******************

.. code-block:: bash

   $ make kat

**Note**: The first run takes 5-10 minutes to build images. Subsequent runs are much faster.

If you encounter errors, run ``make kat`` again - the process is idempotent.

3. Access OpenKAT
*****************

Once installation completes:

1. Open http://localhost:8000 in your browser
2. Get login credentials:

   .. code-block:: bash

      $ cat .env | grep DJANGO_SUPERUSER
      DJANGO_SUPERUSER_EMAIL=superuser@localhost
      DJANGO_SUPERUSER_PASSWORD=GENERATED_PASSWORD

3. Login and complete the onboarding wizard

What's Running?
===============

After ``make kat`` completes, these Docker containers will be running:

.. list-table::
   :header-rows: 1

   * - Container
     - Purpose
     - Port
   * - openkat
     - Django application
     - 8000
   * - postgres
     - Operational database
     - 5432
   * - xtdb
     - Object database
     - 5433
   * - redis
     - Message broker
     - 6379
   * - worker
     - Celery task worker
     - N/A

Check container status:

.. code-block:: bash

   $ docker compose ps

Common Operations
=================

View Logs
*********

.. code-block:: bash

   # All services
   $ docker compose logs -f

   # Specific service
   $ docker compose logs -f openkat

Access Databases
****************

.. code-block:: bash

   # PostgreSQL
   $ docker compose exec postgres psql -U postgres postgres

   # XTDB
   $ docker compose exec postgres psql -h xtdb -d xtdb

Run Django Commands
*******************

.. code-block:: bash

   $ docker compose exec openkat python manage.py COMMAND

   # Examples:
   $ docker compose exec openkat python manage.py shell
   $ docker compose exec openkat python manage.py createsuperuser

Stop OpenKAT
************

.. code-block:: bash

   $ docker compose down

Start OpenKAT
*************

.. code-block:: bash

   $ docker compose up -d

Resetting the Installation
===========================

Clean Everything
****************

Remove all data and start fresh:

.. code-block:: bash

   $ make reset

This keeps your ``.env`` file. To regenerate credentials, delete ``.env`` first.

Clean Only Objects
******************

Clear the object database but keep users and organizations:

.. code-block:: bash

   $ make object-clean

This is useful when you want to start scanning from scratch.

Updating OpenKAT
================

To update to the latest version:

.. code-block:: bash

   $ git pull
   $ docker compose pull
   $ docker compose up -d
   $ docker compose exec openkat python manage.py migrate

Troubleshooting
===============

Port 8000 Already in Use
*************************

.. code-block:: bash

   # Find what's using port 8000
   $ lsof -i :8000

   # Kill the process or change port in docker-compose.yml

Containers Won't Start
**********************

.. code-block:: bash

   # Clean and rebuild
   $ make reset

   # Check Docker disk space
   $ docker system df
   $ docker system prune -a  # Free space

Permission Errors
*****************

On Linux, ensure your user is in the docker group:

.. code-block:: bash

   $ sudo usermod -aG docker $USER
   $ newgrp docker

Out of Memory
*************

Increase Docker memory allocation:

- **Docker Desktop**: Preferences → Resources → Memory (minimum 8 GB)
- **Linux**: Configure Docker daemon memory limits

See :doc:`debugging-troubleshooting` for more solutions.

Next Steps
==========

Development
***********

For development work, see :doc:`developer-environment` for:

- Code editing workflow
- Running tests
- Debugging
- Creating plugins
- Contributing guidelines

Production Deployment
*********************

For production installations, see :doc:`production-deployment` for:

- Production configuration
- SSL/TLS setup
- Reverse proxy configuration
- Monitoring and backups
- Security hardening

Learning OpenKAT
****************

- Complete the onboarding wizard at http://localhost:8000
- Read the :doc:`../user-manual/index`
- Try adding objects and running scans
- Explore the :doc:`../developer-documentation/index`

Advanced Topics
===============

Custom Configuration
********************

Override settings by editing ``.env``:

.. code-block:: bash

   $ vim .env
   # Make changes
   $ docker compose restart

Specific Builds
***************

The Makefile has targets for specific operations:

.. code-block:: bash

   $ make frontend    # Rebuild frontend only
   $ make messages    # Compile translations
   $ make static      # Collect static files

See the `Makefile <https://github.com/minvws/nl-kat-coordination/blob/main/Makefile>`_ for all targets.

Observability
*************

Enable Jaeger tracing for debugging:

.. code-block:: bash

   $ export COMPOSE_PROFILES=jaeger
   $ docker compose up -d
   # Access Jaeger UI at http://localhost:16686

Enable Pyroscope profiling:

.. code-block:: bash

   $ docker compose --profile monitoring up -d
   # Access Pyroscope at http://localhost:4040
   # Access Grafana at http://localhost:4000

Getting Help
============

- **Full Developer Guide**: :doc:`developer-environment`
- **Installation Guide**: :doc:`install`
- **Troubleshooting**: :doc:`debugging-troubleshooting`
- **FAQ**: :doc:`faq`
- **GitHub Issues**: https://github.com/minvws/nl-kat-coordination/issues
- **Documentation**: https://docs.openkat.nl
