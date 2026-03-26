import click
import structlog
from sqlalchemy.orm import sessionmaker

from boefjes.clients.scheduler_client import SchedulerAPIClient
from boefjes.config import Settings, settings
from boefjes.dependencies.plugins import PluginService
from boefjes.job_handler import DockerBoefjeHandler, LocalNormalizerHandler, bytes_api_client
from boefjes.local.runner import LocalNormalizerJobRunner
from boefjes.logging import configure_logging
from boefjes.sql.config_storage import create_config_storage
from boefjes.sql.db import get_engine
from boefjes.sql.plugin_storage import create_plugin_storage
from boefjes.worker.boefje_handler import LocalBoefjeHandler
from boefjes.worker.interfaces import WorkerManager
from boefjes.worker.manager import SchedulerWorkerManager
from boefjes.worker.repository import get_local_repository

configure_logging()

logger = structlog.get_logger(__name__)


def get_runtime_manager(
    settings: Settings, queue: WorkerManager.Queue, images: list[str] | None = None, plugins: list[str] | None = None
) -> WorkerManager:
    local_repository = get_local_repository()

    session = sessionmaker(bind=get_engine())()
    plugin_service = PluginService(create_plugin_storage(session), create_config_storage(session), local_repository)
    scheduler_client = SchedulerAPIClient(plugin_service, str(settings.scheduler_api), images, plugins)

    item_handler: LocalBoefjeHandler | LocalNormalizerHandler | DockerBoefjeHandler

    if queue is WorkerManager.Queue.BOEFJES:
        item_handler = DockerBoefjeHandler(scheduler_client, bytes_api_client)
    else:
        item_handler = LocalNormalizerHandler(
            LocalNormalizerJobRunner(local_repository), bytes_api_client, settings.scan_profile_whitelist
        )

    return SchedulerWorkerManager(
        item_handler,
        scheduler_client,
        settings.pool_size,
        settings.poll_interval,
        settings.worker_heartbeat,
        settings.deduplicate,
    )


@click.command()
@click.argument("queue", type=click.Choice([q.value for q in WorkerManager.Queue]))
@click.option("--worker/--no-worker", "-w/-n", default=True, help="Whether to start a worker.")
@click.option("-i", "--images", type=str, default=None, multiple=True, help="A list of OCI images to filter on.")
@click.option("-p", "--plugins", type=str, default=None, multiple=True, help="A list of plugin ids to filter on.")
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), help="Log level", default="INFO")
def cli(queue: str, worker: bool, images: tuple[str] | None, plugins: tuple[str] | None, log_level: str) -> None:
    logger.setLevel(log_level)
    logger.info("Starting runtime for %s [image_filter=%s, plugin_filter=%s]", queue, images, plugins)

    if not plugins:
        parsed_plugins = settings.plugins or None
    else:
        parsed_plugins = list(plugins)

    if not images:
        parsed_images = settings.images or None
    else:
        parsed_images = list(images)

    runtime = get_runtime_manager(settings, WorkerManager.Queue(queue), parsed_images, parsed_plugins)

    if queue == "boefje":
        import boefjes.api

        boefjes.api.run()

        if worker:
            runtime.run(WorkerManager.Queue(queue))
    else:
        runtime.run(WorkerManager.Queue(queue))


if __name__ == "__main__":
    cli()
