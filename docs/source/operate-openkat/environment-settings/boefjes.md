# Boefjes


## `BOEFJES_LOG_CFG`

*Optional*, default value: `../logging.json`

Path to the logging configuration file

## `BOEFJES_POOL_SIZE`

*Optional*, default value: `2`

Number of workers to run per queue

## `BOEFJES_POLL_INTERVAL`

*Optional*, default value: `10.0`

Time to wait before polling for tasks when all queues are empty

## `BOEFJES_WORKER_HEARTBEAT`

*Optional*, default value: `1.0`

Seconds to wait before checking the workers when queues are full

## `BOEFJES_DEDUPLICATE`

*Optional*, default value: `False`

Whether to apply deduplication

## `BOEFJES_PLUGINS`

*Optional*

A list of plugin ids to filter on.

### Examples

`["dns-records"]`

## `BOEFJES_IMAGES`

*Optional*

A list of oci images to filter on.

### Examples

`["docker.underdark.nl/librekat/openkat-generic:latest"]`

## `BOEFJES_REMOTE_NS`

*Optional*, default value: `1.1.1.1`

Name server used for remote DNS resolution in the boefje runner

## `BOEFJES_SCAN_PROFILE_WHITELIST`

*Optional*

Whitelist for normalizer ids allowed to produce scan profiles, including a maximum level.

### Examples

`{"kat_external_db_normalize": 3, "kat_dns_normalize": 1}`

## `KATALOGUS_DB_URI`

**Required**

Katalogus Postgres DB URI

### Examples

`postgresql://xx:xx@host:5432/katalogus`

## `KATALOGUS_DB_CONNECTION_POOL_SIZE`

*Optional*, default value: `16`

Database connection pool size

## `SCHEDULER_API`

**Required**

Mula API URL

### Examples

`http://localhost:8004`

## `KATALOGUS_API`

**Required**

Katalogus API URL

### Examples

`http://localhost:8003`

## `OCTOPOES_API`

**Required**

Octopoes API URL

### Examples

`http://localhost:8001`

## `BOEFJES_API`

**Required**

The URL on which the boefjes API is available

### Examples

`http://boefje:8000`

## `BOEFJES_API_HOST`

*Optional*, default value: `0.0.0.0`

Host address of the Boefje API server

## `BOEFJES_API_PORT`

*Optional*, default value: `8000`

Host port of the Boefje API server

## `BOEFJES_DOCKER_NETWORK`

*Optional*, default value: `bridge`

Docker network to run Boefjes in

## `BOEFJES_DOCKER_INTERNAL_HOST`

*Optional*, default value: `False`

Add "host.docker.internal:host-gateway" to extra_hosts when running boefje. This is enabled by default in the Debian package.

## `BYTES_API`

**Required**

Bytes API URL

### Examples

`http://localhost:8002`

## `BYTES_USERNAME`

**Required**

Bytes JWT login username

### Examples

`test`

## `BYTES_PASSWORD`

**Required**

Bytes JWT login password

### Examples

`secret`

## `BOEFJES_ENCRYPTION_MIDDLEWARE`

*Optional*, default value: `EncryptionMiddleware.IDENTITY`

Toggle used to configure the encryption strategy

### Examples

`IDENTITY`, `NACL_SEALBOX`

## `BOEFJES_KATALOGUS_PRIVATE_KEY`

*Optional*, default value: ``

Base64 encoded private key used for asymmetric encryption of settings

## `BOEFJES_KATALOGUS_PUBLIC_KEY`

*Optional*, default value: ``

Base64 encoded public key used for asymmetric encryption of settings

## `SPAN_EXPORT_GRPC_ENDPOINT`

*Optional*, default value: `None`

OpenTelemetry endpoint

## `BOEFJES_LOGGING_FORMAT`

*Optional*, default value: `text`

Logging format

### Possible values

`text`, `json`

## `BOEFJES_OUTGOING_REQUEST_TIMEOUT`

*Optional*, default value: `30`

Timeout for outgoing HTTP requests


