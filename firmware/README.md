# Firmware de las ESP32

Código de Arduino de las 5 ESP32 del sistema. Se modifica solo con la aprobación de Juan Pablo: hasta octubre de 2026 el backend se adaptaba a él sin tocarlo; desde la versión 1.18 de la especificación lleva además la medición de la batería.
El contrato completo está en `docs/ARQUITECTURA.md`, §4.

| Carpeta | ESP32 |
|---|---|
| `gateway_puerta/` | Puerta de entrada + **central** (ESP-NOW ↔ MQTT) y app local `http://alarma.local` |
| `nodo_habitacion/` | Habitación (PIR) |
| `nodo_bano/` | Baño (PIR) |
| `nodo_cocina_agua/` | Cocina · agua (sensor de flujo) |
| `nodo_cocina_gas/` | Cocina · gas (MQ + DS18B20 + PIR) |

`protocolo.h` y `bateria.h` deben ser **idénticos en las 5 carpetas**, y `nodo_espnow.h` en las 4 de los nodos: si cambias uno, cópialo a las demás.

Lo que le importa al backend:

- `*/protocolo.h`: bits de alarmas, habilitado, flags y batería (espejo en `backend/app/protocolo.py` y `frontend/src/dominio/protocolo.ts`).
- `gateway_puerta/gateway_puerta.ino`: `jsonEstado()` (payload de `casa/<ID>/estado`), `atenderMqtt()` (conexión, LWT, publicación) y `procesarComandoRemoto()` (formato de `casa/<ID>/cmd`).

Para conectar la central a este servidor se cambian valores de configuración en `gateway_puerta.ino` (ver §12.9):
`MQTT_HOST = "sistemamonitoreo.duckdns.org"`, `MQTT_PUERTO = 8883`, `MQTT_USUARIO` = `ID_CASA`, `MQTT_CLAVE` y `#define USAR_TELEGRAM 0`.
En el repositorio esos valores (y el WiFi) están de ejemplo: al cargar una placa desde aquí, pon los tuyos.

## Batería (las 5 placas)

Cada ESP32 lleva una batería de litio de 3.7 V y 1000 mAh. Para medirla:

```
BAT+ ── 220 kΩ ──┬── 220 kΩ ── GND
                 ├── D34
                 └── 100 nF ── GND
```

- El D34 ve la mitad del voltaje (4.20 V → 2.10 V). **El condensador de 100 nF es necesario**: con resistencias de 220 kΩ, sin él la lectura salta.
- **Nodo de gas:** el sensor MQ pasa del D34 al **D35** (`PIN_MQ` en `nodo_cocina_gas.ino`). Mueve ese cable.
- Si una placa va sin batería, deja el divisor (el D34 queda a 0 V) o no conectes nada: la app no muestra batería para ese nodo.

Qué hace `bateria.h`:

- Mide cada segundo y calcula el porcentaje con la curva de una celda de litio (4.15 V = 100 %, 3.82 V = 50 %, 3.30 V = 0 %).
- **"Cargando" se deduce del voltaje**: al conectar el cargador el voltaje sube de golpe y sigue subiendo; al quitarlo, baja. Puede equivocarse unos minutos, y si la placa arranca ya conectada al cargador puede no notarlo hasta desconectarla y volverla a conectar.
- Marca la batería **baja** al 10 % (hasta que cargue o pase del 20 %) y **llena** al 100 % cargando (hasta desconectarla): el servidor manda una notificación en cada caso. No son alarmas: el buzzer no suena.
- El monitor serie (115200) muestra la batería en cada línea de diagnóstico, por ejemplo `batería 87 % (4.04 V)`. Compara ese voltaje con un multímetro: si difiere mucho, ajusta `BAT_DIVISOR` en `bateria.h` (en las 5 carpetas).

**Autonomía:** la ESP32 está siempre encendida y gasta unos 80 a 120 mA, así que 1000 mAh dan de 8 a 12 horas (menos en el gateway, que además mantiene el MQTT). Con el cargador conectado, la batería sirve de respaldo cuando se va la luz.

## Compilar sin el IDE

Con el `arduino-cli` que trae el IDE (núcleo `esp32:esp32` 3.x; librerías PubSubClient, OneWire y DallasTemperature):

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/nodo_bano
```
