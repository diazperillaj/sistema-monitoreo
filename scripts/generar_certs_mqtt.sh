#!/usr/bin/env bash
# Genera la CA propia y el certificado del broker MQTT (§5.5): RSA 2048, 10 años, SAN = DOMINIO.
# Uso: ./scripts/generar_certs_mqtt.sh [--forzar]
# DOMINIO sale del .env, o de la variable de entorno si está definida.
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash (Windows): que no convierta "/CN=…" en una ruta

cd "$(dirname "$0")/.."
dir=mosquitto/certs

if [[ -z "${DOMINIO:-}" && -f .env ]]; then
  DOMINIO="$(sed -n 's/^DOMINIO=\([^[:space:]#]*\).*/\1/p' .env | head -n1)"
fi
if [[ -z "${DOMINIO:-}" ]]; then
  echo "Falta DOMINIO (en el .env o como variable de entorno)." >&2
  exit 1
fi
if [[ -e "$dir/server.crt" && "${1:-}" != "--forzar" ]]; then
  echo "Ya hay certificados en $dir. Para regenerarlos: $0 --forzar" >&2
  exit 1
fi

mkdir -p "$dir"
rm -f "$dir"/ca.key "$dir"/ca.crt "$dir"/ca.srl "$dir"/server.key "$dir"/server.csr "$dir"/server.crt "$dir"/server.ext
trap 'rm -f "$dir/server.csr" "$dir/server.ext" "$dir/ca.srl"' EXIT
umask 077

# CA propia (solo firma)
openssl genrsa -out "$dir/ca.key" 2048 2>/dev/null
openssl req -x509 -new -key "$dir/ca.key" -sha256 -days 3650 \
  -subj "/CN=Alarma hogar CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -out "$dir/ca.crt"

# Certificado del broker, firmado por la CA
openssl genrsa -out "$dir/server.key" 2048 2>/dev/null
openssl req -new -key "$dir/server.key" -subj "/CN=$DOMINIO" -out "$dir/server.csr"
printf '%s\n' \
  "subjectAltName=DNS:$DOMINIO" \
  "basicConstraints=CA:FALSE" \
  "keyUsage=critical,digitalSignature,keyEncipherment" \
  "extendedKeyUsage=serverAuth" > "$dir/server.ext"
openssl x509 -req -in "$dir/server.csr" -CA "$dir/ca.crt" -CAkey "$dir/ca.key" -CAcreateserial \
  -days 3650 -sha256 -extfile "$dir/server.ext" -out "$dir/server.crt" 2>/dev/null

chmod 644 "$dir/ca.crt" "$dir/server.crt"
chmod 600 "$dir/ca.key" "$dir/server.key"

# Mosquitto corre como el usuario "mosquitto" (uid 1883) y relee la llave al recargar (HUP).
# En Linux se la entrega un contenedor, porque el usuario del host no puede hacer chown.
if [[ "$(uname -s)" == Linux ]]; then
  docker run --rm -v "$PWD/$dir:/certs" --entrypoint chown eclipse-mosquitto:2 1883:1883 /certs/server.key
fi

echo "Certificados creados en $dir (SAN = DNS:$DOMINIO), válidos por 10 años."
openssl x509 -in "$dir/server.crt" -noout -fingerprint -sha256
echo "Guarda $dir/ca.key fuera del servidor (respaldo offline) y bórrala de aquí: solo sirve para firmar."
