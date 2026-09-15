# Mula


## `DEBUG`

*Optional*, default value: `False`

Enables/disables global debugging mode

## `SCHEDULER_LOG_CFG`

*Optional*, default value: `../../../logging.json`

Path to the logging configuration file

## `SCHEDULER_COLLECT_METRICS`

*Optional*, default value: `False`

Enables/disables the collection of metrics to be used with tools like Prometheus

## `SCHEDULER_LOGGING_FORMAT`

*Optional*, default value: `text`

Logging format

### Possible values

`text`, `json`

## `SCHEDULER_API_HOST`

*Optional*, default value: `0.0.0.0`

Host address of the scheduler api server

## `SCHEDULER_API_PORT`

*Optional*, default value: `8000`

Host api server port

## `SCHEDULER_MONITOR_ORGANISATIONS_INTERVAL`

*Optional*, default value: `60`

Interval in seconds of the execution of the `monitor_organisations` method of the scheduler application to check newly created or removed organisations from katalogus. It updates the organisations, their plugins, and the creation of their schedulers.

## `SCHEDULER_OCTOPOES_REQUEST_TIMEOUT`

*Optional*, default value: `10`

The timeout in seconds for the requests to the octopoes api

## `SCHEDULER_OCTOPOES_POOL_CONNECTIONS`

*Optional*, default value: `10`

The maximum number of connections to save in the pool for the octopoes api

## `SCHEDULER_KATALOGUS_REQUEST_TIMEOUT`

*Optional*, default value: `10`

The timeout in seconds for the requests to the katalogus api

## `SCHEDULER_KATALOGUS_POOL_CONNECTIONS`

*Optional*, default value: `10`

The maximum number of connections to save in the pool for the katalogus api

## `SCHEDULER_BYTES_REQUEST_TIMEOUT`

*Optional*, default value: `10`

The timeout in seconds for the requests to the bytes api

## `SCHEDULER_BYTES_POOL_CONNECTIONS`

*Optional*, default value: `10`

The maximum number of connections to save in the pool for the bytes api

## `SCHEDULER_RABBITMQ_PREFETCH_COUNT`

*Optional*, default value: `100`

RabbitMQ prefetch_count for `channel.basic_qos()`, which is the number of unacknowledged messages on a channel. Also see https://www.rabbitmq.com/consumer-prefetch.html

## `KATALOGUS_API`

**Required**

Katalogus API URL

## `BYTES_API`

**Required**

Bytes API URL

## `BYTES_USERNAME`

**Required**

Bytes JWT login username

## `BYTES_PASSWORD`

**Required**

Bytes JWT login password

## `OCTOPOES_API`

**Required**

Octopoes API URL

## `QUEUE_URI`

**Required**

KAT queue URI for host mutations

## `QUEUE_URI`

**Required**

KAT queue URI for host raw data

## `SPAN_EXPORT_GRPC_ENDPOINT`

*Optional*, default value: `None`

OpenTelemetry endpoint

## `SCHEDULER_PQ_MAXSIZE`

*Optional*, default value: `0`

## `SCHEDULER_PQ_INTERVAL`

*Optional*, default value: `60`

Interval in seconds of the execution of the `` method of the `scheduler.Scheduler` class

## `SCHEDULER_PQ_GRACE_PERIOD`

*Optional*, default value: `86400`

Grace period of when a job is considered to be running again in seconds

## `SCHEDULER_PQ_MAX_RANDOM_OBJECTS`

*Optional*, default value: `50`

The maximum number of random objects that can be added to the priority queue, per call

## `SCHEDULER_DB_URI`

**Required**

Scheduler Postgres DB URI

## `SCHEDULER_DB_CONNECTION_POOL_SIZE`

*Optional*, default value: `25`

Database connection pool size


