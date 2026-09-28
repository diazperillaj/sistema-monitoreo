# Alarma hogar — sistema de monitoreo doméstico

App web (FastAPI + React + PostgreSQL + Mosquitto) para el sistema de alarmas con ESP32.
Se publica en `https://sistemamonitoreo.duckdns.org` a través del Caddy que ya existe en el servidor.

- **Especificación completa:** [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md)
- **Instrucciones para Claude Code:** [`CLAUDE.md`](CLAUDE.md)
- **Firmware de referencia:** [`firmware/`](firmware/)

## Empezar

```bash
git init && git add . && git commit -m "Especificación inicial"
claude
```

Primer mensaje sugerido para Claude Code:

> Lee CLAUDE.md y docs/ARQUITECTURA.md. Implementa solo la fase F0 (§14) completa. Al terminar, muéstrame cómo verificar su criterio de "hecho".
