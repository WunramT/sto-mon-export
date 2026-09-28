#!/bin/sh
set -e

BACKEND_HOST=${BACKEND_HOST:-backend}
BACKEND_PORT=${BACKEND_PORT:-8000}
VITE_BASE_PATH=${VITE_BASE_PATH:-/}
DNS_RESOLVER=${DNS_RESOLVER:-127.0.0.11}
# Basis-Pfad immer mit / am Anfang und Ende
case "$VITE_BASE_PATH" in /*) ;; *) VITE_BASE_PATH="/$VITE_BASE_PATH" ;; esac
case "$VITE_BASE_PATH" in */) ;; *) VITE_BASE_PATH="$VITE_BASE_PATH/" ;; esac
export BACKEND_HOST BACKEND_PORT VITE_BASE_PATH DNS_RESOLVER

envsubst '${BACKEND_HOST} ${BACKEND_PORT} ${VITE_BASE_PATH} ${DNS_RESOLVER}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Platzhalter-Basis-Pfad im Build (vite.config.ts) durch den echten ersetzen – ein Image für test und prod.
# Idempotent: die Originale liegen unter /usr/share/nginx/html.orig.
rm -rf /usr/share/nginx/html && cp -r /usr/share/nginx/html.orig /usr/share/nginx/html
find /usr/share/nginx/html -type f \( -name "*.html" -o -name "*.js" -o -name "*.css" \) -exec sed -i "s|/__VITE_BASE_PATH__/|${VITE_BASE_PATH}|g" {} +

echo "Frontend: Basis-Pfad ${VITE_BASE_PATH}, Backend ${BACKEND_HOST}:${BACKEND_PORT}"
exec nginx -g "daemon off;"
