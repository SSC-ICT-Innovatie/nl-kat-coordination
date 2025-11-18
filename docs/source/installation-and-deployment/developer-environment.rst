=======================
Developer Environment
=======================

This guide explains how to set up a local development environment for OpenKAT v2.

Overview
========

OpenKAT v2 uses Docker for local development, making setup simple and consistent across different operating systems. The development environment includes all services needed to run OpenKAT locally.

Prerequisites
=============

Required Software
*****************

- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Git**
- **Make**

System Requirements
*******************

- **CPU**: 2 cores minimum, 4 recommended
- **RAM**: 8 GB minimum, 16 GB recommended
- **Disk**: 25 GB free space
- **OS**: Linux, macOS, or Windows with WSL2

Installation
============

1. Install Docker
*****************

**Linux (Ubuntu/Debian)**:

.. code-block:: bash

   # Remove old versions
   $ sudo apt remove docker docker-engine docker.io containerd runc

   # Install Docker from official repository
   $ curl -fsSL https://get.docker.com -o get-docker.sh
   $ sudo sh get-docker.sh

   # Add your user to docker group
   $ sudo usermod -aG docker $USER
   $ newgrp docker

See https://docs.docker.com/engine/install/ for other Linux distributions.

**macOS**:

Download and install Docker Desktop from https://www.docker.com/products/docker-desktop/

**Windows**:

1. Enable WSL2: https://docs.microsoft.com/en-us/windows/wsl/install
2. Install Docker Desktop for Windows: https://www.docker.com/products/docker-desktop/

2. Install Additional Tools
****************************

**Ubuntu/Debian**:

.. code-block:: bash

   $ sudo apt install make git

**macOS**:

.. code-block:: bash

   $ brew install make git

**Windows (WSL2)**:

.. code-block:: bash

   $ sudo apt install make git

3. Clone Repository
*******************

.. code-block:: bash

   $ git clone https://github.com/minvws/nl-kat-coordination.git
   $ cd nl-kat-coordination

4. Start Development Environment
*********************************

.. code-block:: bash

   $ make kat

This single command will:

1. Generate a ``.env`` file with random credentials
2. Build all Docker images
3. Start all containers:

   - **openkat** - Django application (:8000)
   - **postgres** - PostgreSQL database (:5432)
   - **xtdb** - XTDB database (:5433)
   - **redis** - Redis message broker (:6379)
   - **worker** - Celery worker

4. Run database migrations
5. Create a superuser account
6. Seed initial data (network, plugins, etc.)

**Note**: The first run takes 5-10 minutes to build images. Subsequent runs are much faster.

If you encounter errors, run ``make kat`` again - the process is idempotent.

5. Access OpenKAT
*****************

Once the setup completes:

1. Open http://localhost:8000 in your browser
2. Get credentials from ``.env``:

   .. code-block:: bash

      $ cat .env | grep DJANGO_SUPERUSER
      DJANGO_SUPERUSER_EMAIL=superuser@localhost
      DJANGO_SUPERUSER_PASSWORD=GENERATED_PASSWORD

3. Login and complete the onboarding wizard

Services
========

After running ``make kat``, these services are available:

.. list-table::
   :header-rows: 1

   * - Service
     - URL/Port
     - Purpose
   * - Web Interface
     - http://localhost:8000
     - Main application
   * - Admin Interface
     - http://localhost:8000/admin/
     - Django admin
   * - API
     - http://localhost:8000/api/
     - REST API
   * - PostgreSQL
     - localhost:5432
     - Operational database
   * - XTDB
     - localhost:5433
     - Object database
   * - Redis
     - localhost:6379
     - Message broker

Development Workflow
====================

The OpenKAT container uses volume mounts, so code changes are reflected immediately without rebuilding.

Making Code Changes
*******************

Python code changes are auto-reloaded by Django:

.. code-block:: bash

   # Edit any Python file
   $ vim openkat/views.py

   # Django automatically reloads - no restart needed
   # Check logs to see reload confirmation
   $ docker compose logs -f openkat

For model changes, run migrations:

.. code-block:: bash

   $ docker compose exec openkat python manage.py makemigrations
   $ docker compose exec openkat python manage.py migrate

Frontend Changes
****************

For frontend asset changes:

.. code-block:: bash

   # Rebuild frontend
   $ make frontend

   # Collect static files
   $ docker compose exec openkat python manage.py collectstatic --noinput

Running Tests
*************

.. code-block:: bash

   # All tests
   $ make utest

   # Specific test file
   $ python -m pytest tests/test_models.py

   # Specific test function
   $ python -m pytest tests/test_models.py::test_hostname_creation

   # With coverage
   $ python -m pytest --cov=openkat tests/

Database Access
***************

**PostgreSQL**:

.. code-block:: bash

   # Connect to PostgreSQL
   $ docker compose exec postgres psql -U postgres postgres

.. code-block:: sql

   -- Run SQL queries
   SELECT COUNT(*) FROM auth_user;

**XTDB**:

.. code-block:: bash

   # Connect to XTDB
   $ docker compose exec xtdb psql -U xtdb -p 5433 xtdb

.. code-block:: sql

   -- Query objects
   SELECT * FROM public.objects_hostname LIMIT 10;

Viewing Logs
************

.. code-block:: bash

   # All services
   $ docker compose logs -f

   # Specific service
   $ docker compose logs -f openkat
   $ docker compose logs -f worker
   $ docker compose logs -f postgres

   # Filter for errors
   $ docker compose logs | grep ERROR

   # Follow logs from specific time
   $ docker compose logs --since 5m -f openkat

Running Management Commands
***************************

.. code-block:: bash

   # Django management commands
   $ docker compose exec openkat python manage.py COMMAND

   # Examples:
   $ docker compose exec openkat python manage.py shell
   $ docker compose exec openkat python manage.py createsuperuser
   $ docker compose exec openkat python manage.py seed
   $ docker compose exec openkat python manage.py migrate

Debugging
=========

Interactive Debugging
*********************

Add breakpoints in your code:

.. code-block:: python

   def my_view(request):
       import pdb; pdb.set_trace()  # Breakpoint
       # Your code here

Attach to container to use the debugger:

.. code-block:: bash

   $ docker attach nl-kat-coordination_openkat_1

Use ``Ctrl+P, Ctrl+Q`` to detach without stopping the container.

VS Code Debugging
*****************

Add to ``.vscode/launch.json``:

.. code-block:: json

   {
       "version": "0.2.0",
       "configurations": [
           {
               "name": "Django: Debug",
               "type": "python",
               "request": "attach",
               "pathMappings": [
                   {
                       "localRoot": "${workspaceFolder}",
                       "remoteRoot": "/app"
                   }
               ],
               "port": 5678,
               "host": "localhost"
           }
       ]
   }

Install debugpy in the container and start with remote debugging enabled.

Common Issues
=============

Port Already in Use
*******************

If port 8000 is already in use:

.. code-block:: bash

   # Find process using port
   $ lsof -i :8000

   # Kill the process or change port in docker-compose.yml

Database Connection Errors
**************************

.. code-block:: bash

   # Restart databases
   $ docker compose restart postgres xtdb

   # Check database logs
   $ docker compose logs postgres

   # Verify connection settings in .env

Containers Won't Start
**********************

.. code-block:: bash

   # Clean everything and start fresh
   $ make clean
   $ make kat

   # If still failing, check Docker resources
   $ docker system df
   $ docker system prune  # Free up space

Out of Memory
*************

.. code-block:: bash

   # Check Docker memory allocation
   # On Docker Desktop: Preferences -> Resources -> Memory
   # Increase to at least 8 GB

   # Or reduce worker concurrency in .env:
   CELERY_WORKER_CONCURRENCY=2

Resetting the Environment
==========================

Clean Everything
****************

Remove all containers, volumes, and build artifacts:

.. code-block:: bash

   $ make clean
   $ make kat  # Fresh installation

Keep `.env` file - it won't be regenerated if it exists.

Clean Only Objects
******************

Clear XTDB database but keep users and organizations:

.. code-block:: bash

   $ make object-clean

This is useful when you want to start scanning from scratch without losing user accounts.

Advanced Development
====================

Custom Plugins
**************

Create a new plugin:

.. code-block:: bash

   # Create plugin directory
   $ mkdir -p plugins/plugins/kat_myplugin

   # Create plugin files
   $ touch main.py description.md

   # Add plugin definition to plugins/plugins/plugins.json

See :doc:`../developer-documentation/plugins` for details.

Running Specific Services
*************************

Run only specific services:

.. code-block:: bash

   $ docker compose up -d postgres xtdb redis
   $ python manage.py runserver  # Run Django locally

This is useful for debugging Django without Docker overhead.

Environment Variables
*********************

Override environment variables:

.. code-block:: bash

   # Create .env.local (gitignored)
   $ cat > .env.local << EOF
   DJANGO_DEBUG=True
   CELERY_WORKER_CONCURRENCY=1
   LOG_LEVEL=DEBUG
   EOF

   # Docker Compose automatically loads .env.local

Performance Tips
================

1. **Use SSD**: Docker volumes perform better on SSD
2. **Allocate Resources**: Give Docker Desktop at least 8 GB RAM and 4 CPUs
3. **Prune Regularly**: Run ``docker system prune -a`` to free space
4. **Volume Caching**: Use delegated/cached volume mounts on macOS
5. **Reduce Worker Concurrency**: Lower ``CELERY_WORKER_CONCURRENCY`` if memory-constrained

Next Steps
==========

Now that your development environment is running:

1. **Complete Onboarding**: Follow the wizard at http://localhost:8000
2. **Add Test Data**: Create objects to scan
3. **Explore Code**: Review :doc:`../developer-documentation/index`
4. **Make Changes**: Start contributing!
5. **Run Tests**: Ensure your changes don't break anything

See Also
========

- :doc:`../developer-documentation/quick-start` - Developer quick start
- :doc:`../developer-documentation/models` - Data models
- :doc:`../developer-documentation/tasks` - Task system
- :doc:`../developer-documentation/plugins` - Plugin development
- :doc:`debugging-troubleshooting` - Troubleshooting guide

Getting Help
============

- **Documentation**: https://docs.openkat.nl
- **GitHub Issues**: https://github.com/minvws/nl-kat-coordination/issues
- **Discussions**: https://github.com/minvws/nl-kat-coordination/discussions
