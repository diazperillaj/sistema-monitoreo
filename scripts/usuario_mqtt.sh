#!/usr/bin/env bash
# Crea o actualiza un usuario de Mosquitto (§5.4).
# Uso: ./scripts/usuario_mqtt.sh <usuario> <clave>
#   <usuario>: backend_api, o el ID_CASA de una central (^[a-z0-9-]{4,40}$)
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash (Windows): que no convierta las rutas del contenedor

cd "$(dirname "$0")/.."
usuario="${1:-}"
clave="${2:-}"
if [[ -z "$usuario" || -z "$clave" ]]; then
  echo "Uso: $0 <usuario> <clave>" >&2
  exit 2
fi
if [[ "$usuario" != "backend_api" && ! "$usuario" =~ ^[a-z0-9-]{4,40}$ ]]; then
  echo "Usuario inválido: debe ser backend_api o un ID_CASA (minúsculas, números y guiones; 4 a 40)." >&2
  exit 2
fi

# Ruta absoluta en el formato que entiende Docker (en Git Bash: C:/…)
config="$(pwd -W 2>/dev/null || pwd)/mosquitto/config"

# Contenedor temporal: funciona aunque el broker esté detenido o el archivo aún no exista.
# El archivo queda del usuario "mosquitto" (uid 1883) para que el broker lo relea al recargar.
docker run --rm -v "$config:/mosquitto/config" --entrypoint sh eclipse-mosquitto:2 -c '
  set -e
  f=/mosquitto/config/passwd
  if [ -f "$f" ]; then
    chown root:root "$f" 2>/dev/null || true   # mosquitto_passwd corre como root y espera que sea suyo
    mosquitto_passwd -b "$f" "$1" "$2"
  else
    mosquitto_passwd -c -b "$f" "$1" "$2"
  fi
  chown mosquitto:mosquitto "$f" 2>/dev/null || true
  chmod 600 "$f" 2>/dev/null || true
' sh "$usuario" "$clave"

if [[ -n "$(docker compose ps -q mosquitto 2>/dev/null)" ]]; then
  docker compose kill -s HUP mosquitto >/dev/null
  echo "Usuario '$usuario' listo; Mosquitto recargó los usuarios."
else
  echo "Usuario '$usuario' listo."
fi
