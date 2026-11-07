#!/usr/bin/env bash
# Restore an app-data backup created by deploy/backup.sh.
#
# Usage: ./deploy/restore.sh <archive.tgz>
#
# Destroys the current volume and replaces it with the backup. The stack is
# left down; start it with `docker compose up -d` and run the smoke checks
# from deploy/OPERATIONS.md.
set -euo pipefail

ARCHIVE="${1:?usage: restore.sh <archive.tgz>}"
PROJECT="$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]_-')"
VOLUME="${PROJECT}_app-data"

if [ ! -f "${ARCHIVE}" ]; then
  echo "archive not found: ${ARCHIVE}" >&2
  exit 1
fi

echo "stopping stack and removing volume ${VOLUME}..."
docker compose down -v

echo "recreating volume and extracting $(basename "${ARCHIVE}")..."
docker volume create "${VOLUME}" >/dev/null
docker run --rm \
  -v "${VOLUME}:/data" \
  -v "$(realpath "$(dirname "${ARCHIVE}")"):/backup:ro" \
  alpine tar xzf "/backup/$(basename "${ARCHIVE}")" -C /

echo "restore complete. Start with: docker compose up -d"
