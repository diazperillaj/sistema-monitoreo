/**
 * Espejo de protocolo.h y de backend/app/protocolo.py (§4.4). Los bits y los nombres salen
 * de aquí: ningún otro módulo usa números mágicos.
 */
import type { components } from "../api/tipos.gen";

export type NodoCentral = components["schemas"]["NodoCentral"];
export type EstadoCentral = components["schemas"]["EstadoCentral"];
export type EstadoCasa = components["schemas"]["EstadoCasa"];
export type Alarma = components["schemas"]["Alarma"];
export type Evento = components["schemas"]["Evento"];
export type Comando = components["schemas"]["Comando"];
export type TipoAlarma = Alarma["tipo"];

/** Alarmas (campo "al") */
export const AL = {
  SIN_MOVIMIENTO: 0x01, // nodos 1, 2 y 4
  AGUA: 0x02, // nodo 3
  GAS: 0x04, // nodo 4
  TEMPERATURA: 0x08, // nodo 4
  INTRUSION: 0x10, // nodo 0
} as const;

/** Habilitado (campo "hab") */
export const HAB = {
  PRINCIPAL: 0x01,
  SECUNDARIO: 0x02, // solo nodo 4: presencia
} as const;

/** Banderas (campo "fl") */
export const FL = {
  CONTANDO1: 0x01,
  CONTANDO2: 0x02,
  HORARIO_NOCTURNO: 0x04, // nodo 1 entre 22:00 y 06:00
  MADRUGADA: 0x08, // nodo 0 entre 00:00 y 06:00
  CALENTANDO: 0x10, // sensor PIR o MQ calentando
  ERROR_SENSOR: 0x20, // el DS18B20 no responde
  HORA_VALIDA: 0x40,
} as const;

export const NODO = {
  PUERTA: 0,
  HABITACION: 1,
  BANO: 2,
  COCINA_AGUA: 3,
  COCINA_GAS: 4,
} as const;

export const NODOS = ["Puerta de entrada", "Habitación", "Baño", "Cocina · agua", "Cocina · gas"];

export function tiene(valor: number, bit: number): boolean {
  return (valor & bit) !== 0;
}
