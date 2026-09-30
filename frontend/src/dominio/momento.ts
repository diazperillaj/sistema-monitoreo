/**
 * El momento del día según la central, no según el celular: la puerta vigila de madrugada y la
 * habitación se pausa de noche, y eso lo deciden las banderas del estado.
 */
import { FL, HAB, NODO, tiene, type EstadoCentral } from "./protocolo";

export type Momento = "sin_hora" | "madrugada" | "noche" | "dia";

export interface Franja {
  momento: Momento;
  texto: string;
}

export function franja(central: EstadoCentral): Franja {
  if (!central.horaValida) {
    return {
      momento: "sin_hora",
      texto: "La central no tiene la hora: los horarios de noche y madrugada no funcionan",
    };
  }
  const puerta = central.nodos[NODO.PUERTA];
  const habitacion = central.nodos[NODO.HABITACION];
  const madrugada = !!puerta && tiene(puerta.fl, FL.MADRUGADA);
  const noche = !!habitacion && tiene(habitacion.fl, FL.HORARIO_NOCTURNO);
  // De noche la habitación se pausa sola, pero un cuidador puede reactivarla
  const habitacionEnPausa = noche && !tiene(habitacion.hab, HAB.PRINCIPAL);
  const deLaHabitacion = habitacionEnPausa
    ? "la habitación está en pausa"
    : "la habitación vigila porque la activaron";
  if (madrugada) {
    return {
      momento: "madrugada",
      texto: noche
        ? `Madrugada: la puerta vigila movimiento y ${deLaHabitacion} hasta las 6:00`
        : "Madrugada: la puerta vigila movimiento hasta las 6:00",
    };
  }
  if (noche) {
    return { momento: "noche", texto: `Noche: ${deLaHabitacion} hasta las 6:00` };
  }
  return { momento: "dia", texto: "Día: cada cuarto vigila con su regla de siempre" };
}
