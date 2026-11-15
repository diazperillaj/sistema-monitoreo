/** Horas y duraciones en español de Colombia, siempre con la hora de Bogotá (§11.6). */
const ZONA = "America/Bogota";

const horaCorta = new Intl.DateTimeFormat("es-CO", {
  timeZone: ZONA,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const fechaCorta = new Intl.DateTimeFormat("es-CO", {
  timeZone: ZONA,
  day: "numeric",
  month: "short",
});

const diaClave = new Intl.DateTimeFormat("en-CA", {
  timeZone: ZONA,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** "14:35" */
export function hora(momento: string | Date): string {
  return horaCorta.format(new Date(momento));
}

/** "29 sept." */
export function fecha(momento: string | Date): string {
  return fechaCorta.format(new Date(momento));
}

/** "14:35" si fue hoy, "ayer 14:35" o "27 sept. 14:35" si no. */
export function cuando(momento: string | Date, ahora: Date = new Date()): string {
  const dia = diaClave.format(new Date(momento));
  const hoy = diaClave.format(ahora);
  const ayer = diaClave.format(new Date(ahora.getTime() - 86_400_000));
  if (dia === hoy) return hora(momento);
  if (dia === ayer) return `ayer ${hora(momento)}`;
  return `${fecha(momento)} ${hora(momento)}`;
}

const diaLargo = new Intl.DateTimeFormat("es-CO", {
  timeZone: ZONA,
  weekday: "long",
  day: "numeric",
  month: "long",
});

/** Para agrupar el historial: "Hoy", "Ayer" o "sábado, 27 de septiembre". */
export function dia(momento: string | Date, ahora: Date = new Date()): string {
  const clave = diaClave.format(new Date(momento));
  if (clave === diaClave.format(ahora)) return "Hoy";
  if (clave === diaClave.format(new Date(ahora.getTime() - 86_400_000))) return "Ayer";
  const texto = diaLargo.format(new Date(momento));
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** "desde las 14:35", "desde ayer a las 14:35" o "desde el 27 sept. a las 14:35". */
export function desde(momento: string | Date, ahora: Date = new Date()): string {
  const dia = diaClave.format(new Date(momento));
  if (dia === diaClave.format(ahora)) return `desde las ${hora(momento)}`;
  if (dia === diaClave.format(new Date(ahora.getTime() - 86_400_000))) {
    return `desde ayer a las ${hora(momento)}`;
  }
  return `desde el ${fecha(momento)} a las ${hora(momento)}`;
}

/** "45 s", "3 min", "1 h 5 min", "2 d 3 h" */
export function duracion(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 48) return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
  const d = Math.floor(h / 24);
  return h % 24 ? `${d} d ${h % 24} h` : `${d} d`;
}

/** "hace 12 s", "hace 3 min" */
export function hace(segundos: number): string {
  return segundos < 5 ? "ahora" : `hace ${duracion(segundos)}`;
}
