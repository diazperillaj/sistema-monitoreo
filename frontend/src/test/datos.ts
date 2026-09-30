/** Datos de prueba con la forma exacta del contrato (§4.3, §8.3). */
import type { components } from "../api/tipos.gen";
import { AL, FL, HAB, NODOS } from "../dominio/protocolo";

type Esquemas = components["schemas"];
export type Nodo = Esquemas["NodoCentral"];

const LIMITES = [
  [0, 0],
  [1800, 0],
  [600, 0],
  [480, 0],
  [240, 1200],
];

/** Un nodo en línea, vigilando y sin alarmas; `cambios` pisa lo que haga falta. */
export function nodo(id: number, cambios: Partial<Nodo> = {}): Nodo {
  return {
    id,
    nombre: NODOS[id],
    visto: true,
    enLinea: true,
    hab: HAB.PRINCIPAL,
    al: 0,
    mov: 0,
    fl: FL.HORA_VALIDA,
    c1: 0,
    l1: LIMITES[id][0],
    c2: 0,
    l2: LIMITES[id][1],
    v1: id === 4 ? 24.6 : 0,
    v2: id === 4 ? 640 : 0,
    hace: 1,
    ...cambios,
  };
}

export function central(nodos: Nodo[] = [0, 1, 2, 3, 4].map((id) => nodo(id))) {
  return {
    hora: "29/09/2026 14:05:10",
    horaValida: true,
    red: "wifi" as const,
    nodos,
    eventos: [],
  };
}

export function estadoCasa(cambios: Partial<Esquemas["EstadoCasa"]> = {}): Esquemas["EstadoCasa"] {
  return {
    casa_id: 1,
    online: true,
    online_cambio_en: "2026-09-29T12:00:00Z",
    recibido_en: "2026-09-29T19:05:10Z",
    antiguedad_s: 0,
    central: central(),
    alarmas_abiertas: [],
    ...cambios,
  };
}

export function comando(cambios: Partial<Esquemas["Comando"]> = {}): Esquemas["Comando"] {
  return {
    id: 41,
    nodo_id: 2,
    accion: "desactivar",
    sub: 0,
    estado: "pendiente",
    creado_en: "2026-09-29T19:05:12Z",
    resuelto_en: null,
    usuario: { id: 1, nombre: "Ana Lucía" },
    ...cambios,
  };
}

export { AL, FL, HAB };
