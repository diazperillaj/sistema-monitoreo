#!/usr/bin/env bash
# Respaldo (§16): base de datos, configuración de Mosquitto (usuarios y certificados) y .env.
# Guarda 14 días. Cron del host a las 03:30:
#   30 3 * * *  cd /ruta/alarma-hogar && ./scripts/backup.sh >> backups/backup.log 2>&1
# Después, copia backups/ fuera del servidor (disco externo o nube).
set -euo pipefail
export MSYS_NO_PATHCONV=1
umask 077

cd "$(dirname "$0")/.."
fecha="$(date +%F)"
mkdir -p backups

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/alarma-$fecha.dump"
# passwd y server.key son del usuario del broker: se leen desde su propio contenedor.
docker compose exec -T mosquitto tar -czf - -C /mosquitto config certs > "backups/mosquitto-$fecha.tar.gz"
cp .env "backups/env-$fecha"

find backups -maxdepth 1 -type f \( -name 'alarma-*.dump' -o -name 'mosquitto-*.tar.gz' -o -name 'env-*' \) \
  -mtime +14 -delete
echo "Respaldo listo en backups/ ($fecha)."
