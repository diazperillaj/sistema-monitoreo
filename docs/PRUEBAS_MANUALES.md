# Pruebas a mano

Qué hacer y qué deberías ver para comprobar cada fase con tus propios ojos, en el entorno de desarrollo. Complementa las pruebas automáticas (`cd backend && uv run pytest -q`), que repiten estos casos y muchos más en medio minuto.

Mientras no exista la app con pantallas (F5), se prueba con tres herramientas:

- **El simulador**, en una terminal: hace de central y de nodos. Ahí disparas alarmas, apagas nodos o cortas la conexión, y ves llegar los comandos.
- **La página `/api/v1/docs`**, en el navegador: pregunta y ordena a la API con botones.
- **La consola del navegador** (opcional): muestra en vivo lo que envía el WebSocket.

## Preparación (cada vez)

1. **Levantar la app** desde la raíz del repo:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
   ```

   Comprobar http://localhost:8011/api/v1/salud: debe decir `"ok": true` y `"mqtt": "conectado"`.

2. **Encender la central simulada** en otra terminal (la clave es `CLAVE_CENTRAL` del `.env`):

   ```bash
   cd backend
   uv run python ../tools/simulador_central.py --casa casa-dev --clave "<CLAVE_CENTRAL>"
   ```

   Debe mostrar `[MQTT] conectado como central-casa-dev` y el menú. Déjala abierta: ahí escribes las órdenes (`a 2`, `s 2`…) y ves llegar los comandos (`[cmd] 2:silenciar:0`). `ayuda` muestra el menú otra vez.

3. **Iniciar sesión en `/docs`:** abrir http://localhost:8011/api/v1/docs, desplegar `POST /api/v1/auth/login`, **Try it out**, poner el cuerpo `{"email": "admin@ejemplo.com", "clave": "<ADMIN_DEV_CLAVE del .env>"}` y **Execute**. Debe responder 200 con tu nombre. Desde ahí esa pestaña queda con la sesión abierta. En cada ruta: **Try it out**, `casa_id` = `1` y **Execute**.

4. **(Opcional) Ver el canal en vivo:** en esa misma pestaña, F12 → **Console**. La primera vez Chrome pide escribir `allow pasting`. Pegar:

   ```js
   const ws = new WebSocket(`ws://${location.host}/ws/v1/casas/1`);
   ws.onmessage = (e) => {
     const m = JSON.parse(e.data);
     if (m.tipo === "estado") return; // llega cada 5 s: se omite para no llenar la consola
     console.log(new Date().toLocaleTimeString(), m.tipo, m.evento ?? "", m.data?.texto ?? m.data?.estado ?? m.online ?? "");
   };
   setInterval(() => ws.send('{"tipo":"ping"}'), 25000);
   ```

   Cada aviso sale como una línea, por ejemplo `10:15:14 comando pendiente` o `10:15:14 evento Admin de desarrollo activó Baño`.

Si algo no cuadra, los registros de la API están en `docker compose logs -f api`.

## F0 y F1 · Base

| Qué haces | Qué debes ver |
|---|---|
| Abrir http://localhost:8011 | La página de la app (por ahora, un esqueleto) |
| `POST /auth/login` con una clave equivocada | 401 "Email o clave incorrectos." |
| `GET /casas` | La casa `casa-dev`, con su estado de conexión y cuántas alarmas tiene abiertas |

## F2 · La app escucha a la central

| # | Qué haces | Qué debes ver |
|---|---|---|
| 1 | `GET /casas/{casa_id}/estado` | `"online": true`, los 5 nodos con `"enLinea": true` y `antiguedad_s` entre 0 y 5. Si lo repites, `recibido_en` avanza. |
| 2 | Simulador: `a 2` (alarma en el baño) | En el estado, `alarmas_abiertas` trae "Sin movimiento por 10 min" del Baño. En la consola: `alarma abre` y el evento. |
| 3 | Simulador: `s 2` (botón del propio nodo) | `GET /alarmas`: esa alarma ya tiene `fin_en` y `"cerrada_por": "central"`. `GET /eventos`: "Baño: Sin movimiento por 10 min · se normalizó". |
| 4 | Simulador: `x 3` (apaga el nodo del agua) y esperar 25 s | Evento "Cocina · agua perdió la conexión" y alarma `NODO_SIN_CONEXION`. |
| 5 | Simulador: `x 3` otra vez | "Cocina · agua volvió a conectarse"; la alarma se cierra con `"cerrada_por": "automatica"`. |
| 6 | Simulador: `a 2` y después `r` (reinicia la central) | La alarma del baño **sigue abierta**: un reinicio no la cierra. En eventos, "Central iniciada" aparece una sola vez. Ciérrala con `s 2`. |
| 7 | Simulador: `c` (corta la conexión) | En segundos, el estado dice `"online": false`. Pasado un minuto (más hasta 10 s), alarma "Central desconectada desde las HH:MM". |
| 8 | Simulador: `c` otra vez | La alarma se cierra sola (`automatica`) y aparece "La central volvió a conectarse". |

## F3 · La app manda órdenes a la central

| # | Qué haces | Qué debes ver |
|---|---|---|
| 1 | Simulador: `a 2`. Luego `POST /casas/{casa_id}/comandos` con `{"nodo": 2, "accion": "silenciar"}` | 202 con `"estado": "pendiente"` y un `id`. En el simulador: `[cmd] 2:silenciar:0` y la alarma se apaga. |
| 2 | `GET /casas/{casa_id}/comandos/{comando_id}` con ese `id` | `"estado": "confirmado"` (tarda menos de 1 s). En `GET /alarmas`: `"cerrada_por": "usuario"` con tu nombre. |
| 3 | `{"nodo": 2, "accion": "desactivar"}` y después `activar` | Los dos confirmados. En el estado, el nodo 2 pasa a `"hab": 0` y vuelve a `1`. |
| 4 | `{"nodo": 4, "accion": "desactivar", "sub": 1}` y después `activar` con `"sub": 1` | Confirmados. El nodo 4 pasa de `"hab": 3` a `1` (se apagó la presencia) y vuelve a `3`. |
| 5 | Simulador: `a 2` y `a 4 gas`. Luego `POST /comandos/silenciar-todo` | Confirmado y `alarmas_abiertas` vacío. |
| 6 | Simulador: `x 3` y **enseguida** `{"nodo": 3, "accion": "desactivar"}` | 202, pero a los ~8 s queda `"sin_confirmar"`: el nodo apagado nunca lo aplicó. Evento "La central no confirmó el comando de …". |
| 7 | Esperar 25 s (el nodo ya figura sin conexión) y repetir | 409 "El nodo no tiene conexión". Vuelve a encenderlo con `x 3`. |
| 8 | Simulador: `c`. Enviar cualquier comando | 409 "La central está desconectada". Reconecta con `c`. |
| 9 | `{"nodo": 2, "accion": "activar", "sub": 1}` | 400: la presencia (`"sub": 1`) solo existe en el nodo 4. |

La habitación (nodo 1) se pausa sola de 22:00 a 06:00, como la real: si pruebas de noche, arranca con `"hab": 0`. Por eso los ejemplos usan el baño.

## F4 · Notificaciones en el computador y en el celular (Web Push)

**Antes:** el `.env` necesita claves VAPID. Se crean con `cd backend && uv run python -m app.cli generar-vapid`; se copian las dos líneas al `.env` y se levanta la app otra vez. http://localhost:8011/api/v1/push/clave-publica debe responder 200.

Se usa **Chrome** (o Edge). El navegador que trae la app de Claude no permite notificaciones. La página de inicio tiene, por ahora, un panel "Notificaciones (prueba)"; en F5 pasa al perfil.

### En el computador

| # | Qué haces | Qué debes ver |
|---|---|---|
| 1 | Abrir http://localhost:8011 y entrar con el email y la clave | "Hola, …" |
| 2 | **Activar notificaciones en este dispositivo** y aceptar el permiso de Chrome | "Listo: este dispositivo quedó suscrito." |
| 3 | **Enviar notificación de prueba** | En un segundo, la notificación de Windows "🔔 Notificación de prueba". Si no aparece, revisa que Windows no esté en "No molestar" y que tenga permitidas las notificaciones de Chrome. |
| 4 | Simulador: `a 2` | En menos de 5 s, "🚨 Baño — Sin movimiento por 10 min · (nombre de la casa)", con el botón **Silenciar**. |
| 5 | Tocar **Silenciar** en esa notificación | En el simulador, `[cmd] 2:silenciar:0`. Llega "🔕 Baño — (tu nombre) la silenció". |
| 6 | Simulador: `c`, y esperar un minuto | "📡 Central desconectada — Sin datos desde las HH:MM". Con `c` otra vez: "✅ Central en línea". |
| 7 | Para ver los recordatorios sin esperar: en `/docs`, `PATCH /casas/{casa_id}/ajustes` con `{"recordatorio_min": 1, "recordatorio_conexion_min": 1}`. Luego, en el simulador, `a 2` y `x 3` | A los ~20 s, "⚠️ Cocina · agua sin conexión". Entre 1 y 1,5 min después de cada aviso, "⏰ Sigue activa: Baño" y "⏰ Sigue sin conexión: Cocina · agua". Al terminar, devuelve los dos valores a los de antes. |
| 8 | **Desactivar en este dispositivo** | Desde ahí, ese navegador ya no recibe nada. |

### En tu Android, con un cable USB

El celular necesita abrir la app en una dirección segura. `localhost` lo es, así que Chrome la "presta" del computador por el cable:

1. En el celular: **Ajustes → Acerca del teléfono**, tocar 7 veces **Número de compilación**. Después, en **Opciones de desarrollador**, activar **Depuración por USB**.
2. Conectarlo al computador. En Chrome del computador, abrir `chrome://inspect/#devices` y aceptar el aviso que sale en el celular.
3. **Port forwarding…** → puerto `8011` → `localhost:8011` → marcar **Enable port forwarding** → **Done**.
4. En Chrome del celular, abrir http://localhost:8011 y repetir los pasos 1 a 5 de la tabla anterior. Prueba el paso 4 **con el celular bloqueado**: la alarma debe verse en la pantalla de bloqueo y vibrar.

El aviso llega por internet (por Google), no por el cable. El cable solo hace falta para abrir la página y para que funcione el botón **Silenciar**.

Web Push no suena si el celular está en silencio o en "No molestar". Para eso está Telegram (F4b).

## Lo que todavía no se puede probar

- Telegram: F4b.
- La app con pantallas (tablero, historial, interruptores) y las notificaciones en iPhone, que exigen instalar la app desde el dominio con HTTPS: F5.
- La central ESP32 real y el dominio público con su configuración de producción: F7.
