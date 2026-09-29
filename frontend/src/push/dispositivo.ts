/**
 * Web Push en este dispositivo (§10.3, §10.5): activar, desactivar y probar.
 * F5 lo integra en la sección Notificaciones del perfil.
 */
import { claveBinaria } from "./clave";

export type EstadoPush = "no_soportado" | "bloqueado" | "inactivo" | "activo";

export class ErrorPush extends Error {}

export function soportado(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** El mensaje de un error de la API: {"detail": {"codigo", "mensaje"}} (§8). */
async function mensajeDe(respuesta: Response): Promise<string> {
  const cuerpo = (await respuesta.json().catch(() => null)) as {
    detail?: { mensaje?: string };
  } | null;
  return cuerpo?.detail?.mensaje ?? `El servidor respondió ${respuesta.status}.`;
}

/** El service worker activo. Con `npm run dev` no hay: se prueba con el build (puerto 8011). */
async function registro(): Promise<ServiceWorkerRegistration> {
  const listo = navigator.serviceWorker.ready;
  const espera = new Promise<never>((_, rechazar) =>
    setTimeout(() => rechazar(new ErrorPush("El service worker no está activo.")), 10_000),
  );
  return Promise.race([listo, espera]);
}

export async function estado(): Promise<EstadoPush> {
  if (!soportado()) return "no_soportado";
  if (Notification.permission === "denied") return "bloqueado";
  const actual = await navigator.serviceWorker.getRegistration();
  const suscripcion = await actual?.pushManager.getSubscription();
  return suscripcion ? "activo" : "inactivo";
}

/** Debe llamarse desde un toque del usuario: iPhone lo exige para pedir permiso (§10.5). */
export async function activar(): Promise<void> {
  if ((await Notification.requestPermission()) !== "granted") {
    throw new ErrorPush("No diste permiso para mostrar notificaciones.");
  }
  const respuesta = await fetch("/api/v1/push/clave-publica");
  if (!respuesta.ok) throw new ErrorPush(await mensajeDe(respuesta));
  const { clave } = (await respuesta.json()) as { clave: string };
  const sw = await registro();
  // Una suscripción hecha con otra clave (si se cambiaron las VAPID) no se puede reutilizar
  await (await sw.pushManager.getSubscription())?.unsubscribe();
  const suscripcion = await sw.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: claveBinaria(clave),
  });
  const alta = await fetch("/api/v1/push/suscripciones", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(suscripcion.toJSON()),
  });
  if (!alta.ok) {
    await suscripcion.unsubscribe();
    throw new ErrorPush(await mensajeDe(alta));
  }
}

export async function desactivar(): Promise<void> {
  const actual = await navigator.serviceWorker.getRegistration();
  const suscripcion = await actual?.pushManager.getSubscription();
  if (!suscripcion) return;
  await fetch("/api/v1/push/suscripciones", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: suscripcion.endpoint }),
  });
  await suscripcion.unsubscribe();
}

/** Pide la notificación de prueba y devuelve a cuántos dispositivos salió. */
export async function probar(): Promise<number> {
  const respuesta = await fetch("/api/v1/notificaciones/prueba", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ canal: "webpush" }),
  });
  if (!respuesta.ok) throw new ErrorPush(await mensajeDe(respuesta));
  return ((await respuesta.json()) as { webpush: number }).webpush;
}
