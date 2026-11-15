/** Textos de la app local de la central (textosAlarma y el formato mm:ss), portados tal cual. */
import { AL, NODO, tiene, type NodoCentral } from "./protocolo";

/** Minutos enteros, como el firmware ("Sin movimiento por 10 min"). */
export function minutos(segundos: number): number {
  return Math.floor(Math.max(0, segundos) / 60);
}

/** Las alarmas activas de un nodo, en el orden de la app local (§4.4). */
export function textosAlarma(nodo: NodoCentral): string[] {
  const textos: string[] = [];
  if (tiene(nodo.al, AL.INTRUSION)) textos.push("Movimiento en la entrada durante la madrugada");
  if (tiene(nodo.al, AL.SIN_MOVIMIENTO)) {
    const limite = nodo.id === NODO.COCINA_GAS ? nodo.l2 : nodo.l1;
    textos.push(`Sin movimiento por ${minutos(limite)} min`);
  }
  if (tiene(nodo.al, AL.AGUA)) textos.push(`Agua corriendo más de ${minutos(nodo.l1)} min`);
  if (tiene(nodo.al, AL.GAS)) textos.push(`Gas detectado por más de ${minutos(nodo.l1)} min`);
  if (tiene(nodo.al, AL.TEMPERATURA)) textos.push(`Temperatura alta: ${nodo.v1.toFixed(1)} °C`);
  return textos;
}

/** "07:12". Los minutos no tienen tope: 125 minutos son "125:00". */
export function mmss(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Cuánto lleva sonando: "03:12" y, desde la hora, "1:05:12". */
export function reloj(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos));
  if (s < 3600) return mmss(s);
  const h = Math.floor(s / 3600);
  return `${h}:${mmss(s % 3600)}`;
}
