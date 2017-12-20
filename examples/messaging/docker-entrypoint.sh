#!/bin/sh

set -e

if [ $# -eq 0 ]; then
    set -- runserver
fi

if [ "${1#-}" != "$1" ]; then
    set -- runserver "$@"
fi

if [ "$1" = 'runserver' ]; then
    shift
    set -- gunicorn messagingapp.wsgi --bind :80 "$@"
fi

exec "$@"
