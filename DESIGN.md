---
name: Monitoreo del hogar
description: Instrumentos de la casa. Cada nodo es un medidor que muestra cuánto falta para su alarma.
colors:
  suelo: "#e4e9e8"
  cara: "#f9fbfa"
  cara-2: "#eef2f1"
  filo: "#c9d2d0"
  marca: "#8e9a98"
  tinta: "#14191b"
  tinta-2: "#4b585c"
  tinta-3: "#66747a"
  alarma: "#c42b21"
  alarma-campo: "#c42b21"
  sobre-alarma: "#ffffff"
  sobre-alarma-2: "#ffe3e0"
  ambar: "#c07a06"
  ambar-tinta: "#8a5300"
  ambar-fondo: "#fbeed3"
  verdin: "#1f7a64"
  verdin-fondo: "#dcefe8"
  aviso: "#14191b"
  sobre-aviso: "#f9fbfa"
typography:
  monumental:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "3.25rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.01em"
    fontFeature: "\"tnum\" 1"
  lectura-escala:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.01em"
    fontFeature: "\"tnum\" 1"
  headline:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 600
    lineHeight: "1.75rem"
  title:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: "1.5rem"
  body:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: "1.5rem"
  body-sm:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: "1.25rem"
  nav:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: "1.125rem"
  rotulo:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: "1rem"
    letterSpacing: "0.08em"
rounded:
  pista: "2px"
  mando: "4px"
  tecla: "6px"
  placa: "10px"
  luz: "9999px"
spacing:
  tacto: "44px"
  margen: "16px"
  pila: "16px"
  columna: "24px"
  barra: "56px"
components:
  button-primario:
    backgroundColor: "{colors.tinta}"
    textColor: "{colors.cara}"
    rounded: "{rounded.tecla}"
    height: "44px"
    padding: "0 16px"
  button-secundario:
    backgroundColor: "{colors.cara}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.tecla}"
    height: "44px"
    padding: "0 16px"
  button-secundario-hover:
    backgroundColor: "{colors.cara-2}"
  button-discreto:
    textColor: "{colors.tinta-2}"
    rounded: "{rounded.tecla}"
    height: "44px"
    padding: "0 16px"
  button-discreto-hover:
    backgroundColor: "{colors.cara-2}"
    textColor: "{colors.tinta}"
  button-sobre-alarma:
    backgroundColor: "{colors.sobre-alarma}"
    textColor: "{colors.alarma-campo}"
    rounded: "{rounded.tecla}"
    height: "56px"
    padding: "0 24px"
  button-contorno-alarma:
    textColor: "{colors.sobre-alarma}"
    rounded: "{rounded.tecla}"
    height: "44px"
    padding: "0 12px"
  campo:
    backgroundColor: "{colors.cara}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.tecla}"
    height: "48px"
    padding: "0 12px"
  placa:
    backgroundColor: "{colors.cara}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.placa}"
    padding: "12px 16px"
  campo-alarmas:
    backgroundColor: "{colors.alarma-campo}"
    textColor: "{colors.sobre-alarma}"
    rounded: "{rounded.placa}"
    padding: "12px 20px 20px"
  palanca:
    backgroundColor: "{colors.cara-2}"
    rounded: "{rounded.tecla}"
    width: "52px"
    height: "32px"
  aviso-conexion:
    backgroundColor: "{colors.aviso}"
    textColor: "{colors.sobre-aviso}"
    rounded: "{rounded.tecla}"
    padding: "10px 16px"
  aviso-conexion-leve:
    backgroundColor: "{colors.cara-2}"
    textColor: "{colors.tinta-2}"
    rounded: "{rounded.tecla}"
    padding: "10px 16px"
  chip-activo:
    backgroundColor: "{colors.verdin-fondo}"
    textColor: "{colors.verdin}"
    rounded: "{rounded.mando}"
    padding: "2px 6px"
---

# Design System: Monitoreo del hogar

## Overview

**Creative North Star: "Instrumentos de la casa"**

La app es un tablero de medidores domésticos, como el contador del agua o el tablero de breakers. Cada nodo es una tira-instrumento montada sobre un panel: una escala lineal calibrada que dice cuánto falta para la alarma, no solo si sonó, con su luz piloto y su palanca. De día los instrumentos son esmalte blanco sobre acero gris; de noche, grafito sobre casi negro, sin negro puro ni brillo, porque se mira recién despierto.

El color es señal, no decoración. Rojo, ámbar y verdín tienen cada uno un único trabajo y fuera de él no aparecen; todo lo demás es tinta sobre esmalte. Las cifras son de odómetro (tabulares, en ruedas que giran) y los rótulos son de placa estampada. Lo que no vigila no se distingue solo con un color: va rayado a 45°. La densidad es de herramienta de uso diario en el celular: una columna, tiras apiladas, objetivos táctiles de 44 px y una escala fija de texto, no de afiche.

Rechazo confirmado: la cuadrícula de tarjetas con ícono e interruptor de las apps de casa inteligente.

**Key Characteristics:**
- Día esmalte / noche grafito, conmutados solo por `prefers-color-scheme` (también el `theme-color` del navegador: `cara` de cada esquema).
- Escalas calibradas de 20 tramos con escalones al 25, 50 y 75 % que se encienden al cruzarlos.
- Cifras de odómetro en Barlow Semi Condensed tabular; texto en Barlow.
- Un campo rojo a todo el ancho es la única superficie roja.
- Rayado a 45° para todo lo que no vigila.
- Movimiento mecánico y corto; la única animación perpetua es el latido de la luz de alarma.

## Colors

Neutros de acero y esmalte con tres señales de un solo uso cada una. Los valores del frontmatter son los de día; la noche redefine los mismos tokens en `@media (prefers-color-scheme: dark)` (valores en el sidecar) y los componentes solo usan los nombres.

### Primary
- **Tinta de grafito** (`tinta`): texto principal, botón primario, aguja de la escala, escalones cruzados, marca de pestaña activa, anillo de foco. El recorrido de la escala es esta misma tinta al 25 %. De noche es blanco hueso.

### Secondary
- **Rojo de señal** (`alarma`, `alarma-campo`, `sobre-alarma`, `sobre-alarma-2`): solo alarma. `alarma` pinta la luz de alarma, la palabra ALARMA y el texto de alarma de un instrumento, la lectura y el relleno en el límite, la raya del límite al final de cada escala y el punto de alarma sobre "Tablero" en la navegación. `alarma-campo` es el fondo del campo rojo y de la franja "alarma fuera del tablero"; de noche baja a un rojo oscuro para no encandilar. `sobre-alarma` y `sobre-alarma-2` son el texto y el texto secundario encima.

### Tertiary
- **Ámbar de último tramo** (`ambar`, `ambar-tinta`, `ambar-fondo`): solo el último cuarto de una escala. `ambar-fondo` tiñe la pista del 75 al 100 %; `ambar` es el relleno cuando la lectura entra ahí (gráfico, ≥ 3:1); `ambar-tinta` es la lectura en cifras en ese tramo (texto, ≥ 4.5:1).
- **Verdín de vigilancia** (`verdin`, `verdin-fondo`): solo señales pequeñas de "vigilando" o "activo": la luz piloto, la ranura piloto de la palanca encendida, el punto de "Este dispositivo recibe las alertas", la etiqueta "Esta sesión" (texto `verdin` sobre `verdin-fondo`), el cursor de texto y la selección (al 28 %).

### Neutral
- **Acero** (`suelo`): el panel de fondo donde van montadas las placas.
- **Esmalte** (`cara`): la cara de cada instrumento, la barra superior, la navegación y los campos.
- **Esmalte hundido** (`cara-2`): pistas de escala, palancas, hover de botones, pestaña activa de la barra, esqueletos de carga, aviso leve.
- **Filete** (`filo`): el filete de 1 px de placas, campos y divisores.
- **Marca** (`marca`): las marcas finas de la escala, la luz apagada, el rayado y la barra de desplazamiento.
- **Tinta 2 y 3** (`tinta-2`, `tinta-3`): texto secundario y terciario, rótulos, estados sin datos, el mando de la palanca apagada.
- **Aviso** (`aviso`, `sobre-aviso`): la franja de "central desconectada" o "sin conexión": tinta invertida de día, grafito elevado de noche (nunca una franja casi blanca a oscuras). El retraso usa la variante leve en `cara-2` con filete.

### Named Rules
**The Solo Alarma Rule.** El rojo es solo de alarma: el campo rojo, la palabra ALARMA, las luces de alarma, la raya del límite y el relleno en el límite. Ningún error, borrado ni validación usa rojo.

**The Último Cuarto Rule.** El ámbar vive solo en el último cuarto de una escala. No hay advertencias ámbar en otro sitio.

**The Verdín Piloto Rule.** El verdín es una señal pequeña de "vigilando" (luz, ranura piloto, punto, etiqueta), nunca un relleno grande ni una superficie.

**The Nunca Solo Color Rule.** Cada luz va acompañada de una palabra ("Vigilando", "ALARMA", "Sin conexión"), y lo que no vigila además va rayado.

## Typography

**Display Font:** Barlow Semi Condensed (con Barlow, system-ui)
**Body Font:** Barlow (con system-ui, -apple-system, Segoe UI, Roboto)
**Label/Mono Font:** Barlow Semi Condensed en cifras tabulares

**Character:** Una grotesca industrial de letreros y su versión semi condensada: la de texto se lee tranquila, la condensada pone números de contador y letra estampada de placa. Ambas autoalojadas con @fontsource (400, 500 y 600 de Barlow; 500 y 600 de la semi condensada). Escala fija en rem, razón cercana a 1.2.

### Hierarchy
- **Monumental** (600, 3.25rem, interlineado 1, cifras): la duración de una alarma única dentro del campo rojo, y el "404". Nada más.
- **Lectura de escala** (600, 1.375rem, interlineado 1, cifras): la lectura en odómetro sobre cada escala y en las filas de varias alarmas; va seguida de "/ límite" en 0.875rem `tinta-3`.
- **Headline** (600, 1.375rem, 1.75rem): el título de cada pantalla (Historial, Perfil, Tus casas, Login, 404).
- **Title** (600 o 500, 1.125rem, 1.5rem): el título del campo rojo y su causa, títulos de estados vacíos o de error, el botón grande ("Silenciar").
- **Body** (400, 1rem, 1.5rem): texto corriente; los nombres de nodo y los títulos de placa (h2) en 600. Campos a 16 px siempre, para que iPhone no acerque.
- **Body pequeño** (400 o 500, 0.875rem, 1.25rem): estados, ayudas, bitácora, avisos, franja del momento.
- **Navegación** (500, 0.8125rem, 1.125rem): el texto bajo cada ícono de la barra inferior y las etiquetas pequeñas.
- **Rótulo** (600, 0.75rem, 0.08em, MAYÚSCULAS, `tinta-2`): la letra de placa de cada medidor, de los datos de un instrumento ("SIN MOVIMIENTO", "HORARIO"), del mando del sub-instrumento y la placa "Movimiento ahora" (en `tinta`).

### Named Rules
**The Cifras Rule.** Toda hora, duración o lectura va en cifras tabulares de la semi condensada; las lecturas que cambian van en odómetro.

**The Rótulo De Placa Rule.** El rótulo en mayúsculas espaciadas es solo para nombrar una medida, un dato o un mando de un instrumento. Nunca va encima de un título como antetítulo, ni en tarjetas o pantallas de formulario: cada placa se titula con su propio h2.

## Layout

Celular primero, una sola columna. Margen lateral de 16 px, pila vertical de 16 px entre bloques, contenido a 42rem de ancho máximo; Login, 404 y el error de conexión van en una columna angosta de 24rem. Barra superior pegajosa de 56 px (nombre de la casa, luz de conexión, sonido) con `safe-area-inset-top` (`viewport-fit=cover`); en el celular la navegación va abajo, fija, de 56 px con sus íconos y `safe-area-inset-bottom`; desde `md` (768 px) sube a la barra superior. El tablero en `lg` (1024 px) se abre a 72rem en una rejilla de 4fr/7fr con 24 px de separación: a la izquierda el riel (franja del momento, campo rojo, aviso de canal, bitácora de la central); a la derecha las tiras-instrumento. El campo rojo, los avisos de conexión y la franja de alarma llegan a los bordes de la pantalla en el celular (margen negativo) y se redondean desde `sm` (640 px). Todo objetivo táctil mide al menos 44 px; la palanca amplía su zona a 48 px.

## Elevation & Depth

Casi plano: la profundidad es de placa montada, no de tarjeta flotante. Una placa de esmalte se separa del acero con un filete de 1 px y una sombra corta y baja; nada más proyecta sombra salvo el mando de la palanca y la pestaña elegida del historial. De noche el color de la sombra (`--sombra`, un triplete RGB) pasa a negro y el contraste lo hace el cambio de tono entre `suelo` y `cara`.

### Shadow Vocabulary
- **Placa** (`box-shadow: 0 0 0 1px var(--filo), 0 1px 0 1px rgb(var(--sombra) / 0.04), 0 10px 24px -14px rgb(var(--sombra) / 0.22)`): placas de instrumentos, bitácora, formularios, listas, avisos de canal y toasts.
- **Mando** (`box-shadow: 0 1px 2px rgb(var(--sombra) / 0.35)`): el mando de la palanca, que es la única pieza que "sobresale".
- **Pestaña activa** (`box-shadow: 0 0 0 1px var(--filo), 0 1px 2px rgb(var(--sombra) / 0.12)`): el segmento elegido del selector del historial.

### Named Rules
**The Montado Rule.** Las superficies están montadas en el panel, no flotan: filete de 1 px primero, sombra corta después. Sin sombras de hover ni elevaciones apiladas.

## Shapes

Esquinas cortas de aparato. Placas a 10 px; teclas, campos, palancas y avisos a 6 px; mando, etiquetas y esqueletos a 4 px; pista de escala a 2 px. Las luces piloto son círculos de 10 px; las agujas y el límite son rayas de 2 px con puntas redondas. Los bordes se hacen con anillos internos de 1 px en `filo`, no con bordes que empujen el tamaño. El rayado es un gradiente repetido a -45° con líneas de 1 px de `marca` al 34 % cada 7 px. El ícono de la app (generado por tools/generar_iconos.py con Pillow) repite la forma: un techo sobre una escala calibrada, aguja en verdín al 60 %, límite rojo, fondo grafito; la insignia de Android es la misma silueta en blanco.

## Components

### Buttons
Teclas de aparato: responden al presionar (escala 0.97 en 140 ms), y cada una nombra su acción; mientras trabaja dice qué hace ("Silenciando…") y queda deshabilitada.
- **Shape:** esquinas cortas (6 px).
- **Primario:** tinta con texto de esmalte, 44 px de alto, 600; hover a tinta al 90 %.
- **Secundario:** esmalte con anillo de filete; hover a `cara-2`.
- **Discreto:** sin fondo, `tinta-2`; hover a `cara-2` y tinta.
- **Sobre alarma:** blanco con texto rojo, solo dentro del campo rojo; "Silenciar" y "Silenciar todas" van en tamaño grande (56 px, a todo el ancho en el celular); en las filas de varias alarmas, normal.
- **Contorno alarma:** anillo `sobre-alarma` al 55 % sobre el campo rojo (sonido); hover con un velo `sobre-alarma` al 10 %.
- **Tamaños:** compacto 44 px con 12 px de lado, normal 44 px con 16 px, grande 56 px con 24 px. Deshabilitado al 55 % de opacidad.
- **Foco:** contorno de 2 px de tinta a 3 px de distancia, en toda la app.

### Chips
- **Style:** la única etiqueta es "Esta sesión": texto `verdin` 600 sobre `verdin-fondo`, 4 px, en la lista de sesiones.

### Cards / Containers
- **Corner Style:** 10 px.
- **Background:** `cara` sobre `suelo`.
- **Shadow Strategy:** la sombra de placa (ver Elevation & Depth).
- **Border:** filete de 1 px incluido en la sombra; las tiras y filas de una placa se dividen con `filo`.
- **Internal Padding:** 16 px a los lados; 12 a 20 px arriba y abajo según el contenido. Cada placa se titula con su h2 (1rem, 600) adentro.

### Inputs / Fields
- **Style:** 48 px de alto, esmalte, anillo interno de filete, 6 px; rótulo arriba en 0.875rem 500 (no rótulo de placa).
- **Focus:** anillo de 2 px de tinta.
- **Error / Disabled:** el error va en tinta 500 con un ícono de alerta y el anillo sube a 2 px de `tinta-2`; nunca en rojo. La validación es por campo y el botón de enviar sigue habilitado. Deshabilitado al 55 %. Las claves llevan un botón de mostrar de 48 px.

### Navigation
Celular: barra inferior de esmalte con filete arriba, tres destinos de 56 px (ícono 20 px + texto 0.8125rem); el activo en tinta con una aguja corta de 2 × 32 px arriba, los demás en `tinta-3`. Desde `md`: botones de 44 px en la barra superior, el activo con fondo `cara-2`. Si hay alarma y no se está en el tablero, un punto rojo con anillo de esmalte sobre "Tablero" y, arriba del contenido, la franja roja "Alarma: …  Ver tablero".

### Avisos de conexión
Franja de 0.875rem que entra con `aparece`: `aviso` con `sobre-aviso` cuando la central está desconectada o no hay conexión; la variante leve (`cara-2`, `tinta-2`, filete) cuando solo hay retraso.

### Escala calibrada (firma)
Veinte tramos: marcas finas de 4 px en `marca`, escalones de 8 px al 25, 50 y 75 % que pasan a tinta al cruzarlos (200 ms). Pista de 8 px en `cara-2` con filete y el último cuarto teñido de `ambar-fondo`. El recorrido se rellena con tinta al 25 %; en el último cuarto, `ambar`; en el límite, `alarma`. Una raya roja de 2 × 20 px marca el límite al final. La aguja es una raya de tinta de 2 × 16 px que sube lineal en 1 s al ritmo del reloj y vuelve a cero en 300 ms con `--ease-salida`; en el límite desaparece y queda el relleno rojo. Rótulo de placa a la izquierda y lectura en odómetro a la derecha; sin datos al día la escala se ve pero dice "Sin medir".

### Odómetro
Cada dígito es una rueda con interlineado 1 que gira 200 ms con `--ease-salida`; la ventana se recorta a la franja de la cifra (de 0.17em a 0.93em) para que a mitad del giro nada asome. Las claves van desde la derecha para que las unidades sigan siendo la misma rueda.

### Luz piloto
Círculo de 10 px: verdín vigilando, rojo latiendo (1.2 s, `--ease-mueve`) en alarma, anillo de 2 px `tinta-2` incierta, anillo de 1 px `marca` apagada. En registros (historial, bitácora de la central) la luz de alarma queda fija, y en la bitácora reemplaza al prefijo "ALARMA".

### Palanca
Palanca de breaker de 52 × 32 px: pista sin relleno en `cara-2` con filete (que pasa a `tinta-3` encendida), mando de grafito de 26 px a 4 px con su muesca. Encendida, el mando va a la derecha en tinta y aparece la ranura piloto verdín; apagada, el mando `tinta-3` queda a la izquierda. "Enviando" es la palanca a medio camino, pulsando mientras espera a la central. Deshabilitada al 50 %.

### Campo rojo
La única superficie roja: a todo el ancho, luz `sobre-alarma` latiendo, "Alarma · Nodo", la causa, la duración en cifras monumentales, "sonando desde las HH:MM" y "Silenciar". Con varias alarmas, una fila por nodo (nombre, causa, lectura en odómetro, "Silenciar") separada por filetes `sobre-alarma` al 25 %, y "Silenciar todas". Entra en 220 ms (opacidad y 6 px desde arriba) con `@starting-style`.

### Tira-instrumento
Una sola fila de cabecera de 44 px: luz, nombre, la palabra de estado solo cuando no está vigilando, la placa "Movimiento ahora" y la palanca. Debajo, la escala principal, la fila de datos con rótulo de placa y, en el nodo con presencia, el mando del sub-instrumento con su rótulo y su escala. "Vigilando" lo dicen la luz y la palanca; en palabras solo va lo que no es normal. Desactivada, sin conexión, esperando o sin datos porque la central no está en línea: rayada.

## Do's and Don'ts

### Do:
- **Do** usar `alarma` solo para alarma: campo rojo, palabra ALARMA, luz de alarma, raya y relleno del límite.
- **Do** limitar el ámbar al último cuarto (75–100 %) de una escala.
- **Do** rayar a 45° todo lo que no vigila (desactivado, sin conexión, esperando, sin datos), además de decirlo en palabras.
- **Do** acompañar cada luz con una palabra; el color nunca va solo.
- **Do** mostrar errores de formulario en tinta con un ícono de alerta, junto al campo o al botón que falló.
- **Do** poner horas, duraciones y lecturas en cifras tabulares, y las que avanzan en odómetro.
- **Do** mantener 44 px de objetivo táctil y campos a 16 px.
- **Do** mover las cosas como piezas mecánicas: aguja 1 s lineal al subir y 300 ms `--ease-salida` al bajar; odómetro 200 ms; entradas de 220 ms sin rebote; presión de 140 ms.
- **Do** respetar `prefers-reduced-motion`: las transiciones y animaciones van a 0 ms.

### Don't:
- **Don't** usar rojo para errores, borrados o validación.
- **Don't** usar el verdín como relleno grande, fondo de sección ni color de marca en la interfaz.
- **Don't** usar ámbar como color de advertencia general.
- **Don't** poner antetítulos (eyebrows) sobre los títulos; el rótulo de placa es solo para medidas, datos y mandos de instrumentos.
- **Don't** animar nada en bucle salvo el latido de la luz de alarma; el pulso de la palanca dura solo mientras espera a la central.
- **Don't** armar una cuadrícula de tarjetas con ícono e interruptor al estilo de casa inteligente.
- **Don't** usar negro puro ni una franja casi blanca de noche.
