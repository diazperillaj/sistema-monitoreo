---
version: 1
slug: "frontend-src-vistas-tablero-tsx"
primary_target: "frontend/src/vistas/Tablero.tsx"
related_targets: ["frontend/src/componentes"]
---

# Tablero de la casa

**Pantalla:** `/casa/:casaId`, la primera que se diseña; las demás heredan su mundo.

**Modo:** Operate.

**Para quién y para qué:**
- Familiares y cuidadores en su celular, de noche (despertados por una alerta) y de día (revisión rápida); los dos momentos pesan igual.
- Tarea: saber si la casa está en orden; si algo suena, ver qué, dónde y desde cuándo, y silenciarlo sabiendo si la central lo confirmó.

**Estados que tiene que resolver:**
- en orden;
- alarma, una o varias;
- nodo sin conexión, desactivado, esperando nodo (tras un reinicio) y en pausa por horario;
- central desconectada, datos con retraso y sin conexión con el servidor;
- comando enviando, confirmado o sin confirmar.

**Restricciones:**
- JS inicial ≤ 150 KB gzip.
- Temas claro y oscuro igual de buenos.
- AA y objetivos táctiles de al menos 44 px.
- Nada infantil ni de juguete.

**Momento memorable:** el contador del baño avanza hacia su marca roja; al llegar, la tira salta al campo rojo y "Silenciar" la devuelve a cero cuando la central confirma.

**Sin resolver:** vistas de admin y gráficas (F6); Telegram (F4b).

## Direction contract

THESIS: Cada nodo es un instrumento que muestra cuánto falta para su alarma, no solo si sonó. Rechaza la cuadrícula de tarjetas con ícono e interruptor de las apps de casa inteligente.

OWN-WORLD:
- **Colores:** esmalte blanco sobre gris acero de día; grafito sobre casi negro de noche. Tinta grafito o blanco hueso.
  - Rojo de señal solo para alarma.
  - Ámbar solo para el último escalón antes del límite.
  - Verdín para "vigilando".
- **Instrumentos:** escalas lineales calibradas, con marcas finas y escalones.
- **Tipografía:** cifras de odómetro tabulares y rótulos de placa de medidor.
- **Lo que no vigila:** rayado a 45°.

STORY: En un segundo, la familia sabe si la casa está en orden y cuánto falta para cada alarma. Cuando algo suena, ve qué, dónde y desde cuándo, lo silencia con un toque y ve si la central lo confirmó.

FIRST VIEWPORT (celular, 390×844), de arriba abajo:
1. Barra superior con la casa y su luz de conexión.
2. Franja del momento del día (madrugada, noche o día), según las banderas de la central.
3. Si hay alarma: un campo rojo a todo el ancho con la lectura en cifras grandes, desde cuándo y "Silenciar".
4. Cinco tiras-instrumento apiladas, cada una con su escala, su lectura y su interruptor.
5. Barra inferior: Tablero, Historial y Perfil.

SIGNATURE: Las lecturas avanzan cada segundo y, al cruzar un escalón, su marca se enciende. Al llegar al límite, la tira salta al campo rojo. Al confirmarse el silencio, la aguja vuelve a cero como un contador que se reinicia.

FORM: Instrumentos de la casa (medidores domésticos), puesto 7 de 7 de mi lista ordenada, seed key 8eff8e8e.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
