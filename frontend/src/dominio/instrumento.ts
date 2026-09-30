/**
 * Qué muestra cada nodo: el distintivo, sus escalas, sus datos y sus interruptores.
 * Mismas reglas que tarjeta() y detalle() de la app local de la central (§11.4). La diferencia
 * es de forma: cada contador es una escala que se ve también en reposo, el movimiento se dice
 * solo cuando lo hay ("Movimiento ahora", porque la escala ya cuenta el tiempo sin él) y la
 * lectura cruda del sensor de gas no se muestra (la escala dice si hay gas).
 */
import { AL, FL, HAB, NODO, tiene, type NodoCentral } from "./protocolo";
import { textosAlarma } from "./textos";

export type Distintivo = "esperando" | "sin_conexion" | "alarma" | "desactivado" | "vigilando";

export const TEXTO_DISTINTIVO: Record<Distintivo, string> = {
  esperando: "Esperando nodo",
  sin_conexion: "Sin conexión",
  alarma: "ALARMA",
  desactivado: "Desactivado",
  vigilando: "Vigilando",
};

export interface Escala {
  etiqueta: string; // "Sin movimiento", "Agua corriendo"…
  valor: number; // segundos, tal como los reportó la central
  limite: number;
  contando: boolean; // la central está corriendo este contador (FL_CONTANDO1/2)
  enAlarma: boolean; // la alarma de esta escala está sonando: se muestra llena
  enReposo: string; // qué decir cuando no cuenta: "Esperando que alguien entre"
}

export interface Dato {
  etiqueta: string;
  valor: string;
  aviso?: boolean; // un problema del sensor, no una alarma
}

export interface Interruptor {
  sub: 0 | 1;
  etiqueta: string;
  activo: boolean;
}

export interface Instrumento {
  id: number;
  nombre: string;
  distintivo: Distintivo;
  /** El distintivo en palabras; la habitación pausada de noche lo dice así, no "Desactivado". */
  texto: string;
  alarmas: string[];
  /** El sensor de movimiento ve a alguien en este momento (puerta, habitación, baño, cocina). */
  movimiento: boolean;
  escalas: Escala[];
  datos: Dato[];
  interruptores: Interruptor[];
  ayuda: string | null;
  ultimoDatoHaceS: number | null;
}

/** Mismo orden que la app local: primero lo que impide saber, luego la alarma. */
export function distintivo(n: NodoCentral): Distintivo {
  if (!n.visto) return "esperando";
  if (!n.enLinea) return "sin_conexion";
  if (n.al) return "alarma";
  if (!n.hab) return "desactivado";
  return "vigilando";
}

const CALENTANDO: Dato = { etiqueta: "Sensor", valor: "calentando" };

export function instrumento(n: NodoCentral): Instrumento {
  const cual = distintivo(n);
  const pausaNocturna =
    cual === "desactivado" && n.id === NODO.HABITACION && tiene(n.fl, FL.HORARIO_NOCTURNO);
  const base: Instrumento = {
    id: n.id,
    nombre: n.nombre,
    distintivo: cual,
    texto: pausaNocturna ? "En pausa por la noche" : TEXTO_DISTINTIVO[cual],
    alarmas: textosAlarma(n),
    // En el agua, "mov" es la llave abierta, no una persona
    movimiento: n.id !== NODO.COCINA_AGUA && n.mov !== 0,
    escalas: [],
    datos: [],
    interruptores: [],
    ayuda: null,
    ultimoDatoHaceS: n.visto && !n.enLinea ? n.hace : null,
  };
  if (!n.visto) {
    return { ...base, ayuda: "Enciende este nodo para que se conecte a la central." };
  }
  const principal = tiene(n.hab, HAB.PRINCIPAL);
  const contando1 = tiene(n.fl, FL.CONTANDO1);
  const calentando = tiene(n.fl, FL.CALENTANDO);
  switch (n.id) {
    case NODO.PUERTA:
      base.datos.push(
        !tiene(n.fl, FL.HORA_VALIDA)
          ? { etiqueta: "Horario", valor: "Hora no sincronizada", aviso: true }
          : {
              etiqueta: "Horario",
              valor: tiene(n.fl, FL.MADRUGADA) ? "Madrugada: vigilando" : "Fuera de la madrugada",
            },
      );
      if (calentando) base.datos.push(CALENTANDO);
      base.interruptores.push({ sub: 0, etiqueta: "Vigilancia de madrugada", activo: principal });
      break;
    case NODO.HABITACION:
      if (principal) {
        base.escalas.push({
          etiqueta: "Sin movimiento",
          valor: n.c1,
          limite: n.l1,
          contando: contando1,
          enAlarma: tiene(n.al, AL.SIN_MOVIMIENTO),
          enReposo: "Hay movimiento",
        });
      }
      if (tiene(n.fl, FL.HORARIO_NOCTURNO)) {
        base.datos.push({
          etiqueta: "Horario nocturno",
          valor: "Pausa automática; se puede activar",
        });
      }
      if (calentando) base.datos.push(CALENTANDO);
      base.interruptores.push({ sub: 0, etiqueta: "Vigilancia de inactividad", activo: principal });
      break;
    case NODO.BANO:
      base.escalas.push({
        etiqueta: "Sin movimiento",
        valor: n.c1,
        limite: n.l1,
        contando: contando1,
        enAlarma: tiene(n.al, AL.SIN_MOVIMIENTO),
        enReposo: principal ? "Esperando que alguien entre" : "Sin vigilar",
      });
      if (calentando) base.datos.push(CALENTANDO);
      base.interruptores.push({ sub: 0, etiqueta: "Vigilancia del baño", activo: principal });
      break;
    case NODO.COCINA_AGUA:
      base.escalas.push({
        etiqueta: "Agua corriendo",
        valor: n.c1,
        limite: n.l1,
        contando: contando1,
        enAlarma: tiene(n.al, AL.AGUA),
        enReposo: n.mov ? "Llave abierta" : "Llave cerrada",
      });
      base.datos.push({ etiqueta: "Caudal", valor: `${n.v1.toFixed(1)} L/min` });
      base.interruptores.push({ sub: 0, etiqueta: "Vigilancia de agua", activo: principal });
      break;
    case NODO.COCINA_GAS: {
      const presencia = tiene(n.hab, HAB.SECUNDARIO);
      base.escalas.push({
        etiqueta: "Gas detectado",
        valor: n.c1,
        limite: n.l1,
        contando: contando1,
        enAlarma: tiene(n.al, AL.GAS),
        enReposo: "Sin gas",
      });
      if (presencia) {
        base.escalas.push({
          etiqueta: "Sin movimiento",
          valor: n.c2,
          limite: n.l2,
          contando: tiene(n.fl, FL.CONTANDO2),
          enAlarma: tiene(n.al, AL.SIN_MOVIMIENTO),
          enReposo: "Hay movimiento",
        });
      }
      base.datos.push(
        tiene(n.fl, FL.ERROR_SENSOR)
          ? { etiqueta: "Temperatura", valor: "Error de sensor", aviso: true }
          : { etiqueta: "Temperatura", valor: `${n.v1.toFixed(1)} °C` },
      );
      if (calentando) base.datos.push({ etiqueta: "Sensor de gas", valor: "calentando" });
      base.interruptores.push(
        { sub: 0, etiqueta: "Gas y temperatura", activo: principal },
        { sub: 1, etiqueta: "Presencia (inactividad)", activo: presencia },
      );
      break;
    }
  }
  return base;
}

/**
 * La lectura que se muestra entre dos reportes (§11.3): suma la antigüedad del estado y lo
 * que pasó desde que llegó, medido con el reloj del navegador. Solo avanza si el contador
 * corre y la central y el nodo están en línea, y nunca pasa del límite.
 */
export function lecturaEnVivo(
  escala: Escala,
  opciones: { antiguedadS: number; segundosDesdeLlegada: number; enVivo: boolean },
): number {
  if (escala.enAlarma) return escala.limite; // al disparar, la central puede dejar de contar
  if (!escala.contando) return 0;
  if (!opciones.enVivo) return escala.valor;
  const valor = escala.valor + opciones.antiguedadS + opciones.segundosDesdeLlegada;
  return Math.min(escala.limite, Math.max(0, valor));
}
