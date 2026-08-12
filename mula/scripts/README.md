# Scripts

A collection of scripts that is used for various testing and benchmarking
purposes.

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
