import argparse
import logging
import subprocess
import threading
import time
from pathlib import Path

import httpx

SCHEDULER_API = "http://localhost:8004"
TIMEOUT_FOR_LOG_CAPTURE = 5

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

client = httpx.Client(base_url=SCHEDULER_API)


def are_tasks_done() -> bool:
    response = client.get(url="/tasks/stats", timeout=30)

    try:
        response.raise_for_status()
    except httpx.HTTPError:
        logger.error("Error getting tasks")
        raise

    tasks_stats = response.json()

    return all(tasks_stats[hour].get("queued") <= 0 for hour in tasks_stats)


def parse_stats() -> None:
    resp_tasks_stats = client.get(url="/tasks/stats", timeout=30)

    try:
        resp_tasks_stats.raise_for_status()
    except httpx.HTTPError:
        logger.error("Error getting tasks")
        raise

    tasks_stats = resp_tasks_stats.json()
    for hour in tasks_stats:
        queued = tasks_stats[hour].get("queued")
        running = tasks_stats[hour].get("running")
        failed = tasks_stats[hour].get("failed")
        completed = tasks_stats[hour].get("completed")

        logger.info("HOUR %s, QUEUED %s, RUNNING %s, FAILED %s, COMPLETED %s", hour, queued, running, failed, completed)


def capture_logs(container_id: str, output_file: str) -> None:
    # Capture logs
    with Path.open(output_file, "w", encoding="utf-8") as file:
        subprocess.run(["docker", "logs", container_id], stdout=file, stderr=file, check=True)


def parse_logs(path: str) -> None:
    # Check if there were any errors in the logs
    count = 0
    with Path.open(path, encoding="utf-8") as file:
        for line in file:
            if line.startswith("ERROR") or line.startswith("Traceback"):
                count += 1
                logger.info(line)

    if count > 0:
        logger.error("Found %d errors in the logs", count)


def collect_cpu(container_id: str) -> str:
    return (
        subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}", container_id],
            capture_output=True,
            check=True,
        )
        .stdout.decode("utf-8")
        .strip("%\n")
    )


def collect_memory(container_id: str) -> str:
    return (
        subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container_id],
            capture_output=True,
            check=True,
        )
        .stdout.decode("utf-8")
        .split("/")[0]
        .strip("MiB\n")
    )


def run(container_id: str) -> None:
    # Start capturing logs
    if container_id is not None:
        thread = threading.Thread(target=capture_logs, args=(container_id, "logs.txt"))
        thread.start()

    # Wait for tasks to finish
    while not are_tasks_done():
        logger.debug("Tasks are not done yet")

        cpu = collect_cpu(container_id)
        memory = collect_memory(container_id)
        logger.info("CPU %s, MEMORY %s", cpu, memory)

        # Parse stats
        parse_stats()

        time.sleep(10)
        continue

    logger.debug("Tasks are done")

    # Stop capturing logs
    thread.join(timeout=TIMEOUT_FOR_LOG_CAPTURE)

    # Parse stats
    parse_stats()

    # Parse logs
    parse_logs("logs.txt")


if __name__ == "__main__":
    # Setup command line interface
    parser = argparse.ArgumentParser(description="Benchmark the scheduler.")

    # Add arguments
    parser.add_argument("--verbose", "-v", action="store_true", help="Set to enable verbose logging.")

    parser.add_argument(
        "--container-id", "-c", type=str, required=False, help="The container id of the process to monitor."
    )

    # Parse arguments
    args = parser.parse_args()

    # Configure logging level, if the -v (verbose) flag was given this will
    # set the log-level to DEBUG (printing all debug messages and higher),
    # if -v was not given it defaults to printing level warning and higher.
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG

    logging.basicConfig(level=level, format="%(asctime)s %(name)-10s %(levelname)-8s %(message)s")

    run(args.container_id)
