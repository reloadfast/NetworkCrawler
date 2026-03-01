#!/bin/sh
# Entrypoint: fix /app/data ownership then exec the app as the crawler user.
#
# Runs as root so it can repair volume permissions left behind by the old
# VOLUME-based image (where Docker reset /app/data to root ownership).
# After chown, drops to uid/gid 1000 (crawler) via gosu — no root at runtime.
set -e

chown -R crawler:crawler /app/data

exec gosu crawler "$@"
