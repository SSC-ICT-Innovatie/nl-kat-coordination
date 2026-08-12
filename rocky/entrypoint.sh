#!/bin/bash
set -e

# Make env variable comparison case insensitive
shopt -s nocasematch

if [ "$DATABASE_MIGRATION" = "1" ] || [[ $DATABASE_MIGRATION == "true" ]]; then
    python manage.py migrate --noinput
fi

if [ "$1" = "web" ]; then
    exec granian --interface wsgi rocky.wsgi:application --host 0.0.0.0
elif [ "$1" = "worker" ]; then
    exec python3 manage.py worker
fi

exec "$@"
