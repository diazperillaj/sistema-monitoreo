/**
 * Un solo reloj de 1 s para toda la app: los contadores avanzan entre reportes (§11.3) y los
 * "hace 12 s" se mantienen al día sin un intervalo por componente.
 */
import { useSyncExternalStore } from "react";

let ahora = Date.now();
let intervalo: ReturnType<typeof setInterval> | undefined;
const oyentes = new Set<() => void>();

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  if (oyentes.size === 1) {
    ahora = Date.now();
    intervalo = setInterval(() => {
      ahora = Date.now();
      oyentes.forEach((o) => o());
    }, 1000);
  }
  return () => {
    oyentes.delete(oyente);
    if (oyentes.size === 0) clearInterval(intervalo);
  };
}

export function useAhora(): number {
  return useSyncExternalStore(
    suscribir,
    () => ahora,
    () => ahora,
  );
}
