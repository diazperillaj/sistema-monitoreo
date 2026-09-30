/**
 * Qué tan al día está lo que se ve (§11.4, BannerConexion): la conexión con el servidor, la de
 * la central y la edad del último dato. Primero lo que impide saber, como en los nodos.
 */
import type { Conexion } from "../tiempo-real/useCasaEnVivo";
import { desde } from "./tiempo";

/** Más viejo que esto, el dato "tiene retraso" y los contadores dejan de avanzar (§11.4). */
export const EDAD_MAXIMA_S = 20;

export type Situacion =
  | { tipo: "conectando" }
  | { tipo: "sin_acceso" }
  | { tipo: "sin_servidor" }
  | { tipo: "central_desconectada"; desde: string | null }
  | { tipo: "reconectando" }
  | { tipo: "respaldo" }
  | { tipo: "retraso"; edadS: number }
  | { tipo: "en_vivo" };

export interface Entradas {
  conexion: Conexion;
  hayDatos: boolean;
  /** La última consulta HTTP del estado falló (con el WebSocket caído, no hay otra vía). */
  consultaFallo: boolean;
  centralEnLinea: boolean;
  centralCambioEn: string | null;
  edadS: number;
}

export function situacion(e: Entradas): Situacion {
  if (e.conexion === "sin_acceso") return { tipo: "sin_acceso" };
  if (!e.hayDatos) return e.consultaFallo ? { tipo: "sin_servidor" } : { tipo: "conectando" };
  if (e.conexion !== "en_vivo" && e.consultaFallo) return { tipo: "sin_servidor" };
  if (!e.centralEnLinea) return { tipo: "central_desconectada", desde: e.centralCambioEn };
  if (e.conexion === "reconectando" || e.conexion === "conectando") return { tipo: "reconectando" };
  if (e.edadS > EDAD_MAXIMA_S) return { tipo: "retraso", edadS: e.edadS };
  if (e.conexion === "respaldo") return { tipo: "respaldo" };
  return { tipo: "en_vivo" };
}

/** El texto corto de la barra superior. */
export function textoCorto(s: Situacion): string {
  switch (s.tipo) {
    case "conectando":
      return "Conectando…";
    case "sin_acceso":
      return "Sin acceso";
    case "sin_servidor":
      return "Sin conexión";
    case "central_desconectada":
      return "Central desconectada";
    case "reconectando":
      return "Reconectando…";
    case "respaldo":
      return "Cada 5 s";
    case "retraso":
      return "Con retraso";
    case "en_vivo":
      return "En vivo";
  }
}

/** El aviso a todo el ancho, solo para lo que cambia cómo leer el tablero. */
export function textoAviso(s: Situacion, ahora: Date = new Date()): string | null {
  switch (s.tipo) {
    case "sin_servidor":
      return "Sin conexión con el servidor. Lo que ves puede no estar al día.";
    case "central_desconectada":
      return s.desde
        ? `La central está desconectada ${desde(s.desde, ahora)}. Lo que ves es lo último que mandó.`
        : "La central no está conectada. Lo que ves es lo último que mandó.";
    case "sin_acceso":
      return "Tu cuenta ya no tiene acceso a esta casa.";
    case "retraso":
      // Sin la cuenta de segundos: el aviso es una región viva y no debe leerse cada segundo
      return `Datos con retraso: la central lleva más de ${EDAD_MAXIMA_S} s sin reportar.`;
    default:
      return null;
  }
}
