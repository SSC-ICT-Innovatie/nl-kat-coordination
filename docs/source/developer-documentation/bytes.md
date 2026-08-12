# Bytes

Bytes is a service that provides an API for reading and writing metadata of jobs and job outputs (raw files).
It can also encrypt the raw data, and hash it to proof that the data was seen before a point in time (see below).

## Installation

There are two ways to setup the API.

### With Docker

Bytes can be fired up from the root directory of KAT using docker-compose (check out the README over there!).

To run Bytes as a standalone container, spin up a Postgresql database (e.g. using Docker),
create the database `bytes` and run

```shell
$ docker build . -t bytes

# Without an env-file
$ export BYTES_PASSWORD=$(openssl rand -hex 20) \
    && export BYTES_SECRET=$(openssl rand -hex 20) \
    && export BYTES_DB_URI=postgresql://USER:PWD@bytes-db:5432/bytes  # change accordingly!
$ docker run --rm -p 8002:8002 -e BYTES_USERNAME=bytes -e BYTES_PASSWORD -e BYTES_SECRET -e BYTES_DB_URI bytes


# With an env-file
$ docker run --rm -p 8002:8000 --env-file=/path/to/env bytes  # change accordingly!
```

### Without Docker

To create and start a Python virtual environment, run

```shell
$ python -m venv $PWD/.venv
$ source .venv/bin/activate
```

To install the dependencies, assuming you are in the virtual environment, run

```shell
$ pip install -r requirements-dev.txt
```

Bytes depends on a Postgresql database that is configurable by the BYTES_DB_URI environment variable.
See above for a minimal set of environment variables to start Bytes and

To start the API run

```shell
$ uvicorn bytes.api:app --host 127.0.0.1 --port 8002 --reload --reload-dir /app/bytes/bytes
```

See http://localhost:8002/docs for the OpenAPI documentation.

### Hashing and Encryption

Every raw file is hashed with the current `ended_at` of the `boefje_meta`,
which functions as a 'proof' of it being uploaded at that time.
These proofs can be uploaded externally (a 3rd party) such that we can verify that this data was saved in the past.

Current implementations are

- `BYTES_EXT_HASH_REPOSITORY="IN_MEMORY"` (just a stub)
- `BYTES_EXT_HASH_REPOSITORY="PASTEBIN"` (Needs pastebin API development key)
- `BYTES_EXT_HASH_REPOSITORY="RFC3161"`

For the RFC3161 implementation, see https://www.ietf.org/rfc/rfc3161.txt and https://github.com/trbs/rfc3161ng as a reference.
To use this implementation, set your environment to

- `BYTES_EXT_HASH_REPOSITORY=RFC3161`
- `BYTES_RFC3161_PROVIDER="https://freetsa.org/tsr"` (example)
- `BYTES_RFC3161_CERT_FILE="bytes/timestamping/certificates/freetsa.crt"` (example)

Adding a new implementation means implementing the `bytes.repositories.hash_repository::HashRepository` interface.
Bind your new implementation in `bytes.timestamping.provider::create_hash_repository`.

The secure-hashing-algorithm can be specified with an env var: `BYTES_HASHING_ALGORITHM="SHA512"`.

```bash
BYTES_HASHING_ALGORITHM="SHA512"
BYTES_EXT_HASH_REPOSITORY="IN_MEMORY"
BYTES_PASTEBIN_API_DEV_KEY=""
```

Files in bytes can be saved encrypted to disk,
the implementation can be set using an env-var, `BYTES_ENCRYPTION_MIDDLEWARE`. The options are:

- `"IDENTITY"`
- `"NACL_SEALBOX"`

The `"NACL_SEALBOX"` option requires the `BYTES_PRIVATE_KEY_B64` and `BYTES_PUBLIC_KEY_B64` env vars.

### Observability

Bytes exposes a `/metrics` endpoint for basic application level observability,
such as the amount of organizations and the amount of raw files per organization.
Another important component to monitor is the disk usage of Bytes.
It is recommended to install [node exporter](https://prometheus.io/docs/guides/node-exporter/) to keep track of this.

## Design

We now include two levels of design, according to the [C4 model](https://c4model.com/).

### Design: C2 Container level

The overall view of the code is as follows.

```{mermaid}
graph
    User((User))
    Rocky["Rocky<br/><i>Django App</i>"]
    Bytes{"Bytes<br/><i>FastAPI App"}
    RabbitMQ[["RabbitMQ<br/><i>Message Broker"]]
    Scheduler["Scheduler<br/><i>Software System"]
    Boefjes["Boefjes<br/><i>Python App"]

    Boefjes -- GET/POST Raw/Meta --> Bytes
    User -- Interacts with --> Rocky
    Rocky -- GET/POST Raw/Meta --> Bytes

    Bytes -- "publish(RawFileReceived)" --> RabbitMQ
    Scheduler --"subscribe(RawFileReceived)"--> RabbitMQ
    Scheduler --"GET BoefjeMeta"--> Bytes
```

### Design: C3 Component level

The overall view of the code is as follows.

```{mermaid}
graph LR
    User -- BoefjeMeta --> APIR1
    User -- NormalizerMeta --> APIR2
    User -- RawFile --> APIR3


    User[User]

    APIR1 -- save BoefjeMeta --> MR
    APIR2 -- save NormalizerMeta --> MR
    APIR3 -- save RawFile --> MR

    subgraph API["Bytes API"]
        APIR1[API Route]
        APIR2[API Route]
        APIR3[API Route]
    end

    subgraph Bytes["Bytes Domain"]
        APIR3 -- "publish(RawFileReceived)" --> EM[EventManager]
        MR[Meta Repository] -- Raw  --> H[Hasher] -- Hash --> MR[Meta Repository]
        MR[Meta Repository] -- save Hash --> HR[Hash Repository]
        MR[Meta Repository] -- save RawFile --> R[Raw Repository]
        R[Raw Repository] -- RawFile --> F[FileMiddleware]
    end

    F[FileMiddleware] -- Encrypted Data --> Disk[[Disk]] -- Encrypted Data  --> F[FileMiddleware]
    HR[Hash Repository] -- Hash --> T[[Third Party]]
    MR[Meta Repository] -- BoefjeMeta/NormalizerMeta --> RDB[(Psql)]
    EM[EventManager] -- "{'event_id': 123}" --> RabbitMQ[[RabbitMQ]]
```

This diagram roughly covers the C4 level as well, as this is a small service that can be regarded as one component.

## Development

The `Makefile` provides useful targets to use during development. To see the options run

```shell
$ make help
```

### Code style and tests

All the code style and linting checks are done by running

```shell
$ make check
```

The unit and integration tests targets are `utest` and `itest` respectively.
To run all test, run

```shell
$ make test
```

To make sure all github actions (checks and tests) pass, run

```shell
$ make done
```

Ideally, you run this before each commit.
Passing all the checks and tests in this target should ensure the github actions pass.

### Migrations

To make a new migration file and run the migration, run

```shell
$ make migrations m='Some migration message'
$ make migrate
```

### Export SQL migrations

To export raw SQL from the SQLAlchemy migration files, run the following target
(for the diff between 0003 and 0004):

```shell
$ make sql rev1=0003 rev2=0004 > sql_migrations/0004_change_x_to_y_add_column_z.sql
```

## Production

### Performance tuning

Bytes caches some metrics for performance, but the default is not to cache these queries.
It is recommended to tune the `BYTES_METRICS_TTL_SECONDS` variable to on the amount of calls to the `/metrics` endpoint.
As a guideline, add at least 10 seconds to the cache for every million of raw files in the database.
