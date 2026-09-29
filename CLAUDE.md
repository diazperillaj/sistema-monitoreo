# Alarma hogar
Sistema de monitoreo con ESP32. Solo la app: 3 contenedores (mosquitto, api = FastAPI + frontend React compilado en la misma imagen, db = PostgreSQL 17). La app escucha en el puerto 8011 (127.0.0.1:8011 en el host y alarma-api:8011 en la red RED_PROXY). Se publica a través del Caddy que YA existe en el servidor. NO agregar Caddy, nginx ni certbot al proyecto.
- Especificación completa: docs/ARQUITECTURA.md (fuente de verdad).
- Plan de implementación (orden de cada fase y sus dependencias): docs/PLAN_IMPLEMENTACION.md
- El firmware en firmware/ es solo de referencia: NO se modifica.
- Desarrollo: `docker network create alarma_proxy_dev` (una vez) y `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`. La primera vez, además: `.env` local (ver README), `./scripts/generar_certs_mqtt.sh` y `./scripts/usuario_mqtt.sh` para `backend_api` y `casa-dev`. En este equipo PostgreSQL de desarrollo queda en el 5434 (`PUERTO_DB_DEV`).
- Python con uv: `cd backend && uv sync`. Pruebas: `uv run pytest -q` (desde F1 usa testcontainers: requiere Docker). Lint: `uv run ruff check . ../tools && uv run ruff format --check . ../tools`
- Frontend (Node 24): `cd frontend && npm run dev` → http://localhost:5173 (proxy a la API en :8011). Pruebas: `npm test`. Lint: `npm run lint`. TypeScript fijo en ~5.9 (no subir a 7: rompe typescript-eslint y openapi-typescript).
- Tipos de la API en el frontend: `uv run python -m app.cli exportar-openapi > ../frontend/openapi.json` y luego `npm run tipos`.
- Migraciones: desde backend/, contra la base de desarrollo: `DATABASE_URL=postgresql+asyncpg://alarma:<POSTGRES_PASSWORD>@localhost:5434/alarma uv run alembic revision --autogenerate --rev-id <NNNN> -m "..."`, y revisar a mano los índices parciales (§7.3). La API las aplica sola al arrancar.
- Base de desarrollo: superadmin `admin@ejemplo.com` (clave en `ADMIN_DEV_CLAVE` del `.env`) y casa `casa-dev`, la del simulador.
- Simulador de central (desde backend/): `uv run python ../tools/simulador_central.py --casa casa-dev --clave <CLAVE_CENTRAL del .env>`; escribe `ayuda` para ver el menú. También lee órdenes por tubería, una por línea (`w <s>` espera), para guionar escenarios.
- Notificaciones: Web Push (base) + Telegram opcional por usuario (long polling, sin webhook). Con TELEGRAM_BOT_TOKEN vacío el canal se desactiva.
- Fase actual: F4b (F0 a F4 terminadas; F4b es opcional)

## Cómo trabajar en este repo
- Antes de cada fase, releer en docs/ARQUITECTURA.md la fase (§14) y las secciones que cita.
- Una fase a la vez: terminarla con sus pruebas en verde y su criterio de "hecho" antes de pasar a la siguiente.
- Al cerrar cada fase: agregar a docs/PRUEBAS_MANUALES.md cómo probarla a mano (qué hacer y qué se debe ver), comprobando cada paso; un commit y push a GitHub (github.com/diazperillaj/sistema-monitoreo, rama main); después, esperar la revisión del usuario antes de empezar la siguiente.
- Si algo del documento es ambiguo o parece requerir tocar el firmware, detenerse y preguntar.
