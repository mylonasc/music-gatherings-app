#!/usr/bin/env bash
# Real-stack UI evidence on a disposable, uniquely named Compose volume only.
set -euo pipefail
cd "$(dirname "$0")/../.."
project="mg-ui-e2e-$$"
export MUSIC_GATHERINGS_FRONTEND_PORT="${UI_E2E_FRONTEND_PORT:-3200}"
export MUSIC_GATHERINGS_BACKEND_PORT="${UI_E2E_BACKEND_PORT:-8200}"
export E2E_LOGIN_MAX_ATTEMPTS=100
export E2E_BASE_URL="http://localhost:${MUSIC_GATHERINGS_FRONTEND_PORT}"
export API_BASE_URL="http://localhost:${MUSIC_GATHERINGS_BACKEND_PORT}"
export SEED_ADMIN_PASSWORD=ui-isolated-test-pass-1
image="mcr.microsoft.com/playwright:v1.57.0-noble@sha256:3bed4b1a12f2338642f3d8cba28e291deef3c66bd4a964bbeb3e57bbff511dbd"
if docker volume inspect "${project}_app-data" >/dev/null 2>&1 || [[ -n "$(docker compose -p "$project" ps -aq)" ]]; then
  echo "Refusing to reuse existing project $project" >&2
  exit 1
fi
cleanup() { docker compose -p "$project" down -v; }
trap cleanup EXIT
npm ci --prefix tests/e2e
docker compose -p "$project" up -d --build --wait
docker compose -p "$project" exec -T -e MUSIC_GATHERINGS_BOOTSTRAP_PASSWORD="$SEED_ADMIN_PASSWORD" backend python -m app.cli create-admin --username root
npm run seed --prefix tests/e2e
docker run --rm --network host --ipc=host --user "$(id -u):$(id -g)" \
  -e E2E_BASE_URL -e CI="${CI:-}" -v "$PWD/tests/e2e:/work" -w /work "$image" \
  npx playwright test "$@"
