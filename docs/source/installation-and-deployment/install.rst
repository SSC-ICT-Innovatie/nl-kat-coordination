============================
How to Install OpenKAT v2
============================

OpenKAT v2 is a monolithic Django application that is significantly simpler to install than v1. This guide covers the different installation methods available.

Installation Options
====================

Development Environment
***********************

For development, testing, or evaluation purposes, use the simple Docker-based setup:

.. code-block:: bash

   $ git clone https://github.com/minvws/nl-kat-coordination.git
   $ cd nl-kat-coordination
   $ make kat

This is the recommended way to get started quickly. See :doc:`developer-environment` for details.

Production Deployment
*********************

For production installations, use the Docker Compose setup with proper configuration. See :doc:`production-deployment` for details.

Pre-built Docker images are available on the GitHub Container Registry and are the recommended deployment method for v2.

Alternative Deployments
***********************

Community-maintained deployment options:

Kubernetes
  Kubernetes files: https://gitlab.com/digilab.overheid.nl/platform/helm-charts/openkat/

Ansible
  Ansible playbooks: https://github.com/sigio/openkat-ansible

Quick Start
===========

The fastest way to get OpenKAT running is:

.. code-block:: bash

   # Clone repository
   $ git clone https://github.com/minvws/nl-kat-coordination.git
   $ cd nl-kat-coordination

   # Start all services
   $ make kat

This command will:

1. Generate a ``.env`` file with random credentials
2. Build Docker images
3. Start all containers (openkat, postgres, xtdb, redis, worker)
4. Run database migrations
5. Create a superuser account
6. Seed initial data

Access OpenKAT at http://localhost:8000 with credentials from the ``.env`` file.

System Requirements
===================

Minimum Requirements
********************

For development and testing:

- **CPU**: 2 cores minimum, 4 cores recommended
- **RAM**: 8 GB minimum, 16 GB recommended
- **Disk**: 25 GB minimum, 50 GB recommended
- **OS**: Linux (Ubuntu 22.04+ recommended), macOS, or Windows with WSL2

The disk space is primarily used by:

- XTDB database (object storage)
- PostgreSQL database (operational data)
- Docker images and containers
- Plugin data and files

Production Requirements
***********************

For production deployments:

- **CPU**: 4+ cores (scales with workload)
- **RAM**: 16 GB minimum, 32 GB+ recommended
- **Disk**: 100 GB+ (depends on data volume)
- **Network**: Stable internet connection for plugin operations

Services Overview
=================

OpenKAT v2 consists of these Docker containers:

.. list-table::
   :header-rows: 1
   :widths: 20 40 20 20

   * - Container
     - Purpose
     - Port
     - Scaling
   * - openkat
     - Django application (web + API)
     - 8000
     - Can be horizontally scaled
   * - postgres
     - Operational database
     - 5432
     - Single instance (can use managed PostgreSQL)
   * - xtdb
     - Bitemporal object database
     - 5433
     - Single instance (can cluster)
   * - redis
     - Celery message broker
     - 6379
     - Single instance (can cluster)
   * - worker
     - Celery task worker
     - N/A
     - Can be horizontally scaled

Architecture Simplification
===========================

Compared to v1, OpenKAT v2 has a much simpler architecture:

**v1 Architecture** (6+ microservices):

- Rocky (web interface)
- Octopoes (object management)
- Boefjes (plugin execution)
- Mula (scheduler)
- Bytes (file storage)
- Katalogus (plugin registry)
- Plus separate workers and services

**v2 Architecture** (1 monolithic app):

- Single Django application
- Integrated plugin system
- Built-in task scheduling (Celery)
- Simpler deployment and operations

This simplification makes v2 much easier to:

- Install and configure
- Deploy to production
- Monitor and debug
- Upgrade and maintain
- Scale horizontally

Data Storage
============

OpenKAT v2 uses two databases:

PostgreSQL
**********

Stores operational data:

- User accounts and authentication
- Organizations and members
- Tasks and schedules
- Plugin configurations
- Business rules
- Settings

Can be backed up using standard PostgreSQL tools (``pg_dump``).

XTDB
****

Stores object data with full history:

- Network objects (hostnames, IPs, etc.)
- DNS records
- Findings
- Object-organization relationships

XTDB provides bitemporal storage, enabling:

- Complete audit trail
- Time-travel queries
- Point-in-time recovery

Backup both databases for complete system recovery.

Initial Setup
=============

After installation, you'll need to:

1. **Access the Application**

   Navigate to http://localhost:8000 (or your configured domain)

2. **Login**

   Use credentials from ``.env``:

   - Email: ``DJANGO_SUPERUSER_EMAIL``
   - Password: ``DJANGO_SUPERUSER_PASSWORD``

3. **Complete Onboarding**

   The first login will guide you through:

   - Creating an organization
   - Setting up indemnification
   - Configuring scan levels
   - Adding your first objects

4. **Add Objects**

   Start by adding objects to scan:

   - Hostnames
   - IP addresses
   - Networks

5. **Schedule Plugins**

   Enable plugins to scan your objects:

   - DNS records
   - SSL certificates
   - Open ports
   - Security headers

See the :doc:`../user-manual/getting-started/onboarding` for detailed instructions.

Upgrading from v1
=================

OpenKAT v2 represents a significant architectural change from v1. **Direct upgrades are not supported.**

For organizations running v1:

1. Deploy v2 as a new installation
2. Migrate data manually or re-scan
3. Update any custom integrations
4. Train users on v2 interface (similar but streamlined)

The data models have changed significantly, so v1 databases cannot be directly migrated to v2.

Next Steps
==========

- **Development**: See :doc:`developer-environment`
- **Production**: See :doc:`production-deployment`
- **Security**: See :doc:`hardening`
- **User Guide**: See :doc:`../user-manual/index`
- **Developer Guide**: See :doc:`../developer-documentation/index`

Getting Help
============

- **Documentation**: https://docs.openkat.nl
- **GitHub Issues**: https://github.com/minvws/nl-kat-coordination/issues
- **Community**: https://openkat.nl

For installation issues, check :doc:`debugging-troubleshooting` and :doc:`faq`.
