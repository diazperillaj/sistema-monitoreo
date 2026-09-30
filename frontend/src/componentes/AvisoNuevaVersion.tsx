/**
 * "Nueva versión disponible → Actualizar" (§11.5). Una PWA instalada puede quedar abierta días,
 * así que además se busca una versión nueva cada 30 minutos.
 */
import { useEffect } from "react";
import { toast } from "sonner";
import { useRegisterSW } from "virtual:pwa-register/react";

const CADA_MS = 30 * 60 * 1000;

export function AvisoNuevaVersion() {
  const {
    needRefresh: [hayNueva],
    updateServiceWorker,
  } = useRegisterSW({
    immediate: true,
    onRegisteredSW(_url, registro) {
      if (!registro) return;
      setInterval(() => {
        if (navigator.onLine) void registro.update();
      }, CADA_MS);
    },
  });

  useEffect(() => {
    if (!hayNueva) return;
    toast("Nueva versión disponible", {
      id: "nueva-version",
      description: "Actualiza para tener la última versión de la app.",
      duration: Infinity,
      action: { label: "Actualizar", onClick: () => void updateServiceWorker(true) },
    });
  }, [hayNueva, updateServiceWorker]);

  return null;
}
