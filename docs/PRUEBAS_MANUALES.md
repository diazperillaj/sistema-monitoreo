# Pruebas a mano

Qué hacer y qué deberías ver para comprobar cada fase con tus propios ojos, en el entorno de desarrollo. Complementa las pruebas automáticas (`cd backend && uv run pytest -q`), que repiten estos casos y muchos más en medio minuto.

Se prueba con estas herramientas:

- **La app**, en Chrome: http://localhost:8011 (desde F5 tiene tablero, historial y perfil; desde F6, gráficas, ajustes e invitaciones).
- **El simulador**, en una terminal: hace de central y de nodos. Ahí disparas alarmas, apagas nodos o cortas la conexión, y ves llegar los comandos.
- **La página `/api/v1/docs`** (para F1 a F4), en el navegador: pregunta y ordena a la API con botones.
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
| Abrir http://localhost:8011 | La pantalla de entrada "Monitoreo del hogar" |
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

Se usa **Chrome** (o Edge). El navegador que trae la app de Claude no permite notificaciones. Desde F5, todo esto está en **Perfil**, en la tarjeta "Alertas en este dispositivo".

### En el computador

| # | Qué haces | Qué debes ver |
|---|---|---|
| 1 | Abrir http://localhost:8011, entrar e ir a **Perfil** | La tarjeta "Alertas en este dispositivo" con **Activar en este dispositivo** |
| 2 | **Activar en este dispositivo** y aceptar el permiso de Chrome | "Listo: este dispositivo recibirá las alertas" y, en la tarjeta, "Este dispositivo recibe las alertas" |
| 3 | **Enviar una prueba** | En un segundo, la notificación de Windows "🔔 Notificación de prueba". Si no aparece, revisa que Windows no esté en "No molestar" y que tenga permitidas las notificaciones de Chrome. |
| 4 | Simulador: `a 2` | En menos de 5 s, "🚨 Baño — Sin movimiento por 10 min · (nombre de la casa)", con el botón **Silenciar**. |
| 5 | Tocar **Silenciar** en esa notificación | En el simulador, `[cmd] 2:silenciar:0`. Llega "🔕 Baño — (tu nombre) la silenció". |
| 6 | Simulador: `c`, y esperar un minuto | "📡 Central desconectada — Sin datos desde las HH:MM". Con `c` otra vez: "✅ Central en línea". |
| 7 | Para ver los recordatorios sin esperar: en `/docs`, `PATCH /casas/{casa_id}/ajustes` con `{"recordatorio_min": 1, "recordatorio_conexion_min": 1}`. Luego, en el simulador, `a 2` y `x 3` | A los ~20 s, "⚠️ Cocina · agua sin conexión". Entre 1 y 1,5 min después de cada aviso, "⏰ Sigue activa: Baño" y "⏰ Sigue sin conexión: Cocina · agua". Al terminar, devuelve los dos valores a los de antes. |
| 8 | **Desactivar aquí** | Desde ahí, ese navegador ya no recibe nada. |

### En tu Android, con un cable USB

El celular necesita abrir la app en una dirección segura. `localhost` lo es, así que Chrome la "presta" del computador por el cable:

1. En el celular: **Ajustes → Acerca del teléfono**, tocar 7 veces **Número de compilación**. Después, en **Opciones de desarrollador**, activar **Depuración por USB**.
2. Conectarlo al computador. En Chrome del computador, abrir `chrome://inspect/#devices` y aceptar el aviso que sale en el celular.
3. **Port forwarding…** → puerto `8011` → `localhost:8011` → marcar **Enable port forwarding** → **Done**.
4. En Chrome del celular, abrir http://localhost:8011 y repetir los pasos 1 a 5 de la tabla anterior. Prueba el paso 4 **con el celular bloqueado**: la alarma debe verse en la pantalla de bloqueo y vibrar.

El aviso llega por internet (por Google), no por el cable. El cable solo hace falta para abrir la página y para que funcione el botón **Silenciar**.

Web Push no suena si el celular está en silencio o en "No molestar". Para eso está Telegram (F4b).

## F5 · La app: tablero, historial y perfil

Todo en Chrome, en http://localhost:8011, con el simulador encendido. Para verla como en el celular: F12 → el ícono de celular (arriba a la izquierda de las herramientas) → un modelo como "iPhone 12 Pro". Para cambiar el código y verlo al instante: `cd frontend && npm run dev` y abrir http://localhost:5173.

### Entrar

| # | Qué haces | Qué debes ver |
|---|---|---|
| 1 | Sin sesión, abrir http://localhost:8011/casa/1/historial | La pantalla de entrada "Monitoreo del hogar". |
| 2 | Tocar **Entrar** sin escribir nada | Junto a cada campo: "Escribe tu email." y "Escribe tu clave." |
| 3 | Entrar con una clave equivocada | "Email o clave incorrectos." debajo de la clave. |
| 4 | Entrar bien | Llega al historial de la casa: vuelve a donde ibas. |

### El tablero

| # | Qué haces | Qué debes ver |
|---|---|---|
| 5 | Tocar **Tablero** | Arriba, el nombre de la casa y "● En vivo". Debajo, la franja del momento ("Día: cada cuarto vigila…", o noche, o madrugada) con la hora de la central. Luego los cinco nodos en una sola placa: luz verde, nombre y palanca. Lo que vigila no dice nada más: la luz verde y la palanca a la derecha bastan. |
| 6 | Simulador: `m 2` (alguien entra al baño) | La escala del baño cuenta ("00:05 / 10:00") y avanza cada segundo: las cifras giran como un contador de agua y la aguja negra camina. Al pasar el 25 %, esa marca se oscurece; el último cuarto de la escala es ámbar y el final tiene una raya roja. |
| 7 | Simulador: `a 2` | En menos de 5 s, arriba, el campo rojo: "Alarma · Baño", "Sin movimiento por 10 min", cuánto lleva sonando en cifras grandes y "sonando desde las HH:MM". La tira del baño dice ALARMA y su escala queda llena de rojo. |
| 8 | **Activar sonido** (en el campo rojo) | Un pitido corto; desde ahí pita cada segundo mientras haya alarmas (y vibra en el celular). **Apagar sonido** lo calla: la alarma sigue. El parlante de la barra de arriba hace lo mismo en cualquier momento. |
| 9 | **Silenciar** | "Silenciando…" y, en menos de un segundo, el campo rojo desaparece y la escala vuelve a cero. En el simulador, `[cmd] 2:silenciar:0`. |
| 10 | Simulador: `a 2` y `a 4 gas` | "2 alarmas": una fila por nodo, cada una con su **Silenciar**, y abajo **Silenciar todas**. |
| 11 | **Silenciar todas** | "Silenciando todas…" y el campo desaparece. |
| 12 | Tocar la palanca del Baño | Queda a medio camino con "Enviando…" y en menos de un segundo pasa a apagada: la tira se raya en diagonal y dice "Desactivado". Tócala otra vez para reactivarlo. |
| 13 | Simulador: `x 3` (apaga el nodo del agua) y **enseguida** tocar la palanca de Cocina · agua | "Enviando…" unos 9 s y luego el aviso "La central no confirmó el cambio": la palanca vuelve a donde estaba. Unos 20 s después, la tira dice "Sin conexión · último dato hace …", va rayada y su palanca queda bloqueada. Enciende el nodo con `x 3`. |
| 14 | Simulador: `c` | Arriba "Central desconectada" y una franja oscura "La central está desconectada desde las HH:MM…". Todas las tiras rayadas, con "Sin datos"; las palancas bloqueadas. Con `c` otra vez vuelve "En vivo". |
| 15 | Apagar la API (`docker compose -f docker-compose.yml -f docker-compose.dev.yml stop api`), esperar 30 s y encenderla (`start api`) | La página sigue abierta: "Reconectando…", luego "Cada 5 s" y luego "Sin conexión" con la franja "Sin conexión con el servidor…". Al volver la API, en menos de un minuto regresa "En vivo" sola. |

### Historial y perfil

| # | Qué haces | Qué debes ver |
|---|---|---|
| 16 | **Historial** | Las alarmas por día ("Hoy", "Ayer"…): qué fue, a qué hora, cuánto duró y cómo terminó ("Silenciada por …", "Se apagó en la casa" o "Se cerró al volver la conexión") y cuántos avisos se enviaron. Filtros: el nodo y "Solo abiertas". En **Eventos**, todo lo que pasó, con "Solo alarmas". Al final, **Cargar más** si hay más. |
| 17 | Con el historial abierto, simulador: `a 2` | Arriba aparece una barra roja "Alarma: Baño · Ver tablero" y un punto rojo sobre **Tablero**. **Ver tablero** lleva al campo rojo; silénciala. |
| 18 | **Perfil** | Tu nombre y email. "Alertas en este dispositivo": en Chrome del computador, activar y probar funciona como en F4. "Alertas por notificación": una palanca que pausa los avisos en todos tus dispositivos. "Cambiar la clave": pide 10 caracteres o más y repetirla igual. "Sesiones abiertas": cada dispositivo ("Chrome en Windows"); la tuya dice "Esta sesión" y las demás tienen **Cerrar** (y **Cerrar las otras** si son varias). |
| 19 | **Salir de esta cuenta** | Vuelve a la pantalla de entrada. |

### Pantalla ancha, modo oscuro y versiones

| # | Qué haces | Qué debes ver |
|---|---|---|
| 20 | Ventana del computador a todo el ancho | El tablero en dos columnas: a la izquierda el momento, las alarmas y "Lo último en la central"; a la derecha los instrumentos. Las secciones pasan a la barra de arriba. |
| 21 | Tocar la **luna** de la barra de arriba (junto al parlante); luego el **sol** | Pasa a grafito, sin nada blanco que encandile de noche (el rojo de alarma se oscurece); el sol vuelve al esmalte. Al recargar se queda como lo dejaste, sin destello. En **Perfil → Apariencia**, "Automático" vuelve a seguir el modo de Windows (Configuración → Personalización → Colores). |
| 22 | (Opcional) Con la app abierta, cambiar un texto en `frontend/src`, volver a levantar con `up -d --build api` y recargar la página una vez | "Nueva versión disponible" con el botón **Actualizar**; al tocarlo, la página carga la versión nueva. |

### En el celular (lo pruebas tú)

Esto no lo pude comprobar: necesita tus celulares.

- **Android por cable:** con el cable y el reenvío de puertos de F4, abrir http://localhost:8011 en Chrome del celular y repetir los pasos 5 a 9. En **Perfil** debe aparecer "Instalar la app" (o, en el menú de Chrome, "Instalar app"). Instalada, se abre desde su ícono sin la barra del navegador.
- **iPhone:** necesita la app en el dominio con HTTPS (el servidor). En Safari: **Compartir → Agregar a inicio**, abrirla desde el ícono y en **Perfil → Activar en este dispositivo**. Sin instalar, el perfil muestra esos mismos pasos. Luego, una alarma del simulador del servidor (o de la central real) debe llegar como notificación.

## F6 · Invitar, miembros, ajustes y gráficas

En http://localhost:8011 con tu sesión de admin y el simulador encendido. La persona invitada ("Tomás") necesita **otro perfil de Chrome**: la foto de perfil arriba a la derecha → **Agregar** → **Continuar sin una cuenta**. No sirve una ventana de incógnito: ahí Chrome no deja recibir notificaciones.

### Invitar a alguien

| # | Qué haces | Qué debes ver |
|---|---|---|
| 1 | Tocar **Ajustes** (abajo en el celular, arriba en el computador) | "Ajustes de la casa" con dos pestañas, **Avisos** y **Miembros**. |
| 2 | **Miembros** | En "Personas", tú con la marca "Tú". Tu rol y tu botón **Salir** están bloqueados, con la explicación "La casa necesita al menos un admin: haz admin a otra persona para cambiar este rol." |
| 3 | En "Invitar a alguien", dejar **Cuidador**, escribir un email (por ejemplo `tomas@ejemplo.com`) y **Crear enlace** | El enlace (`http://localhost:8011/invitacion/…`) con **Copiar enlace** y **Compartir** (este, si el navegador sabe compartir; Chrome en Windows sí), y "Sirve una sola vez y vence el … a las …". Abajo, "Enlaces sin usar" lo muestra con el email. |
| 4 | **Copiar enlace** | "Enlace copiado". |
| 5 | En el perfil de Tomás, pegar el enlace | "Te invitaron a string" (el nombre de tu casa) y lo que podrá hacer. El email ya viene escrito. |
| 6 | **Crear cuenta y entrar** sin llenar nada más | Junto a cada campo lo que falta ("Escribe tu nombre.", "La clave necesita al menos 10 caracteres.") y el cursor en el primero. |
| 7 | Escribir el nombre "Tomás" y una clave de 10 caracteres o más, y **Crear cuenta y entrar** | "Ya eres parte de string · Activa las alertas en este celular desde Perfil." y el tablero de la casa, con el aviso "Este dispositivo no recibe alertas". En la navegación **no** aparece **Ajustes**. |
| 8 | En el perfil de Tomás, escribir en la barra `localhost:8011/casa/1/miembros` | Vuelve al tablero: un cuidador no entra ahí. |
| 9 | **Perfil → Activar en este dispositivo** (y permitir las notificaciones) | "Este dispositivo recibe las alertas". |
| 10 | Simulador: `m 2` y luego `a 2` | La notificación "🚨 Baño" llega a los dos perfiles de Chrome: el tuyo y el de Tomás. |
| 11 | Simulador: `s 2` | "🔕 Baño" en los dos. |
| 12 | Abrir otra vez el mismo enlace | "Esta invitación no sirve" y "Esta invitación ya se usó. Pide una nueva a quien te invitó." |
| 13 | En tu perfil, **Miembros** | Tomás aparece como Cuidador y ya no hay "Enlaces sin usar". |
| 14 | **Historial → Eventos** | "Tomás se unió a la casa como cuidador". |

### Cambiar un rol y quitar a alguien

| # | Qué haces | Qué debes ver |
|---|---|---|
| 15 | En **Miembros**, cambiar el rol de Tomás a **Admin** | "Tomás ahora es admin". Tu rol y tu **Salir** se desbloquean: ya hay dos admins. |
| 16 | Volver a poner a Tomás como **Cuidador** y tocar **Quitar** en su fila | Un diálogo "¿Quitar a Tomás de la casa?", que explica que dejará de ver la casa y de recibir sus alertas. **Cancelar** lo cierra sin hacer nada. |
| 17 | **Quitar** otra vez y **Quitar de la casa** | "Tomás ya no es parte de la casa" y su fila desaparece. En **Historial → Eventos**, "Admin de desarrollo quitó a Tomás de la casa" (y los cambios de rol del paso 15 y 16). |
| 18 | En el perfil de Tomás, recargar | Ya no ve la casa: "Tu cuenta todavía no tiene casas." Tampoco le llegan más alarmas. |
| 19 | Crear otro enlace y tocar **Anular** en "Enlaces sin usar"; luego abrir ese enlace en el perfil de Tomás | "Enlace anulado: ya no sirve" y, arriba, vuelve el formulario de invitar: ya no ofrece copiar un enlace muerto. Al abrirlo: "Esta invitación no sirve" y "Puede que el enlace esté incompleto o que lo hayan anulado." |

### Ajustes de la casa

| # | Qué haces | Qué debes ver |
|---|---|---|
| 20 | **Ajustes → Avisos** | El nombre de la casa, los tres recordatorios en minutos (alarma, conexión y cuándo avisar que la central se desconectó), cada uno con una frase de qué cambia, y dos palancas: "Nodo sin conexión" y "Alarma resuelta". **Guardar cambios** está bloqueado: "Sin cambios por guardar." |
| 21 | Cambiar "Repetir el aviso de una alarma cada" a 10, apagar "Alarma resuelta" y **Guardar cambios** | "Ajustes guardados". Al recargar siguen así. Déjalos luego como estaban. |
| 22 | Escribir 0 en "Avisar que la central se desconectó después de" y tocar **Guardar cambios** | Debajo del campo, "Un número entre 1 y 1440." con un ícono de alerta. El botón no se bloquea (como en el resto de la app), pero no guarda: lleva el cursor a ese campo. Vuelve a poner 1. |
| 23 | Cambiar el nombre de la casa y guardar | El nombre nuevo aparece arriba, en la barra. |

### Gráficas

| # | Qué haces | Qué debes ver |
|---|---|---|
| 24 | **Gráficas** | "Alarmas de los últimos 7 días": el total, el tiempo promedio para silenciar, cuántas de cada tipo y una barra por día (rojo, de los sensores; gris, de conexión). Debajo, temperatura, sensor de gas y agua de la cocina de las últimas 24 horas: cada una con su último valor ("Ahora" o "Último, HH:MM"), el máximo y el mínimo. Donde la central no mandó datos, la línea se corta. |
| 25 | Pasar el mouse (o el dedo) por una gráfica | Una burbuja con el valor y la hora. |
| 26 | **Ver los datos** | La misma serie en una tabla, de la más reciente a la más antigua. |
| 27 | **7 días** | Las tres gráficas pasan a la semana, con los siete días en el eje. Con el foco en el selector, las flechas del teclado también cambian el periodo. |
| 28 | Ventana a todo el ancho | Dos columnas: las alarmas a la izquierda, quietas al bajar, y las lecturas a la derecha. |

### Al otro día (lo compruebas tú)

- **Limpieza de madrugada:** si la API quedó encendida a las 3:00, `docker compose logs api | grep Mantenimiento` muestra una línea como `Mantenimiento: eventos 0, lecturas 0, sesiones 1, invitaciones 0`: cuántas filas viejas borró de cada tabla (eventos de más de 180 días, lecturas de más de 90, sesiones vencidas e invitaciones usadas o vencidas hace más de 30).
- **En tu celular:** la invitación también se puede abrir allí, con el reenvío de puertos de F4. **Compartir** abre el menú del celular (WhatsApp, etc.).

## Lo que todavía no se puede probar

- Telegram (y su sección del perfil): F4b.
- La central ESP32 real y el dominio público con su configuración de producción: F7.
