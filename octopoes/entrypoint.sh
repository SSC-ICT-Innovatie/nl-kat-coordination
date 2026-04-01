#!/bin/bash
set -e

# Make env variable comparison case insensitive
shopt -s nocasematch

if [ "$1" = "web" ]; then
    exec uvicorn octopoes.api.api:app --host 0.0.0.0 --port 80
elif [ "$1" = "worker-beat" ]; then
    exec celery -A octopoes.tasks.tasks worker -B -s /tmp/celerybeat-schedule --loglevel=INFO
elif [ "$1" = "worker" ]; then
    exec celery -A octopoes.tasks.tasks worker --loglevel=INFO
elif [ "$1" = "scanprofiles" ]; then
    exec python3 -m octopoes.tasks.scanprofiles --loglevel=INFO
fi

exec "$@"
