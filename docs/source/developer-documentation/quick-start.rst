===========
Quick Start
===========

Get started with OpenKAT v2 development in minutes.

Prerequisites
*************

- Docker and Docker Compose
- Git
- Make
- 8GB RAM minimum
- 20GB disk space

Installation
************

This quick start guide will help you get OpenKAT v2 started using Docker. OpenKAT v2 is a monolithic Django application, making setup much simpler than v1.

**Note:** Do *not* install Docker from the default Ubuntu repositories. Use the official Docker installation to get the latest version.

#. Follow the Docker installation steps: `Docker Installation <https://docs.docker.com/engine/install/>`_

#. Follow the post-installation steps to run Docker as non-root: `Post-installation <https://docs.docker.com/engine/install/linux-postinstall/>`_

#. Install make (if not already installed):

   .. code-block:: bash

      sudo apt install make

#. Clone the repository:

   .. code-block:: bash

      git clone https://github.com/minvws/nl-kat-coordination.git
      cd nl-kat-coordination

#. Start the development environment:

   .. code-block:: bash

      make kat

   This command will:

   - Generate ``.env`` file with random credentials
   - Build Docker images
   - Start all containers (openkat, postgres, xtdb, redis, worker)
   - Run database migrations
   - Create superuser
   - Seed initial data

   **Tip:** If errors occur, run ``make kat`` again. The process is idempotent.

#. Get your credentials:

   .. code-block:: bash

      cat .env | grep DJANGO_SUPERUSER
      # DJANGO_SUPERUSER_EMAIL=superuser@localhost
      # DJANGO_SUPERUSER_PASSWORD=GENERATED_PASSWORD

#. Access OpenKAT:

   - Web interface: http://localhost:8000/en/login
   - Admin interface: http://localhost:8000/admin/
   - Login with credentials from step 6

#. Follow the onboarding wizard to create your first organization and start scanning

Services Running
****************

After installation, these Docker containers will be running:

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
     - Bitemporal object database
     - 5433
   * - redis
     - Celery message broker
     - 6379
   * - worker
     - Celery task worker
     - N/A

First Steps
***********

After logging in:

#. **Create Objects:**

   - Go to http://localhost:8000/en/objects/hostname/add/
   - Add a hostname (e.g., ``example.com`` in network ``internet``)

#. **Schedule a Plugin:**

   - Navigate to http://localhost:8000/en/plugins/
   - Find a plugin (e.g., "DNS Records")
   - Click "Schedule" and configure

#. **View Tasks:**

   - Check http://localhost:8000/en/tasks/ to see task execution

#. **View Results:**

   - Return to your hostname to see discovered objects
   - Check http://localhost:8000/en/objects/finding/ for findings

Development Commands
********************

**View logs:**

.. code-block:: bash

   docker compose logs -f openkat
   docker compose logs -f worker

**Run management commands:**

.. code-block:: bash

   docker compose exec openkat python manage.py COMMAND

**Access databases:**

.. code-block:: bash

   # PostgreSQL
   docker compose exec postgres psql -U postgres postgres

   # XTDB (through the postgres container as this is guaranteed to have psql installed)
   docker compose exec postgres psql -h xtdb -d xtdb

**Run tests:**

.. code-block:: bash

   make utest

Resetting the Environment
**************************

**Clean everything:**

.. code-block:: bash

   make reset  # Removes all containers and volumes, create a fresh installation

**Clean only objects:**

.. code-block:: bash

   make object-clean  # Clears XTDB but keeps users/orgs

Next Steps
**********

- Read :doc:`v2-architecture` to understand the system design
- Explore :doc:`models` to learn about data structures
- Check :doc:`tasks` for task scheduling
- Review :doc:`plugins` for plugin development
- See :doc:`business-rules` for finding detection

Troubleshooting
***************

**Containers won't start:**

.. code-block:: bash

   make reset

**Database connection errors:**

.. code-block:: bash

   docker compose restart postgres xtdb
   docker compose exec openkat python manage.py migrate

**Celery tasks not running:**

.. code-block:: bash

   docker compose logs worker
   docker compose restart worker

Getting Help
************

- Documentation: https://docs.openkat.nl
- GitHub Issues: https://github.com/minvws/nl-kat-coordination/issues
- Community: https://openkat.nl
