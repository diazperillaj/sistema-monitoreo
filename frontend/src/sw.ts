/// <reference lib="webworker" />
/**
 * Service worker (§10.3, §11.5), servido como /sw.js. En F4: notificaciones push; en F5 se
 * completa con el aviso de nueva versión.
 */
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { claveBinaria } from "./push/clave";

declare let self: ServiceWorkerGlobalScope;

// Solo el "cascarón" de la app. /api y /ws nunca se cachean: las alarmas siempre en vivo.
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), {
    denylist: [/^\/api\//, /^\/ws\//],
  }),
);

// La versión nueva espera a que la página lo pida (§11.5)
self.addEventListener("message", (evento) => {
  if ((evento.data as { type?: string } | null)?.type === "SKIP_WAITING") void self.skipWaiting();
});

/** El payload de §10.2 */
interface Aviso {
  titulo: string;
  cuerpo: string;
  tag: string;
  url: string;
  tipo: "alarma" | "recordatorio" | "resuelta" | "conexion" | "central" | "prueba";
  casa_id: number | null;
  alarma_id?: number | null;
  nodo_id?: number | null;
}

/** Los tipos de TypeScript no traen renotify, vibrate ni actions, que Chrome sí usa. */
type OpcionesNotificacion = NotificationOptions & {
  renotify?: boolean;
  vibrate?: number[];
  actions?: { action: string; title: string }[];
};

/** Las alarmas de sensor se pueden silenciar desde la notificación (solo Android). */
function silenciable(aviso: Aviso): boolean {
  return (
    (aviso.tipo === "alarma" || aviso.tipo === "recordatorio") &&
    aviso.tag.startsWith("a-") &&
    aviso.casa_id !== null &&
    aviso.nodo_id != null
  );
}

self.addEventListener("push", (evento) => {
  const aviso = evento.data?.json() as Aviso | undefined;
  if (!aviso) return;
  const opciones: OpcionesNotificacion = {
    body: aviso.cuerpo,
    tag: aviso.tag,
    renotify: true,
    requireInteraction: aviso.tipo === "alarma",
    icon: "/icons/icon-192.png",
    badge: "/icons/badge-96.png",
    vibrate: [400, 200, 400, 200, 400],
    data: aviso,
    actions: silenciable(aviso) ? [{ action: "silenciar", title: "Silenciar" }] : [],
  };
  evento.waitUntil(self.registration.showNotification(aviso.titulo, opciones));
});

async function abrir(url: string): Promise<void> {
  const ventanas = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  const abierta = ventanas[0];
  if (abierta) {
    await abierta.focus();
    await abierta.navigate(url).catch(() => undefined);
    return;
  }
  await self.clients.openWindow(url);
}

async function silenciar(aviso: Aviso): Promise<void> {
  // El navegador pone el Origin del sitio y la cookie de sesión (§12.3)
  const respuesta = await fetch(`/api/v1/casas/${aviso.casa_id}/comandos`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nodo: aviso.nodo_id, accion: "silenciar" }),
  }).catch(() => null);
  if (!respuesta?.ok) await abrir(aviso.url); // sin sesión o sin conexión: mejor abrir la app
}

self.addEventListener("notificationclick", (evento) => {
  const aviso = evento.notification.data as Aviso;
  evento.notification.close();
  evento.waitUntil(evento.action === "silenciar" ? silenciar(aviso) : abrir(aviso.url));
});

// El navegador renovó la suscripción: se registra la nueva (§10.3)
self.addEventListener("pushsubscriptionchange", (evento: Event) => {
  (evento as ExtendableEvent).waitUntil(
    (async () => {
      const { clave } = (await (await fetch("/api/v1/push/clave-publica")).json()) as {
        clave: string;
      };
      const nueva = await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: claveBinaria(clave),
      });
      await fetch("/api/v1/push/suscripciones", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nueva.toJSON()),
      });
    })(),
  );
});
