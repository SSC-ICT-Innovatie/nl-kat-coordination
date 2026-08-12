import structlog

from rocky.settings import *  # noqa: F401, F403, TID251

STORAGES = {"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
COMPRESS_OFFLINE = False

# Disable caching of loggers so they can be changed in tests.
structlog.configure(cache_logger_on_first_use=False)
