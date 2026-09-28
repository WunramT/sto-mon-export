// =============================================================================
// Deployment „Export konfigurierbare Stücklisten“ (konfig-stueckliste-export)
// -----------------------------------------------------------------------------
// Voraussetzung (CI, .gitlab-ci.yml): Images liegen in Harbor
//   harbor.aks-infra.polipol-service.de/dap-api/konfig-stueckliste-export:<tag>
//   harbor.aks-infra.polipol-service.de/dap-ui/konfig-stueckliste-export:<tag>
//
// Auf dem Zielhost (einmalig, siehe docs/DEPLOYMENT.md):
//   $HOME/deployment/konfig-stueckliste-export_<env>/base/sens.env   Geheimnisse + DB-Zugang
//   $HOME/deployment/konfig-stueckliste-export_<env>/base/exports/   SAP-Exporte (nur lesend gemountet)
//   Docker-Netz app_network, Postgres-Container postgres_db_prod / postgres_db_dev, Host-nginx
//
// Ablauf: Prüfen → Images ziehen → Datenbank anlegen/sichern → alte Container parken → neue starten
//         (Health) → optional Exporte neu laden → Aufräumen. Bei Fehler: alte Container wieder starten.
// Basis: Jenkinsfile aus dap-base-lib/templates/app_backend_frontend bzw. MLP (dpn-svr-iot, BASE_PATH "").
// =============================================================================
pipeline {
    agent any

    parameters {
        choice(name: 'TARGET_SERVER', choices: ['dpn-svr-iot', 'cho-svr-lin01', 'pod-svr-lin01', 'jan-svr-lin01', 'srem-svr-lin01', 'foi-svr-lnx01', 'wag-svr-lin01', 'gor-svr-lin01', 'slu-svr-lin02'], description: 'Zielserver')
        choice(name: 'ENVIRONMENT', choices: ['test', 'prod'], description: 'Umgebung')
        string(name: 'IMAGE_TAG_BACKEND', defaultValue: 'latest', description: 'Image-Tag Backend (Commit-SHA aus der GitLab-Pipeline oder latest)')
        string(name: 'IMAGE_TAG_FRONTEND', defaultValue: 'latest', description: 'Image-Tag Frontend')
        choice(name: 'RELOAD_EXPORTS', choices: ['no', 'yes'], description: 'Nach dem Deploy die SAP-Exporte aus base/exports neu laden (sonst nur beim ersten Start mit leerer Datenbank)')
        string(name: 'PUBLIC_BASE_URL', defaultValue: 'https://iot.polipol-service.de', description: 'Öffentliche Adresse des Host-nginx (nur für Log/CORS)')
        string(name: 'DNS_RESOLVER', defaultValue: '127.0.0.11', description: 'DNS-Resolver im Frontend-nginx (Docker: 127.0.0.11)')
    }

    environment {
        PROJECT_NAME = 'konfig-stueckliste-export'
        REGISTRY_URL = 'harbor.aks-infra.polipol-service.de'
        BACKEND_IMAGE = "${REGISTRY_URL}/dap-api/${PROJECT_NAME}"
        FRONTEND_IMAGE = "${REGISTRY_URL}/dap-ui/${PROJECT_NAME}"

        // Gemeinsamer Postgres-Container je Umgebung; eigene Datenbank je Umgebung (mehrere Schemas: sap_raw, basis_bom)
        POSTGRES_CONTAINER = "${params.ENVIRONMENT == 'prod' ? 'postgres_db_prod' : 'postgres_db_dev'}"
        POSTGRES_USER = 'postgres'
        DATABASE_NAME = "${params.ENVIRONMENT == 'prod' ? 'konfig_stueckliste_export' : 'konfig_stueckliste_export_test'}"
        HOST_BACKUP_DIR = '$HOME/backups'

        APP_NETWORK = 'app_network'
        BACKEND_CONTAINER = "${PROJECT_NAME}_backend_${params.ENVIRONMENT}"
        FRONTEND_CONTAINER = "${PROJECT_NAME}_frontend_${params.ENVIRONMENT}"
        BACKEND_PORT = '8000'

        DEPLOY_DIR = "\$HOME/deployment/${PROJECT_NAME}_${params.ENVIRONMENT}"
        // URL-Pfad hinter dem Host-nginx (dpn-svr-iot: kein /app/<prefix> davor, siehe MLP)
        APP_PATH = "${params.ENVIRONMENT == 'prod' ? '/konfig-stueckliste-export/' : '/test/konfig-stueckliste-export/'}"
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 60, unit: 'MINUTES')
    }

    stages {
        stage('Vorbereitung') {
            steps {
                script {
                    echo "Deploy ${PROJECT_NAME} → ${params.TARGET_SERVER} (${params.ENVIRONMENT})"
                    echo "Backend:  ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND}"
                    echo "Frontend: ${FRONTEND_IMAGE}:${params.IMAGE_TAG_FRONTEND}"
                    echo "Datenbank: ${DATABASE_NAME} in ${POSTGRES_CONTAINER}"
                    echo "Adresse: ${params.PUBLIC_BASE_URL}${APP_PATH}"
                }
            }
        }

        stage('Zielhost') {
            steps {
                script {
                    def mkHost = { name, ip, credId -> [name: name, host: ip, port: 22, allowAnyHosts: true, credId: credId] }
                    def HOSTS = [
                        'dpn-svr-iot'   : mkHost('dpn-svr-iot', '192.168.48.240', 'dpn-svr-iot_pw'),
                        'cho-svr-lin01' : mkHost('cho-svr-lin01', '10.11.1.101', 'cho-svr-lin01_pw'),
                        'pod-svr-lin01' : mkHost('pod-svr-lin01', '10.20.1.160', 'pod-svr-lin01_pw'),
                        'jan-svr-lin01' : mkHost('jan-svr-lin01', '10.30.1.150', 'jan-svr-lin01_pw'),
                        'srem-svr-lin01': mkHost('srem-svr-lin01', '10.40.1.161', 'srem-svr-lin01_pw'),
                        'wag-svr-lin01' : mkHost('wag-svr-lin01', '10.60.1.198', 'wag-svr-lin01_pw'),
                        'foi-svr-lnx01' : mkHost('foi-svr-lnx01', '192.168.64.60', 'foi-svr-lnx01_pw'),
                        'gor-svr-lin01' : mkHost('gor-svr-lin01', '10.87.1.150', 'gor-svr-lin01_pw'),
                        'slu-svr-lin02' : mkHost('slu-svr-lin02', '10.90.1.20', 'slu-svr-lin02_pw'),
                    ]
                    def hostConfig = HOSTS[params.TARGET_SERVER]
                    if (!hostConfig) error("Unbekannter Zielserver: ${params.TARGET_SERVER}")
                    withCredentials([usernamePassword(credentialsId: hostConfig.credId, usernameVariable: 'REMOTE_USR', passwordVariable: 'REMOTE_PSW')]) {
                        REMOTE = [name: params.TARGET_SERVER, host: hostConfig.host, port: hostConfig.port,
                                  allowAnyHosts: hostConfig.allowAnyHosts, user: REMOTE_USR, password: REMOTE_PSW]
                    }
                    // dpn-svr-iot läuft direkt unter der Domain (MLP); die Werks-Server unter /app/<kürzel>
                    env.BASE_PATH = params.TARGET_SERVER == 'dpn-svr-iot' ? '' : "/app/${params.TARGET_SERVER.take(4).replaceAll(/-$/, '')}"
                }
            }
        }

        stage('Host prüfen') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        set -e
                        docker network inspect ${APP_NETWORK} >/dev/null 2>&1 || { echo "FEHLER: Docker-Netz ${APP_NETWORK} fehlt"; exit 1; }
                        docker inspect ${POSTGRES_CONTAINER} >/dev/null 2>&1 || { echo "FEHLER: Postgres-Container ${POSTGRES_CONTAINER} fehlt"; exit 1; }
                        test -f ${DEPLOY_DIR}/base/sens.env || { echo "FEHLER: ${DEPLOY_DIR}/base/sens.env fehlt (Vorlage: deploy/sens.env.example)"; exit 1; }
                        mkdir -p ${DEPLOY_DIR}/base/exports ${DEPLOY_DIR}/out ${HOST_BACKUP_DIR}
                        echo "Exporte in ${DEPLOY_DIR}/base/exports:"
                        ls -la ${DEPLOY_DIR}/base/exports || true
                    """
                }
            }
        }

        stage('Images ziehen') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        set -e
                        docker pull ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND}
                        docker pull ${FRONTEND_IMAGE}:${params.IMAGE_TAG_FRONTEND}
                        # Ausgabeverzeichnis für den Backend-Benutzer (uid 1000) beschreibbar machen
                        docker run --rm --user root -v ${DEPLOY_DIR}/out:/data/out --entrypoint chown ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND} -R 1000:1000 /data/out
                    """
                }
            }
        }

        // Datenbank anlegen (erster Deploy) und die fachlichen Daten sichern. Gesichert wird nur das Schema
        // basis_bom (Regeln, Bewertungen, Bestätigungen, Entwürfe) – sap_raw lässt sich aus den Exporten neu laden.
        stage('Datenbank') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        set -e
                        # Die App verbindet sich mit DATABASE_USER aus sens.env (empfohlen: eigene Rolle, siehe docs/DEPLOYMENT.md)
                        APP_USER=\$(grep -E '^DATABASE_USER=' ${DEPLOY_DIR}/base/sens.env | tail -1 | cut -d= -f2- | tr -d '"' )
                        APP_USER=\${APP_USER:-postgres}
                        docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='\$APP_USER'" | grep -q 1 \
                            || { echo "FEHLER: Datenbank-Rolle \$APP_USER fehlt (einmalig anlegen, siehe docs/DEPLOYMENT.md)"; exit 1; }
                        if ! docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DATABASE_NAME}'" | grep -q 1; then
                            echo "Lege Datenbank ${DATABASE_NAME} an (erster Deploy, Eigentümer \$APP_USER)"
                            docker exec ${POSTGRES_CONTAINER} createdb -U ${POSTGRES_USER} -O \$APP_USER ${DATABASE_NAME}
                        elif docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d ${DATABASE_NAME} -tAc "SELECT 1 FROM information_schema.schemata WHERE schema_name='basis_bom'" | grep -q 1; then
                            DATEI=${HOST_BACKUP_DIR}/${DATABASE_NAME}_basis_bom_\$(date +%Y%m%d_%H%M%S).dump
                            docker exec ${POSTGRES_CONTAINER} pg_dump -U ${POSTGRES_USER} -d ${DATABASE_NAME} -n basis_bom -Fc > \$DATEI
                            echo "Sicherung: \$DATEI (\$(du -h \$DATEI | cut -f1))"
                            # nur die letzten 20 Sicherungen behalten
                            ls -1t ${HOST_BACKUP_DIR}/${DATABASE_NAME}_basis_bom_*.dump | tail -n +21 | xargs -r rm -f
                        else
                            echo "Datenbank vorhanden, aber noch ohne Schema basis_bom – keine Sicherung nötig"
                        fi
                    """
                }
            }
        }

        stage('Alte Container parken') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        docker rm -f ${BACKEND_CONTAINER}-previous ${FRONTEND_CONTAINER}-previous >/dev/null 2>&1 || true
                        docker stop ${FRONTEND_CONTAINER} || true
                        docker stop ${BACKEND_CONTAINER}  || true
                        docker inspect ${BACKEND_CONTAINER}  >/dev/null 2>&1 && docker rename ${BACKEND_CONTAINER}  ${BACKEND_CONTAINER}-previous  || true
                        docker inspect ${FRONTEND_CONTAINER} >/dev/null 2>&1 && docker rename ${FRONTEND_CONTAINER} ${FRONTEND_CONTAINER}-previous || true
                    """
                    // Erst ab hier ersetzt der Deploy laufende Container – nur dann zurückrollen
                    env.GEPARKT = 'true'
                }
            }
        }

        stage('Backend starten') {
            steps {
                script {
                    // DB-Host/-Name setzt die Pipeline (nach --env-file, hat Vorrang), damit test und prod sicher getrennt sind.
                    // Healthcheck kommt aus dem Image (HEALTHCHECK), hier nur engere Intervalle.
                    sshCommand remote: REMOTE, command: """
                        set -e
                        docker run -d \\
                            --name ${BACKEND_CONTAINER} \\
                            --network ${APP_NETWORK} \\
                            --restart unless-stopped \\
                            --env-file ${DEPLOY_DIR}/base/sens.env \\
                            -e MODE=production \\
                            -e DATABASE_HOST=${POSTGRES_CONTAINER} \\
                            -e DATABASE_NAME=${DATABASE_NAME} \\
                            -e ROOT_PATH= \\
                            -e CORS_ORIGINS=${params.PUBLIC_BASE_URL} \\
                            -e APP_VERSION=${params.IMAGE_TAG_BACKEND} \\
                            -v ${DEPLOY_DIR}/base/exports:/data/exports:ro \\
                            -v ${DEPLOY_DIR}/out:/data/out \\
                            --health-interval=15s --health-timeout=10s --health-start-period=20s --health-retries=3 \\
                            ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND}
                    """
                    waitHealthy(BACKEND_CONTAINER, 24)
                    // Backend meldet sich sofort gesund; Datenbankfehler zeigen sich im Datenstand
                    sshCommand remote: REMOTE, command: """
                        sleep 5
                        docker logs --tail 30 ${BACKEND_CONTAINER}
                        # Liveness ist sofort grün; hier zusätzlich: Datenbank erreichbar, Start nicht fehlgeschlagen
                        docker exec ${BACKEND_CONTAINER} python -c "import json,sys,urllib.request; h=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health')); print(h); sys.exit(1 if h.get('daten') == 'fehler' else 0)"
                    """
                }
            }
        }

        stage('Frontend starten') {
            steps {
                script {
                    def viteBasePath = env.BASE_PATH + APP_PATH
                    sshCommand remote: REMOTE, command: """
                        set -e
                        docker run -d \\
                            --name ${FRONTEND_CONTAINER} \\
                            --network ${APP_NETWORK} \\
                            --restart unless-stopped \\
                            -e BACKEND_HOST=${BACKEND_CONTAINER} \\
                            -e BACKEND_PORT=${BACKEND_PORT} \\
                            -e VITE_BASE_PATH=${viteBasePath} \\
                            -e DNS_RESOLVER=${params.DNS_RESOLVER} \\
                            ${FRONTEND_IMAGE}:${params.IMAGE_TAG_FRONTEND}
                    """
                    waitHealthy(FRONTEND_CONTAINER, 12)
                    // Durchstich: Frontend-nginx → Backend
                    sshCommand remote: REMOTE, command: """
                        docker exec ${FRONTEND_CONTAINER} wget -q -O - http://127.0.0.1${viteBasePath}api/health
                    """
                }
            }
        }

        stage('Exporte neu laden') {
            when { expression { params.RELOAD_EXPORTS == 'yes' } }
            steps {
                script {
                    // Die neuen Container laufen schon gesund: ein Fehler beim Laden macht den Build UNSTABLE,
                    // löst aber keinen Rollback aus (die Oberfläche zeigt den Fehler im Datenstand).
                    catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                        sshCommand remote: REMOTE, command: """
                            docker exec ${BACKEND_CONTAINER} python scripts/neu_laden.py --warten
                        """
                    }
                }
            }
        }

        stage('Aufräumen') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        docker rm ${BACKEND_CONTAINER}-previous  || true
                        docker rm ${FRONTEND_CONTAINER}-previous || true
                        docker image prune -a --filter "until=168h" -f || true
                    """
                }
            }
        }
    }

    post {
        failure {
            script {
                if (env.GEPARKT != 'true') {
                    // Fehler vor dem Austausch (Host, Images, Datenbank): die laufende Version bleibt unberührt
                    echo 'Fehler vor dem Austausch der Container – laufende Version bleibt unverändert, kein Rollback.'
                    return
                }
                echo 'Deployment fehlgeschlagen – alte Container werden wieder gestartet.'
                sshCommand remote: REMOTE, command: """
                    docker logs --tail 80 ${BACKEND_CONTAINER} 2>&1 || true
                    docker rm -f ${FRONTEND_CONTAINER} ${BACKEND_CONTAINER} >/dev/null 2>&1 || true
                    docker inspect ${BACKEND_CONTAINER}-previous  >/dev/null 2>&1 && docker rename ${BACKEND_CONTAINER}-previous  ${BACKEND_CONTAINER}  || true
                    docker inspect ${FRONTEND_CONTAINER}-previous >/dev/null 2>&1 && docker rename ${FRONTEND_CONTAINER}-previous ${FRONTEND_CONTAINER} || true
                    docker start ${BACKEND_CONTAINER}  || true
                    docker start ${FRONTEND_CONTAINER} || true
                    echo "Rollback fertig. Sicherung der Regeln/Bewertungen liegt in ${HOST_BACKUP_DIR} (siehe docs/DEPLOYMENT.md)."
                """
            }
        }
        success {
            echo "✓ ${PROJECT_NAME} läuft: ${params.PUBLIC_BASE_URL}${APP_PATH}"
        }
    }
}

// Wartet, bis Docker den Container als healthy meldet (je Versuch 5 s)
def waitHealthy(String container, int versuche) {
    for (int i = 1; i <= versuche; i++) {
        def status = sshCommand(remote: REMOTE, command: "docker inspect --format='{{.State.Health.Status}}' ${container}").trim()
        if (status == 'healthy') {
            echo "✓ ${container} ist gesund"
            return
        }
        echo "[${i}/${versuche}] ${container}: ${status}"
        if (status == 'unhealthy') break
        sleep(5)
    }
    error("${container} wurde nicht gesund")
}
