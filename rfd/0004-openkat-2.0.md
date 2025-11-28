---
authors: Jeroen Dekkers <@dekkers>, Donny Peeters <@donnype>
state: implemented
discussion:
labels: Architecture, Data Models
---

# RFD 0004: OpenKAT 2.0

## Introduction

XTDB 2 has been released with a lot of big improvements over XTDB 1. XTDB 2 is not compatible with XTDB 1 however, XTDB
2 uses SQL instead of datalog and you connect over the pgwire protocol. This means that we need to rewrite big parts of
OpenKAT. We take this opportunity to do a general review of the OpenKAT architecture.

## Current architecture

The code consists of 5 modules that were previously in separate git
repositories and are still treated as standalone modules in the current shared git repository.
At https://docs.openkat.nl/basics/modules.html you can see a description of the different modules. Except for one
component, no code is shared between these modules.

Each module forms the basis for one or more services. In total, there are 9 services running and communicating with each
other. There are also 4 separate PostgreSQL databases, 1 XTDB database and a RabbitMQ instance. OpenKAT uses Django, the
other modules use FastAPI and SQLAlchemy, and Octopoes also uses Celery.

Having so many services with their own database means that data that is sometimes needed together is spread across
different services and databases. There is also duplication and it is difficult to guarantee that the different
databases are consistent with each other: when a new organization is created, we must make a call to two other services;
when new boefjes are started, the scheduler currently learns about this by querying an endpoint in the KATalogus every
minute; when new objects are found, the scheduler learns about this via RabbitMQ. Additionally, error handling when a
service is unavailable or problematic is complex and error-prone. This is a recurring source of bugs.

The many moving parts also give a lot of problems for people who want to run OpenKAT and are not familiar with all the
details. And even for the developers of OpenKAT it is quite often time consuming to help users of OpenKAT figure out
what goes wrong in their installation.

The duplication also has a negative impact on scalability. For example, every boefje and normalizer task is stored in
the scheduler's database, but for each task, the result is also stored in the bytes database. Part of the data is
therefore stored twice. In other cases, not all data is available and must be requested from another service, which is
slower than if this could be retrieved directly via one database query from one database.

Furthermore, some functionality in OpenKAT is also designed very complex. For example, reports are stored as
thousands of subreports, one for each selected subreport type and each object. However, this could be much simpler
by just storing the report as one object. The service that creates reports also has no direct connection to the
(correct) database, so all aggregations are handwritten and therefore very slow.

## Proposal: Simplification of architecture

We think it is necessary to simplify things so that OpenKAT becomes easier to develop, maintain and run.
The migration of OpenKAT to XTDB 2 is a good moment to do this because a big part of OpenKAT needs to be rewritten
anyway. We are currently planning for the following changes for OpenKAT 2.0:

- XTDB1 will be replaced with XTDB2. Because XTDB2 uses SQL instead of Datalog, we will use the Django ORM for all XTDB2
  objects.
- The four different PostgreSQL databases will be merged into one PostgreSQL database. The Django ORM is used for all
  access.
- All different modules will be merged into one whole where all code is shared
- All code will directly use the database instead of having to communicate via HTTP and RabbitMQ.
- Instead of the Bytes service that stores files on the disk we will use standard S3 object storage and have the code
  communicate directly with S3
- All the different task runners and schedulers (boefjes, normalizers, bits, reports) will be merged into one runner and
  PostgreSQL will be used for everything. RabbitMQ will be removed. Investigate whether we can use django-tasks or need
  to define our own Task model.
- Boefjes/normalizers need to be changed to be able to have a single run for multiple or all objects of a certain type.
- Reports will be stored as one object
- We plan to keep the current user interface as much as possible, but we can simplify the Django view code because we
  can use the Django ORM instead of having to create fake querysets that use http calls and complex error handling.
  Dynamic parts of the user interface will be done with HTMX.

## Upcoming RFDs

The plan is to create RFDs for changes on (some of) the following topics as well:

1. Raw Data Storage
2. The KATalogus database schema
3. Deletion Propagation
4. Boefje, Normalizers and other task flows
5. Scheduling
6. OCI Images
7. Reporting and Dashboarding
8. Scan Level Recalculation
9. Timestamping
10. Octopoes models for XTDB 2.0
