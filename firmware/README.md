# Firmware de referencia (solo lectura)

Código de Arduino de las 5 ESP32 del sistema. **No se modifica** desde este repo: el backend se adapta a él.
El contrato completo está en `docs/ARQUITECTURA.md`, §4.

| Carpeta | ESP32 |
|---|---|
| `gateway_puerta/` | Puerta de entrada + **central** (ESP-NOW ↔ MQTT) y app local `http://alarma.local` |
| `nodo_habitacion/` | Habitación (PIR) |
| `nodo_bano/` | Baño (PIR) |
| `nodo_cocina_agua/` | Cocina · agua (sensor de flujo) |
| `nodo_cocina_gas/` | Cocina · gas (MQ + DS18B20 + PIR) |

Lo que le importa al backend:

- `*/protocolo.h`: bits de alarmas, habilitado y flags (espejo en `backend/app/protocolo.py` y `frontend/src/dominio/protocolo.ts`).
- `gateway_puerta/gateway_puerta.ino`: `jsonEstado()` (payload de `casa/<ID>/estado`), `atenderMqtt()` (conexión, LWT, publicación) y `procesarComandoRemoto()` (formato de `casa/<ID>/cmd`).

Para conectar la central a este servidor solo se cambian valores de configuración en `gateway_puerta.ino` (ver §12.9):
`MQTT_HOST = "sistemamonitoreo.duckdns.org"`, `MQTT_PUERTO = 8883`, `MQTT_USUARIO` = `ID_CASA`, `MQTT_CLAVE` y `#define USAR_TELEGRAM 0`.
