#!/bin/sh

set -e

if [ $# -eq 0 ]; then
    set -- stormd
fi

if [ "${1#-}" != "$1" ]; then
    set -- stormd "$@"
fi

exec "$@"
