#!/usr/bin/env bash
# Coherent backup of the app-data volume (SQLite database + object store).
#
# Usage: ./deploy/backup.sh [backup-dir]
#
# Stops the stack first (keeping the volume) so the copy is coherent:
# objects are immutable, so with no writers running the tarball is a
# consistent snapshot. Never back up a live database by raw file copy.
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
PROJECT="$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]_-')"
VOLUME="${PROJECT}_app-data"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="${BACKUP_DIR}/music-gatherings-${STAMP}.tgz"

mkdir -p "${BACKUP_DIR}"
if ! docker volume inspect "${VOLUME}" >/dev/null 2>&1; then
  echo "volume ${VOLUME} does not exist; nothing to back up" >&2
  exit 1
fi

echo "stopping stack (keeping the volume)..."
docker compose down

echo "archiving ${VOLUME} to ${ARCHIVE}..."
docker run --rm \
  -v "${VOLUME}:/data:ro" \
  -v "$(realpath "${BACKUP_DIR}"):/out" \
  alpine tar czf "/out/$(basename "${ARCHIVE}")" -C / data

cat > "${ARCHIVE%.tgz}.manifest" <<EOF
date_utc=${STAMP}
volume=${VOLUME}
git_rev=$(git rev-parse HEAD 2>/dev/null || echo unknown)
EOF

echo "backup complete: ${ARCHIVE}"
echo "restart with: docker compose up -d"
