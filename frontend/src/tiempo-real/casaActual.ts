/**
 * La casa que se está mirando y su conexión en vivo, compartidas por el tablero, el historial y
 * la barra superior. La conexión vive en el Layout: cambiar de pantalla no corta el sonido.
 */
import { createContext, use } from "react";
import type { Yo } from "../api/consultas";
import { useEstadoCasa } from "../api/consultas";
import { EDAD_MAXIMA_S, situacion, type Situacion } from "../dominio/conexion";
import type { AlertaSonora } from "./useAlertaSonora";
import { useAhora } from "./useAhora";
import type { Conexion } from "./useCasaEnVivo";

export interface CasaActual {
  casaId: number | null;
  conexion: Conexion;
  sonido: AlertaSonora;
}

export const ContextoCasa = createContext<CasaActual | null>(null);

export function useCasaActual(): CasaActual {
  const valor = use(ContextoCasa);
  if (!valor) throw new Error("useCasaActual va dentro del Layout");
  return valor;
}

// ------------------------------------------------------------------ la última casa vista
const CLAVE = "alarma-hogar:casa";

export function recordarCasa(casaId: number): void {
  try {
    localStorage.setItem(CLAVE, String(casaId));
  } catch {
    // sin almacenamiento (modo privado): se elige la primera casa
  }
}

function casaRecordada(): number | null {
  try {
    const valor = Number(localStorage.getItem(CLAVE));
    return Number.isInteger(valor) && valor > 0 ? valor : null;
  } catch {
    return null;
  }
}

export function esMiembro(yo: Yo, casaId: number): boolean {
  return yo.usuario.es_superadmin || yo.casas.some((casa) => casa.id === casaId);
}

/** Fuera de /casa/:id (perfil, inicio): la última casa vista si sigue siendo suya, o la primera. */
export function casaPorDefecto(yo: Yo): number | null {
  const recordada = casaRecordada();
  if (recordada !== null && esMiembro(yo, recordada)) return recordada;
  return yo.casas[0]?.id ?? null;
}

// ------------------------------------------------------------------ el estado y su edad
export interface EstadoEnVivo {
  consulta: ReturnType<typeof useEstadoCasa>;
  /** Segundos desde que llegó el último estado, con el reloj del celular. */
  desdeLlegadaS: number;
  /** Edad del dato para los contadores: deja de crecer al pasar EDAD_MAXIMA_S (§11.3). */
  edadS: number;
  situacion: Situacion;
  /** La central está en línea y sus datos llegan. */
  vivo: boolean;
}

export function useEstadoEnVivo(casaId: number | null, conexion: Conexion): EstadoEnVivo {
  const consulta = useEstadoCasa(casaId, conexion === "respaldo");
  const ahora = useAhora();
  const estado = consulta.data;
  const desdeLlegadaS = consulta.dataUpdatedAt
    ? Math.max(0, (ahora - consulta.dataUpdatedAt) / 1000)
    : 0;
  const edadReal = (estado?.antiguedad_s ?? 0) + desdeLlegadaS;
  const actual = situacion({
    conexion,
    hayDatos: estado !== undefined,
    consultaFallo: consulta.isError,
    centralEnLinea: estado?.online ?? false,
    centralCambioEn: estado?.online_cambio_en ?? null,
    edadS: edadReal,
  });
  const vivo =
    estado !== undefined &&
    estado.online &&
    estado.central !== null &&
    actual.tipo !== "sin_servidor" &&
    actual.tipo !== "sin_acceso";
  return {
    consulta,
    desdeLlegadaS,
    edadS: Math.min(edadReal, EDAD_MAXIMA_S),
    situacion: actual,
    vivo,
  };
}
