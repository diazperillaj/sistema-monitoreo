/**
 * "Este celular no recibe alertas" (§11.4): sin Web Push activo aquí ni Telegram vinculado y
 * activo, una alarma con la app cerrada pasaría sin aviso. Lleva al perfil para activarlo.
 */
import { BellOff, ChevronRight } from "lucide-react";
import { Link } from "react-router";
import { useEstadoPush, usePreferencias } from "../api/consultas";

export function AvisoSinCanal() {
  const preferencias = usePreferencias();
  const push = useEstadoPush();
  if (!preferencias.data || !push.data) return null;

  const { webpush, telegram } = preferencias.data;
  const pushListo = push.data === "activo" && webpush.activo;
  const telegramListo = telegram.disponible && telegram.vinculado && telegram.activo;
  if (pushListo || telegramListo) return null;

  const texto =
    push.data === "requiere_instalar"
      ? "Instala la app en este iPhone para recibir alertas"
      : push.data === "bloqueado"
        ? "Las notificaciones están bloqueadas en este navegador"
        : push.data === "activo" && !webpush.activo
          ? "Tus alertas por notificación están en pausa"
          : "Este dispositivo no recibe alertas";

  return (
    <Link
      to="/perfil#notificaciones"
      className="pulsable placa flex min-h-12 items-center gap-3 rounded-[10px] px-4 py-3 text-sm hover:bg-cara-2"
    >
      <BellOff aria-hidden="true" className="size-5 shrink-0 text-tinta-2" />
      <span className="flex-1 font-medium">{texto}</span>
      <span className="flex items-center gap-0.5 font-semibold text-tinta">
        Activar
        <ChevronRight aria-hidden="true" className="size-4" />
      </span>
    </Link>
  );
}
