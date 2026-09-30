# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Familiares y cuidadores contratados** de la persona que vive en una casa monitoreada. El caso de uso de la especificación es la casa de una persona mayor ("Casa de la abuela"): la familia la cuida a distancia y los cuidadores la atienden por trabajo.
- Usan la app en su propio celular, casi siempre fuera de la casa. Entran por dos caminos: una notificación de alarma, o una revisión rápida para confirmar que todo está bien.
- Todos se manejan bien con el celular: no hay una necesidad especial de lectura o motricidad confirmada.
- Roles por casa: **admin** (gestiona miembros, invitaciones y ajustes) y **cuidador** (ve, silencia, activa y desactiva). Un **superadmin** (Juan Pablo) opera el servidor y ve todas las casas. Una persona puede pertenecer a varias casas.

## Product Purpose

Ver y atender a distancia el sistema de sensores ESP32 de una casa: cinco nodos (puerta de entrada de madrugada, habitación sin movimiento, baño sin movimiento, agua corriendo en la cocina, gas y temperatura en la cocina). La app muestra el estado en vivo, avisa las alarmas, permite silenciar, activar y desactivar cada nodo, y guarda el historial.

Éxito significa:

- **en una alarma:** saber en segundos qué pasó, dónde y desde cuándo, y actuar;
- **en la revisión diaria:** confirmar de un vistazo que todo está bien;
- nadie se pierde una alarma: notificaciones y recordatorios hasta que alguien la atiende.

Los dos momentos, la emergencia y la revisión tranquila, pesan lo mismo.

## Positioning

Es la propia central de la casa llevada al celular de cada familiar y cuidador. Usa los mismos nodos, reglas y textos que la central ESP32 y su app local (`alarma.local`), en un servidor propio y sin costo mensual. Cada acción remota se da por hecha solo cuando la central la confirma en su siguiente reporte.

## Operating Context

- **Dispositivos:** celulares Android e iPhone, con la app instalada como PWA. Notificaciones Web Push y, opcionalmente, Telegram por persona (fase F4b, pendiente).
- **Tiempo real:** la central reporta cada ~5 s por WebSocket; los contadores avanzan cada segundo entre reportes. Con la app abierta, las alarmas pitan y vibran.
- **La realidad es imperfecta:**
  - la central puede quedar desconectada, los nodos perder la conexión y la central reiniciarse;
  - los datos pueden llegar con retraso;
  - un comando puede quedar sin confirmar a los 8 s.

  Todo eso forma parte del uso normal.
- **Comandos:** silenciar, activar y desactivar; silenciar todo; presencia del nodo 4. Siguen el ciclo enviando → confirmado o sin confirmar.
- **Reglas de cada tarjeta:** vienen de la app local de la central. Contadores con su límite, horario nocturno de la habitación (22:00–06:00), sensor calentando y error de sensor.
- **Idioma y hora:** español (es-CO); horas de Colombia (America/Bogota).

## Capabilities and Constraints

- **Vistas** (§11.2 de `docs/ARQUITECTURA.md`): Login, Invitación, Casas, Tablero, Historial, Gráficas, Miembros, Ajustes, Perfil y No encontrado.
- **Stack ya decidido:** React 19, TypeScript ~5.9 (fijo), Vite 8, Tailwind 4, shadcn/ui (Radix), lucide-react, sonner, TanStack Query, React Router, Recharts (carga diferida), vite-plugin-pwa y tipos generados del OpenAPI.
- **Restricciones:**
  - JS inicial del tablero ≤ 150 KB gzip;
  - modo oscuro automático (`prefers-color-scheme`);
  - CSP sin scripts en línea;
  - sin `dangerouslySetInnerHTML`;
  - nada sensible en `localStorage`; la sesión va solo en una cookie HttpOnly.
- **iPhone:** el push exige instalar la PWA (iOS ≥ 16.4), así que hace falta una guía de instalación. Web Push no suena con el celular en silencio.
- **Términos:** casa, central, nodo (Puerta de entrada, Habitación, Baño, Cocina · agua, Cocina · gas), alarma, evento, comando, silenciar, activar, desactivar, presencia, horario nocturno. Distintivos de nodo: "Vigilando", "ALARMA", "Desactivado", "Sin conexión", "Esperando nodo".
- **Pendiente:** Telegram (F4b) no está implementado; su sección del perfil queda oculta mientras `disponible = false`.

## Brand Commitments

- **Nombres en uso:** "Monitoreo del hogar" (nombre de la app) y "Alarma hogar" (nombre corto de la PWA). Dominio: `sistemamonitoreo.duckdns.org`.
- **Voz:** español claro y directo, sin jerga técnica. Los textos de las alarmas son los de §4.4 de la especificación ("Sin movimiento por 10 min", "Agua corriendo más de 8 min").
- Todavía no hay logotipo ni identidad visual: los íconos de F4 son provisionales.

## Evidence on Hand

- **Datos reales del protocolo:**
  - estados de ejemplo en `backend/tests/fixtures/estado_*.json`;
  - textos y nombres en `backend/app/protocolo.py`;
  - el simulador de la central en `tools/simulador_central.py`, que genera datos en vivo.
- **Contrato de la API:** `frontend/openapi.json` y `frontend/src/api/tipos.gen.ts`.
- **No hay** testimonios, clientes ni cifras de uso: no se inventan.

## Product Principles

1. **Un vistazo basta:** "¿está todo bien?" se responde en un segundo, sin leer párrafos.
2. **La alarma manda:** cuando algo pasa, qué, dónde y desde cuándo aparecen primero, y silenciar queda a un toque, nunca detrás de un menú.
3. **Verdad antes que optimismo:** la app muestra lo que la central confirmó. Desconexiones, retrasos y comandos sin confirmar se ven; nunca se disimulan.
4. **Igual que la casa:** los mismos nodos, reglas y textos que la central y su app local.
5. **Calma en lo cotidiano:** cuando todo está bien, la app transmite tranquilidad, sin alarmismo.

## Accessibility & Inclusion

- WCAG AA: contraste suficiente y objetivos táctiles de al menos 44 px.
- Interruptores y diálogos accesibles con teclado y lector de pantalla (Radix).
- Las alarmas se anuncian con `aria-live="assertive"`.
- No se confirmó una necesidad especial de lectura: se usa el estándar, sin letra agrandada obligatoria.
