from celery import Celery

import octopoes.config.celery as celery_config
from octopoes.config.settings import Settings

settings = Settings()

app = Celery()
app.config_from_object(celery_config)
