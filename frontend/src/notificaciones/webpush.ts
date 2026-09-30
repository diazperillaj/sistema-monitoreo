/**
 * Web Push en este dispositivo (§10.3, §10.5): saber si está activo, activarlo (desde un toque),
 * desactivarlo y pedir la notificación de prueba.
 */
import { api, ErrorApi, llamar } from "../api/cliente";
import { claveBinaria } from "./clave";

export type EstadoPush =
  | "no_soportado"
  | "requiere_instalar" // iPhone o iPad: Web Push solo funciona con la app instalada (§10.5)
  | "bloqueado"
  | "inactivo"
  | "activo";

/** Un error de este dispositivo (permiso, service worker), con un mensaje para mostrar. */
export class ErrorPush extends Error {}

export function esIOS(): boolean {
  const ua = navigator.userAgent;
  // El iPad se presenta como Mac, pero tiene pantalla táctil
  return /iPhone|iPad|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
}

export function instalada(): boolean {
  return (
    window.matchMedia?.("(display-mode: standalone)").matches === true ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export function soportado(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

async function suscripcionActual(): Promise<PushSubscription | null> {
  const registro = await navigator.serviceWorker.getRegistration();
  return (await registro?.pushManager.getSubscription()) ?? null;
}

export async function estadoPush(): Promise<EstadoPush> {
  if (!soportado()) return esIOS() && !instalada() ? "requiere_instalar" : "no_soportado";
  if (Notification.permission === "denied") return "bloqueado";
  return (await suscripcionActual()) ? "activo" : "inactivo";
}

/** El service worker activo. Con `npm run dev` no hay: se prueba con el build (puerto 8011). */
async function registro(): Promise<ServiceWorkerRegistration> {
  const espera = new Promise<never>((_, rechazar) =>
    setTimeout(
      () => rechazar(new ErrorPush("La app no terminó de instalarse. Recarga la página.")),
      10_000,
    ),
  );
  return Promise.race([navigator.serviceWorker.ready, espera]);
}

/** Debe llamarse desde un toque: iPhone lo exige para pedir permiso (§10.5). */
export async function activarPush(): Promise<void> {
  if ((await Notification.requestPermission()) !== "granted") {
    throw new ErrorPush(
      "No diste permiso para mostrar notificaciones. Puedes darlo en los ajustes del navegador.",
    );
  }
  const { clave } = await llamar(() => api.GET("/api/v1/push/clave-publica"));
  const sw = await registro();
  // Una suscripción hecha con otra clave (si se cambiaron las VAPID) no se puede reutilizar
  await (await sw.pushManager.getSubscription())?.unsubscribe();
  const suscripcion = await sw.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: claveBinaria(clave),
  });
  const { keys } = suscripcion.toJSON();
  try {
    await llamar(() =>
      api.POST("/api/v1/push/suscripciones", {
        body: {
          endpoint: suscripcion.endpoint,
          keys: { p256dh: keys?.p256dh ?? "", auth: keys?.auth ?? "" },
        },
      }),
    );
  } catch (error) {
    await suscripcion.unsubscribe();
    throw error;
  }
}

export async function desactivarPush(): Promise<void> {
  const suscripcion = await suscripcionActual();
  if (!suscripcion) return;
  await llamar(() =>
    api.DELETE("/api/v1/push/suscripciones", { body: { endpoint: suscripcion.endpoint } }),
  ).catch(() => undefined); // si el servidor no responde, igual se quita de este dispositivo
  await suscripcion.unsubscribe();
}

/** Pide la notificación de prueba y devuelve a cuántos dispositivos salió. */
export async function probarPush(): Promise<number> {
  const resultado = await llamar(() =>
    api.POST("/api/v1/notificaciones/prueba", { body: { canal: "webpush" } }),
  );
  return resultado.webpush;
}

export function mensajeDePush(error: unknown): string {
  if (error instanceof ErrorApi || error instanceof ErrorPush) return error.message;
  return "Este navegador no pudo activar las notificaciones. Vuelve a intentarlo.";
}
