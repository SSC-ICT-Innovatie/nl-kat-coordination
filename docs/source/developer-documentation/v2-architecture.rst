OpenKAT V2 Architecture
=======================

Overview
--------

OpenKAT v2 represents a significant architectural shift from v1. The system has been consolidated from a microservices architecture into a monolithic Django application, simplifying deployment, development, and operations.

Key Components
--------------

Django Application
******************

The core of OpenKAT v2 is a single Django application that provides:

- **Web Interface**: User-facing pages for managing scans, viewing findings, and generating reports
- **REST API**: API endpoints for object management and task operations
- **Admin Interface**: Django admin for user and organization management
- **Object Models**: Django ORM models for all system entities

Databases
*********

OpenKAT v2 uses two databases:

1. **PostgreSQL** (``:5432``): Operational database for:

   - User accounts and authentication
   - Organization and member management
   - Task tracking and scheduling
   - Plugin configurations and schedules
   - Business rules
   - Settings and preferences

2. **XTDB** (``:5433``): Bitemporal document database for:

   - Objects (Hostnames, IP addresses, DNS records, etc.)
   - Object history and audit trail
   - Temporal queries
   - Multi-organization data isolation

Task Processing
***************

**Celery Worker** with **Redis** (``:6379``):

- Asynchronous task execution
- Plugin running
- Scheduled scans
- Report generation
- Business rule evaluation

Architecture Diagram
--------------------

::

   graph TD
       User[User Browser] --> Django[Django Application :8000]
       Django --> PostgreSQL[(PostgreSQL :5432)]
       Django --> XTDB[(XTDB :5433)]
       Django --> Redis[(Redis :6379)]
       Worker[Celery Worker] --> Redis
       Worker --> PostgreSQL
       Worker --> XTDB
       Worker --> Plugins[Plugin Execution]

Key Features
------------

Object Sets
***********

Object sets allow filtering and grouping objects by type (e.g., hostnames, IP addresses). They enable:

- Filtered list views
- Targeted plugin scheduling
- Granular scan control
- Organization-specific object management

Task System
***********

Tasks are managed through Django models and executed by Celery:

- Plugin tasks
- Scheduled tasks via ``Schedule`` model
- Task-to-object mapping via ``ObjectTask`` model
- Status tracking and history

Business Rules
**************

SQL-based finding detection:

- Rules defined as SQL queries
- Executed periodically
- Create ``Finding`` objects
- Inverse queries for cleanup

Plugin System
*************

Plugins are containerized applications that:

- Scan objects and produce data
- Store data as ``File`` objects
- Create new objects via API with ``task_id`` tracking
- Can be scheduled on object sets
- Support file uploads for custom templates

Multi-Organization Support
***************************

- Organization-based access control
- Object-organization many-to-many relationships
- User permissions per organization

Data Flow
---------

1. **User adds object** (e.g., Hostname)
2. **User schedules plugin** on an object set
3. **Schedule creates tasks** for matching objects
4. **Celery worker picks up task**
5. **Plugin executes** and stores results as files
6. **Plugin creates new objects** via API (with ``task_id``)
7. **ObjectTask records** link tasks to created objects
8. **Business rules** run periodically to create findings
9. **User views results** in web interface

Comparison with V1
------------------

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Aspect
     - V1 (Microservices)
     - V2 (Monolith)
   * - Architecture
     - 6+ separate services
     - Single Django app
   * - Databases
     - XTDB, PostgreSQL (multiple)
     - PostgreSQL + XTDB
   * - Task Queue
     - RabbitMQ + custom workers
     - Celery + Redis
   * - API
     - Multiple FastAPI services
     - Single Django REST API
   * - Deployment
     - Docker Compose (complex)
     - Docker Compose (simple)
   * - Development
     - Multiple processes
     - Single repo/process
   * - OOI Model
     - Complex graph model
     - Simpler Django models
   * - Scheduling
     - Mula (separate service)
     - Django + Celery
   * - Data Model
     - OOI classes
     - Concrete Django models

Development Environment
-----------------------

To run the development environment:

.. code-block:: shell

   $ make kat

This starts:

- ``openkat`` container (Django + Celery)
- ``postgres`` container
- ``xtdb`` container
- ``redis`` container
- ``worker`` container (Celery worker)

All services run together, making development simpler than v1's multi-service architecture.

Benefits of V2 Architecture
----------------------------

1. **Simplified Deployment**: Single application to deploy
2. **Easier Development**: One codebase, standard Django patterns
3. **Better Performance**: No network overhead between services
4. **Simplified Testing**: Test entire stack in one process
5. **Reduced Complexity**: Fewer moving parts
6. **Standard Django**: Leverage Django ecosystem and tooling
7. **Easier Debugging**: Single application to debug
8. **Simpler Data Model**: Django ORM instead of complex graph queries

Migration from V1
-----------------

Organizations migrating from v1 should note:

- Data models have changed significantly
- APIs have changed (now Django REST framework)
- Deployment is simpler (fewer containers)
- Plugin system is integrated (not separate workers)
- No separate Octopoes/Mula/Boefjes services
