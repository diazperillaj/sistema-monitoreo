# Alarma hogar
Sistema de monitoreo con ESP32. Solo la app: 3 contenedores (mosquitto, api = FastAPI + frontend React compilado en la misma imagen, db = PostgreSQL 17). La app escucha en el puerto 8011 (127.0.0.1:8011 en el host y alarma-api:8011 en la red RED_PROXY). Se publica a través del Caddy que YA existe en el servidor. NO agregar Caddy, nginx ni certbot al proyecto.
- Especificación completa: docs/ARQUITECTURA.md (fuente de verdad).
- Plan de implementación (orden de cada fase y sus dependencias): docs/PLAN_IMPLEMENTACION.md
- El firmware en firmware/ es solo de referencia: NO se modifica.
- Desarrollo: `docker network create alarma_proxy_dev` (una vez) y `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
- Pruebas: `cd backend && pytest -q` (usa testcontainers: requiere Docker). Lint: `ruff check . && ruff format --check .`
- Frontend (Node 24): `cd frontend && npm run dev` → http://localhost:5173 (proxy a la API en :8011). Pruebas: `npm test`. Lint: `npm run lint`. TypeScript fijo en ~5.9 (no subir a 7: rompe typescript-eslint y openapi-typescript).
- Tipos de la API en el frontend: `python -m app.cli exportar-openapi > ../frontend/openapi.json` y luego `npm run tipos`.
- Migraciones: `alembic revision --autogenerate -m "..."` y revisar a mano los índices parciales (§7.3).
- Simulador de central: `python tools/simulador_central.py --casa casa-dev --host localhost --puerto 1883`
- Notificaciones: Web Push (base) + Telegram opcional por usuario (long polling, sin webhook). Con TELEGRAM_BOT_TOKEN vacío el canal se desactiva.
- Fase actual: F0

## Cómo trabajar en este repo
- Antes de cada fase, releer en docs/ARQUITECTURA.md la fase (§14) y las secciones que cita.
- Una fase a la vez: terminarla con sus pruebas en verde y su criterio de "hecho" antes de pasar a la siguiente.
- Al cerrar cada fase: un commit y push a GitHub (github.com/diazperillaj/sistema-monitoreo, rama main); después, esperar la revisión del usuario antes de empezar la siguiente.
- Si algo del documento es ambiguo o parece requerir tocar el firmware, detenerse y preguntar.
