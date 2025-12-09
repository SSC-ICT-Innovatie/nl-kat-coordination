# Installation

## Setting up a Development Environment

To set up a local development instance of OpenKAT, run

```shell
$ make kat
```

This should download, build and start the necessary containers, and seed relevant data.
An error during installation is usually solved by an additional (idempotent) `make kat`.
This should take no longer than a minute or two.
All necessary credentials are generated in a `.env` file.

## Development Services

After installation, the following services should be running:

| Container        | Usage                                     |
| ---------------- | ----------------------------------------- |
| openkat (:8000)  | Django Application                        |
| postgres (:5432) | Operational Database                      |
| xtdb (:5433)     | Bitemporal Document Database              |
| worker (no port) | Celery Worker                             |
| redis (:6379)    | Celery Message Broker and Caching/Locking |

Again, the initial credentials are stored in the `.env` file. In particular,
`DJANGO_SUPERUSER_EMAIL` and `DJANGO_SUPERUSER_PASSWORD` can be used to log in at http://localhost:8000/en/login/.
Note that to inspect the data in XTDB, a regular psql client can be used to connect to the `xtdb` database.

## Delete All Data

To start with a fresh installation again, you can run

```shell
$ make reset
```

This cleans out all data and rebuilds the frontend. The only thing that persists is your `.env` file.
To get a new `.env` file, just remove it and run `make kat`. To only clean out the objects database (XTDB), run:

```shell
$ make object-clean
```

## Organizations and permissions

To add new organizations, users and organization members, currently only the [admin page](http://localhost:8000/en/admin/) can be used.

## Scanning

To perform a first scan, you need to:

- Add objects (such as [hostnames](http://localhost:8000/en/objects/hostname/add/) or [ipaddresses]
  (http://localhost:8000/en/objects/ipaddress/add/))
- Raise their scan level on their detail page (or through the overview using the `Actions` dropdown)
- Schedule a plugin on the [plugin page](http://localhost:8000/en/plugins/)

Or directly trigger a scan from the [plugin page](http://localhost:8000/en/plugins/) once you added an object by
pressing `Run`, so you don't have to wait on the scheduling to create a new task.

## Tasks and Schedules

To see if a task has run, the [task page](http://localhost:8000/en/tasks/) lists all tasks and their status.
If you don't see any tasks, make sure the `worker` logs show that tasks have been picked up and make sure the user
had the "view*task" permission. Tasks will be created automatically through schedules if there are objects that
have a sufficient scan level and haven't been scanned recently in the required interval. Schedules are created per
plugin on an \_object set*

## Object Sets

The [object sets](http://localhost:8000/en/object-sets/) are a subset of objects of the same type, i.e. hostnames or
ipaddresses currently. They can be used to filter the ipaddress and hostname pages and schedule a plugin for a
specific subset of data. As typically the object type and scan level is not enough granularity to define how and
when certain objects should be scanned, this is a particularly useful feature for larger installations.

## Files

Plugins produce files that can be parsed. Files can be uploaded and used in plugins as well by pressing `Add Plugin`
on the overview page. The `{file/1}` like argument placeholder in the plugin definition will be replaced at runtime
by a downloaded path to the particular file. This can be useful for e.g. creating a Nuclei plugin with a custom
template.

## Business Rules

The business rules can be used to create Findings using SQL. These will be tricky to tune without a lot of SQL
experience and knowledge of the data model, but can be turned off as well. The inverse query is responsible for
cleaning up invalid findings.

## Findings

The findings end up in the [Findings overview](http://localhost:8000/en/objects/finding/).
This page is a lot like the old findings page, but here you can now filter the Findings efficiently.

## Reports

A rudimentary version of reporting has been implemented where we give an overview of the objects in the database (XTDB).
Reports can be scheduled and created ad hoc, given a set of organizations, finding types and an object set.
