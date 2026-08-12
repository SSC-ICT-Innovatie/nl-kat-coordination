from kombu import Queue

from octopoes.config.settings import QUEUE_NAME_OCTOPOES, Settings

settings = Settings()

broker_url = str(settings.queue_uri)
result_backend = f"rpc://{settings.queue_uri}"

task_serializer = "json"
result_serializer = "json"
event_serializer = "json"
accept_content = ["application/json", "application/x-python-serialize"]
result_accept_content = ["application/json", "application/x-python-serialize"]

task_queues = (Queue(QUEUE_NAME_OCTOPOES),)

worker_concurrency = settings.workers
