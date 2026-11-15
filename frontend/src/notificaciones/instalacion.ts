/**
 * "Instalar app" (§11.6). Android avisa con `beforeinstallprompt` una sola vez y temprano, así
 * que se escucha desde que carga la app (main.tsx importa este módulo) y se guarda el evento.
 */
import { useSyncExternalStore } from "react";

interface EventoInstalacion extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let pendiente: EventoInstalacion | null = null;
const oyentes = new Set<() => void>();
const avisar = () => oyentes.forEach((oyente) => oyente());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (evento) => {
    evento.preventDefault(); // sin el mini aviso del navegador: se ofrece en el perfil
    pendiente = evento as EventoInstalacion;
    avisar();
  });
  window.addEventListener("appinstalled", () => {
    pendiente = null;
    avisar();
  });
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => oyentes.delete(oyente);
}

export function useInstalacion(): { disponible: boolean; instalar: () => Promise<boolean> } {
  const evento = useSyncExternalStore(
    suscribir,
    () => pendiente,
    () => null,
  );
  return {
    disponible: evento !== null,
    instalar: async () => {
      if (!evento) return false;
      await evento.prompt();
      const { outcome } = await evento.userChoice;
      pendiente = null; // el navegador no deja usar el mismo evento dos veces
      avisar();
      return outcome === "accepted";
    },
  };
}
