# Alarma hogar — sistema de monitoreo doméstico

App web (FastAPI + React + PostgreSQL + Mosquitto) para el sistema de alarmas con ESP32.
Se publica en `https://sistemamonitoreo.duckdns.org` a través del Caddy que ya existe en el servidor.

- **Especificación completa:** [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md)
- **Plan de implementación:** [`docs/PLAN_IMPLEMENTACION.md`](docs/PLAN_IMPLEMENTACION.md)
- **Instrucciones para Claude Code:** [`CLAUDE.md`](CLAUDE.md)
- **Firmware de referencia:** [`firmware/`](firmware/)

## Desarrollo local

Requisitos: Docker, Node 24, Python 3.12 con [uv](https://docs.astral.sh/uv/) y, en Windows, Git Bash.

**La primera vez:**

1. `cp .env.example .env` y ajustar para desarrollo: `DOMINIO=localhost`, `RED_PROXY=alarma_proxy_dev`,
   `ENTORNO=desarrollo`, `ORIGEN_PERMITIDO=http://localhost:5173,http://localhost:8011`, y claves
   aleatorias (`openssl rand -hex 24`) en `POSTGRES_PASSWORD`, `MQTT_CLAVE` y `CLAVE_CENTRAL`.
2. Red, certificados y usuarios de Mosquitto:

   ```bash
   docker network create alarma_proxy_dev
   ./scripts/generar_certs_mqtt.sh
   ./scripts/usuario_mqtt.sh backend_api "<MQTT_CLAVE del .env>"
   ./scripts/usuario_mqtt.sh casa-dev "<CLAVE_CENTRAL del .env>"
   ```
3. Con los contenedores arriba, un superadmin y la casa del simulador:

   ```bash
   docker compose exec api python -m app.cli crear-superadmin --email admin@ejemplo.com --nombre "Admin"
   docker compose exec api python -m app.cli crear-casa --codigo casa-dev --nombre "Casa de desarrollo" --admin admin@ejemplo.com
   ```

La documentación interactiva de la API queda en http://localhost:8011/api/v1/docs.

**Cada día:**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build   # app en http://localhost:8011
cd frontend && npm install && npm run dev                                     # recarga en caliente: http://localhost:5173
cd backend && uv run python ../tools/simulador_central.py --casa casa-dev --clave "<CLAVE_CENTRAL>"
```

**Pruebas y calidad:**

```bash
cd backend && uv run pytest -q && uv run ruff check . ../tools && uv run ruff format --check . ../tools
cd frontend && npm run lint && npm test && npm run build
```

La instalación en el servidor está en la §15 de la arquitectura.
