# Imagen de la API (§5.2). Contexto de build: la raíz del repositorio.

# ---- Etapa 1: compilar el frontend (React) ----
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build                                        # -> /web/dist

# ---- Etapa 2: API ----
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# Solo dependencias, con las versiones exactas de uv.lock: capa reutilizable si no cambian
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requisitos.txt \
 && uv pip install --system --no-cache -r /tmp/requisitos.txt \
 && rm /tmp/requisitos.txt
COPY backend/ ./
COPY --from=web /web/dist ./frontend
RUN useradd --system --uid 10001 app
USER app
EXPOSE 8011
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8011 --workers 1 --proxy-headers --forwarded-allow-ips \"$IPS_PROXY_CONFIABLES\""]
