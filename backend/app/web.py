"""FastAPI sirve el build de React (§6.7): así la app no depende del Caddy compartido.

Orden de registro, después de los routers de la API: 404 JSON para /api/* y /ws/*,
los archivos del build y, al final, el respaldo SPA que devuelve index.html.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings

METODOS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
RUTAS_DOCS = ("/api/v1/docs", "/api/v1/docs/oauth2-redirect")

# Swagger UI carga su JS y su CSS de jsDelivr e inicia con un script en línea.
CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)


def politica_csp(settings: Settings) -> str:
    conectar = f"'self' wss://{settings.dominio}"
    if settings.entorno == "desarrollo":
        conectar += " ws://localhost:*"
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "  # atributos style de Recharts y Radix
        "img-src 'self' data:; "
        f"connect-src {conectar}; "
        "worker-src 'self'; "
        "manifest-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )


def cache_control(ruta: str, estado: int) -> str:
    if estado >= 400 or ruta.startswith("/api/"):
        return "no-store"
    if ruta.startswith("/assets/"):
        return "public, max-age=31536000, immutable"  # Vite pone un hash en cada nombre
    if ruta.startswith("/icons/"):
        return "public, max-age=604800"
    return "no-cache"  # index.html, sw.js y manifest: la PWA debe ver las versiones nuevas


class CabecerasSeguridad:
    """Cabeceras de seguridad y de caché en todas las respuestas HTTP (§6.7)."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.csp = politica_csp(settings)
        self.hsts = settings.entorno == "produccion"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ruta: str = scope["path"]

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                cabeceras = MutableHeaders(scope=mensaje)
                cabeceras["X-Content-Type-Options"] = "nosniff"
                cabeceras["Referrer-Policy"] = "strict-origin-when-cross-origin"
                cabeceras["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                cabeceras["Content-Security-Policy"] = CSP_DOCS if ruta in RUTAS_DOCS else self.csp
                cabeceras["Cache-Control"] = cache_control(ruta, mensaje["status"])
                if self.hsts:
                    cabeceras["Strict-Transport-Security"] = "max-age=31536000"
            await send(mensaje)

        await self.app(scope, receive, enviar)


def archivo_del_build(directorio: Path, ruta: str) -> Path | None:
    """El archivo del build que corresponde a `ruta`, o None si no existe o sale del directorio."""
    base = directorio.resolve()
    candidato = (base / ruta).resolve()
    if candidato.is_relative_to(base) and candidato.is_file():
        return candidato
    return None


def montar_frontend(app: FastAPI, directorio: Path) -> None:
    @app.api_route("/api/{resto:path}", methods=METODOS, include_in_schema=False)
    async def api_inexistente(resto: str) -> None:
        # También lo espera la app local de la ESP32: en este dominio, /api/estado da 404 (§3.4).
        raise HTTPException(
            404, {"codigo": "no_encontrado", "mensaje": "Ruta de la API inexistente."}
        )

    @app.api_route("/ws/{resto:path}", methods=METODOS, include_in_schema=False)
    async def ws_por_http(resto: str) -> None:
        raise HTTPException(
            404, {"codigo": "no_encontrado", "mensaje": "Esta ruta es solo WebSocket."}
        )

    if (directorio / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=directorio / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    async def respaldo_spa(ruta: str) -> Response:
        archivo = archivo_del_build(directorio, ruta) if ruta else None
        if archivo is not None:
            return FileResponse(archivo)  # sw.js, manifest.webmanifest, icons/…
        if ruta.startswith("assets/"):
            return PlainTextResponse("No encontrado.", status_code=404)
        index = directorio / "index.html"
        if not index.is_file():
            return PlainTextResponse("Frontend no compilado.", status_code=503)
        return FileResponse(index)  # rutas del cliente: /casa/1, /invitacion/<token>…
