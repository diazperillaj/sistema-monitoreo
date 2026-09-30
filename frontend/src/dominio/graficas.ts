/**
 * Lo que las gráficas calculan antes de dibujar: huecos donde faltan lecturas, marcas del eje de
 * tiempo en horas redondas de Bogotá y el resumen de cada serie.
 */
const BOGOTA_MS = -5 * 3600_000; // UTC-5, sin horario de verano

const DIA_CORTO = new Intl.DateTimeFormat("es-CO", {
  timeZone: "America/Bogota",
  weekday: "short",
  day: "numeric",
});

export interface Muestra {
  t: number; // ms
  valor: number | null; // null: un hueco, la línea se corta
}

/**
 * Si entre dos lecturas pasa más de 1,5 intervalos, la línea se corta: un nodo apagado o una
 * central caída no se dibujan como una recta inventada entre el antes y el después.
 */
export function conHuecos(puntos: { t: string; valor: number }[], intervaloMs: number): Muestra[] {
  const muestras: Muestra[] = [];
  let anterior: number | null = null;
  for (const punto of puntos) {
    const t = Date.parse(punto.t);
    if (anterior !== null && t - anterior > 1.5 * intervaloMs) {
      muestras.push({ t: anterior + intervaloMs, valor: null });
    }
    muestras.push({ t, valor: punto.valor });
    anterior = t;
  }
  return muestras;
}

/** Marcas del eje cada `pasoHoras` horas en punto de Bogotá (6 → 00, 06, 12, 18; 24 → medianoche). */
export function marcasDeTiempo(desde: number, hasta: number, pasoHoras: number): number[] {
  const paso = pasoHoras * 3600_000;
  const primera = Math.ceil((desde + BOGOTA_MS) / paso) * paso - BOGOTA_MS;
  const marcas: number[] = [];
  for (let t = primera; t <= hasta; t += paso) marcas.push(t);
  return marcas;
}

/** "mar 29" */
export function diaCorto(momento: number | string | Date): string {
  return DIA_CORTO.format(new Date(momento));
}

/** { semana: "mar", numero: "29" }: para escribir el día en dos líneas en un eje angosto. */
export function diaEnPartes(momento: number | string | Date): { semana: string; numero: string } {
  const partes = DIA_CORTO.formatToParts(new Date(momento));
  return {
    semana: partes.find((p) => p.type === "weekday")?.value ?? "",
    numero: partes.find((p) => p.type === "day")?.value ?? "",
  };
}

export interface ResumenSerie {
  ultimo: { t: number; valor: number } | null;
  maximo: number | null;
  minimo: number | null;
}

export function resumenSerie(muestras: Muestra[]): ResumenSerie {
  let ultimo: ResumenSerie["ultimo"] = null;
  let maximo: number | null = null;
  let minimo: number | null = null;
  for (const { t, valor } of muestras) {
    if (valor === null) continue;
    ultimo = { t, valor };
    maximo = maximo === null ? valor : Math.max(maximo, valor);
    minimo = minimo === null ? valor : Math.min(minimo, valor);
  }
  return { ultimo, maximo, minimo };
}
