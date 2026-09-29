#!/usr/bin/env bash
# Spielt das Jenkins-Deployment lokal nach (gleiche docker-run-Aufrufe wie im Jenkinsfile), inkl. Host-nginx.
# Aufruf: deploy/lokal-deploy.sh [backend-image] [frontend-image]   → http://localhost:8088/app/dpn/test/konfig-stueckliste-export/
# Exporte: ./export (oder EXPORTS=/pfad); ohne Exporte lädt das Backend Beispieldaten (DEMO_FIXTURES=T).
# RESET=1 legt die Datenbank neu an (frische Beispieldaten).
set -euo pipefail
BACKEND_IMAGE=${1:-kse-backend:dev}
FRONTEND_IMAGE=${2:-kse-frontend:dev}
P=konfig-stueckliste-export
ENVIRONMENT=test
NET=app_network
PG=postgres_db_dev
DB=konfig_stueckliste_export_test
DEPLOY_DIR=${DEPLOY_DIR:-$HOME/deployment/${P}_${ENVIRONMENT}}
APP_PATH=/app/dpn/test/$P/
BE=konfig_stueckliste_export_backend_${ENVIRONMENT}
FE=konfig_stueckliste_export_frontend_${ENVIRONMENT}

docker network inspect $NET >/dev/null 2>&1 || docker network create $NET
if ! docker inspect $PG >/dev/null 2>&1; then
  docker run -d --name $PG --network $NET -e POSTGRES_PASSWORD=postgres postgres:16 >/dev/null
  until docker exec $PG pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done; sleep 2
fi
mkdir -p "$DEPLOY_DIR/base/exports" "$DEPLOY_DIR/out"
if [ -n "${EXPORTS:-}" ]; then cp -r "$EXPORTS"/. "$DEPLOY_DIR/base/exports/"; fi
[ -f "$DEPLOY_DIR/base/sens.env" ] || cat > "$DEPLOY_DIR/base/sens.env" <<ENV
SECRET_KEY=lokal-secret-key-mindestens-32-zeichen-lang-0000
MASTER_PASSWORD_ADMIN=${PASSWORT:-test}
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DEMO_FIXTURES=T
ENV
if [ -n "${RESET:-}" ]; then  # RESET=1: Datenbank neu (Beispieldaten frisch, z. B. vor E2E)
  docker rm -f $FE $BE >/dev/null 2>&1 || true
  docker exec $PG dropdb -U postgres --if-exists --force $DB
fi
docker exec $PG psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1 || docker exec $PG createdb -U postgres $DB
docker run --rm --user root -v "$DEPLOY_DIR/out:/data/out" --entrypoint chown "$BACKEND_IMAGE" -R 1000:1000 /data/out
docker rm -f $FE $BE >/dev/null 2>&1 || true
docker run -d --name $BE --network $NET --restart unless-stopped --env-file "$DEPLOY_DIR/base/sens.env" \
  -e MODE=production -e DATABASE_HOST=$PG -e DATABASE_NAME=$DB -e ROOT_PATH= -e CORS_ORIGINS=http://localhost:8088 \
  -v "$DEPLOY_DIR/base/exports:/data/exports:ro" -v "$DEPLOY_DIR/out:/data/out" \
  --health-interval=5s --health-timeout=5s --health-start-period=10s --health-retries=3 "$BACKEND_IMAGE" >/dev/null
docker run -d --name $FE --network $NET --restart unless-stopped -e BACKEND_HOST=$BE -e BACKEND_PORT=8000 \
  -e VITE_BASE_PATH=$APP_PATH -e DNS_RESOLVER=127.0.0.11 "$FRONTEND_IMAGE" >/dev/null
# Host-nginx wie auf dem Server: Pfad bleibt erhalten, Weiterleitung an den Frontend-Container
cat > "$DEPLOY_DIR/host-nginx.conf" <<NGX
server {
  listen 80;
  location $APP_PATH { resolver 127.0.0.11 valid=10s; set \$fe $FE; proxy_pass http://\$fe:80; proxy_set_header Host localhost;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; proxy_read_timeout 300s; }
}
NGX
docker rm -f host_nginx >/dev/null 2>&1 || true
docker run -d --name host_nginx --network $NET -p 8088:80 -v "$DEPLOY_DIR/host-nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:1.29-alpine >/dev/null
for c in $BE $FE; do
  for i in $(seq 1 30); do s=$(docker inspect --format='{{.State.Health.Status}}' $c); [ "$s" = healthy ] && break; sleep 2; done
  echo "$c: $s"
done
docker exec $FE wget -q -O - "http://127.0.0.1${APP_PATH}api/health"; echo
echo "→ http://localhost:8088$APP_PATH (Passwort: ${PASSWORT:-test})"
