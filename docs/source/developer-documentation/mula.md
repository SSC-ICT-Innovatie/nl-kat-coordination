# Scheduler

## Purpose

The scheduler is responsible for scheduling the execution of tasks. The
execution of those tasks are being prioritized / scored by a ranker. The tasks
are then pushed onto a priority queue.

Within the project of KAT, the scheduler is tasked with scheduling boefje,
normalizer, and report tasks.

## Architecture

See
[architecture](https://github.com/minvws/nl-kat-coordination/tree/main/mula/docs/architecture.md)
document for the architecture and the
[extending](https://github.com/minvws/nl-kat-coordination/tree/main/mula/docs/extending.md)
document for the extending the scheduler with your own custom schedulers, and
rankers.

### Stack, packages and libraries

| Name       | Version   | Description         |
| ---------- | --------- | ------------------- |
| Python     | ^3.10     |                     |
| FastAPI    | ^0.115.12 | Used for api server |
| SQLAlchemy | ^2.0.23   |                     |
| pydantic   | ^2.11.3   |                     |
| uvicorn    | ^0.29.0   |                     |

The scheduler uses PostgreSQL as its database.

### External services

The scheduler interfaces with the following services:

| Service     | Usage                                                                   |
| ----------- | ----------------------------------------------------------------------- |
| [Octopoes]  | Retrieving random OOI's of organizations                                |
| [Katalogus] | Used for referencing available plugins and organizations                |
| [Bytes]     | Retrieve last run boefje for organization and OOI                       |
| [RabbitMQ]  | Used for retrieving scan profile changes, and created raw data in bytes |

### Project structure

```
.
├── docs/                           # additional documentation
├── scheduler/                      # scheduler python module
│   ├── clients/                    # external service clients
│   │   ├── amqp/                   # amqp clients
│   │   ├── http/                   # http api clients
│   │   ├── __init__.py
│   │   ├── connector.py
│   │   └── errors.py
│   ├── config/                     # application settings configuration
│   ├── context/                    # shared application context
│   ├── models/                     # internal model definitions
│   ├── schedulers/                 # schedulers
│   │   ├── queue/                  # priority queue implementation
│   │   ├── rankers/                # rankers for tasks
│   │   ├── schedulers/
│   │   │   ├── __init__.py
│   │   │   ├── boefje.py           # boefje scheduler implementation
│   │   │   ├── normalizer.py       # normalizer scheduler implementation
│   │   │   └── report.py           # report scheduler implementation
│   │   ├── __init__.py
│   │   └── scheduler.py            # abstract base class for schedulers
│   ├── storage/                    # data abstraction layer
│   ├── server/                     # http rest api server
│   ├── utils/                      # common utility functions
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py                      # openkat scheduler app implementation
│   └── version.py                  # version information
└─── tests/                         # test suite
```

## Running / Developing

Typically the scheduler will be run from the overarching
[nl-kat-coordination](https://github.com/minvws/nl-kat-coordination) project.
When you want to run and the scheduler individually you can use the following
setup. We are using docker to setup our development environment, but you are
free to use whatever you want.

### Prerequisites

By the use of environment variables we load in the configuration of the
scheduler. See the environment settings section under Installation and Deployment for more information.

### Running

```
# Build and run the scheduler in the background
$ docker compose up --build -d scheduler
```

### Migrations

Creating a migration:

```
# Run migrations
make revid=0008 m="add_task_schedule" migrations
```

Sometimes it is helpful to run the migrations in a clean environment:

```
docker system prune
docker volume prune --force --all
```

## Testing

```
# Run integration tests
$ make itest

# Run unit tests
$ make utest

# Individually test a file
$ make file=test_file.py utest

# Individually test a function
$ make file=test_file.py function='test_function' utest
```

## Scripts

The scheduler comes with a few scripts that can be used to interact with the
scheduler. These scripts are located in the `scripts/` directory and can be
check its documentation. These scripts are a collection of scripts that are
used for various testing and benchmarking purposes.

## `load.py`

Allows to create multiple organisations and with a supplied `data.csv` file
create objects on which a select number of boefjes will be performed upon.

```shell
docker build -t mula_scripts .
docker run -it --rm --network=host mula_scripts load.py \
    --orgs {number-of-orgs} \
    --oois {number-of-oois} \
    --boefjes {comma-separated-list-of-boefjes}
```

## `benchmark.py`

Allows to benchmark the operations of the Scheduler. When running the `load.py`
the benchmark script can run along side it to measure the performance of the
Scheduler.

It will check:

- Errors in the logs
- Task stats (how many are queued, running, etc.)
- CPU and memory usage

```shell
docker build -t mula_scripts .
docker run -it --rm --network=host mula_scripts benchmark.py --container {container-id-of-scheduler}
```
