# Frontend: Vue/Vuetify-Build, ausgeliefert von nginx. Build-Kontext ist das Repo-Wurzelverzeichnis.
FROM node:22-alpine AS builder

WORKDIR /app
# Platzhalter – wird zur Laufzeit durch VITE_BASE_PATH ersetzt (entrypoint.sh)
ENV VITE_BASE_PATH='/__VITE_BASE_PATH__/' \
    NODE_ENV=production

COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci --include=dev --no-audit --no-fund

COPY frontend/ .
RUN npm run build

# envsubst und wget sind im offiziellen nginx-Image enthalten
FROM nginx:1.29-alpine

COPY --from=builder /app/dist /usr/share/nginx/html.orig
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf.template
COPY frontend/entrypoint.sh /docker-entrypoint-custom.sh
RUN chmod +x /docker-entrypoint-custom.sh && rm -f /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/health || exit 1

CMD ["/docker-entrypoint-custom.sh"]
