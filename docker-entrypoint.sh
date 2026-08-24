#!/bin/sh
# Seed at start rather than at build: seed.py dates its games to the current
# US/Eastern date, so a database baked into the image goes stale overnight.
set -e

python seed.py

exec "$@"
