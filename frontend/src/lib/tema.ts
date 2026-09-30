/**
 * Modo claro u oscuro. "Automático" (lo de siempre) sigue el modo del dispositivo; "Claro" y
 * "Oscuro" lo fijan en este dispositivo. public/tema.js lo aplica antes de pintar; este módulo
 * guarda la elección, sigue los cambios del sistema y pinta la barra del celular (theme-color).
 */
import { useSyncExternalStore } from "react";

export type PreferenciaTema = "sistema" | "claro" | "oscuro";
export type Tema = "claro" | "oscuro";

const CLAVE = "alarma-hogar:tema"; // la misma que lee public/tema.js
const COLOR_BARRA: Record<Tema, string> = { claro: "#f9fbfa", oscuro: "#151a1c" };

const sistema =
  typeof window !== "undefined" ? window.matchMedia?.("(prefers-color-scheme: dark)") : undefined;

function leer(): PreferenciaTema {
  try {
    const valor = localStorage.getItem(CLAVE);
    return valor === "claro" || valor === "oscuro" ? valor : "sistema";
  } catch {
    return "sistema"; // sin almacenamiento (modo privado): como el dispositivo
  }
}

let preferencia: PreferenciaTema = typeof window !== "undefined" ? leer() : "sistema";
const oyentes = new Set<() => void>();

export function temaEfectivo(p: PreferenciaTema = preferencia): Tema {
  if (p !== "sistema") return p;
  return sistema?.matches ? "oscuro" : "claro";
}

function aplicar(sinTransiciones: boolean): void {
  const raiz = document.documentElement;
  const tema = temaEfectivo();
  if (sinTransiciones) raiz.classList.add("cambiando-tema");
  raiz.dataset.tema = tema;
  document
    .querySelectorAll('meta[name="theme-color"]')
    .forEach((barra) => barra.setAttribute("content", COLOR_BARRA[tema]));
  if (sinTransiciones) {
    // Leer un estilo obliga al navegador a calcular ya los colores nuevos, con las transiciones
    // apagadas; después vuelven. No depende de los cuadros de animación (una pestaña oculta no
    // los da, y la clase se quedaría puesta).
    void window.getComputedStyle(document.body).color;
    window.setTimeout(() => raiz.classList.remove("cambiando-tema"), 1);
  }
  oyentes.forEach((oyente) => oyente());
}

export function fijarTema(nueva: PreferenciaTema): void {
  preferencia = nueva;
  try {
    if (nueva === "sistema") localStorage.removeItem(CLAVE);
    else localStorage.setItem(CLAVE, nueva);
  } catch {
    // sin almacenamiento: vale para esta visita
  }
  aplicar(true);
}

if (typeof window !== "undefined") {
  aplicar(false); // por si public/tema.js no corrió (pruebas, desarrollo)
  sistema?.addEventListener("change", () => {
    if (preferencia === "sistema") aplicar(true);
  });
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => oyentes.delete(oyente);
}

/** La elección de este dispositivo y el tema que se ve ahora. */
export function useTema(): { preferencia: PreferenciaTema; tema: Tema } {
  const instantanea = useSyncExternalStore(
    suscribir,
    () => `${preferencia}|${temaEfectivo()}`,
    () => "sistema|claro",
  );
  const [p, t] = instantanea.split("|") as [PreferenciaTema, Tema];
  return { preferencia: p, tema: t };
}
