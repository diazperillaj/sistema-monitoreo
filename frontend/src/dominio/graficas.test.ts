import { describe, expect, it } from "vitest";
import { conHuecos, diaCorto, diaEnPartes, marcasDeTiempo, resumenSerie } from "./graficas";

const CINCO_MIN = 5 * 60_000;

describe("conHuecos", () => {
  it("lecturas seguidas: la línea no se corta", () => {
    const muestras = conHuecos(
      [
        { t: "2026-09-29T12:00:00Z", valor: 24 },
        { t: "2026-09-29T12:05:00Z", valor: 25 },
      ],
      CINCO_MIN,
    );
    expect(muestras.map((m) => m.valor)).toEqual([24, 25]);
  });

  it("si faltan lecturas (nodo apagado), mete un hueco en vez de inventar una recta", () => {
    const muestras = conHuecos(
      [
        { t: "2026-09-29T12:00:00Z", valor: 24 },
        { t: "2026-09-29T13:00:00Z", valor: 26 },
      ],
      CINCO_MIN,
    );
    expect(muestras.map((m) => m.valor)).toEqual([24, null, 26]);
    expect(muestras[1].t).toBe(Date.parse("2026-09-29T12:05:00Z"));
  });
});

describe("marcasDeTiempo", () => {
  it("cada 6 horas en punto de Bogotá", () => {
    // 29/09 09:10 a 30/09 09:10 en Bogotá (14:10 a 14:10 UTC)
    const marcas = marcasDeTiempo(
      Date.parse("2026-09-29T14:10:00Z"),
      Date.parse("2026-09-30T14:10:00Z"),
      6,
    );
    // 12:00, 18:00, 00:00 y 06:00 de Bogotá = 17, 23, 05 y 11 UTC
    expect(marcas.map((t) => new Date(t).toISOString().slice(11, 16))).toEqual([
      "17:00",
      "23:00",
      "05:00",
      "11:00",
    ]);
  });

  it("cada día a medianoche de Bogotá", () => {
    const marcas = marcasDeTiempo(
      Date.parse("2026-09-23T14:00:00Z"),
      Date.parse("2026-09-30T14:00:00Z"),
      24,
    );
    expect(marcas).toHaveLength(7);
    expect(new Date(marcas[0]).toISOString()).toBe("2026-09-24T05:00:00.000Z");
    expect(diaCorto(marcas[0])).toBe("jue 24");
    // En dos líneas para el eje de 7 días; el día es el de Bogotá, no el de UTC
    expect(diaEnPartes(Date.parse("2026-09-30T03:00:00Z"))).toEqual({
      semana: "mar",
      numero: "29",
    });
  });
});

describe("resumenSerie", () => {
  it("último, máximo y mínimo sin contar los huecos", () => {
    expect(
      resumenSerie([
        { t: 1, valor: 24 },
        { t: 2, valor: null },
        { t: 3, valor: 21.5 },
        { t: 4, valor: 23 },
      ]),
    ).toEqual({ ultimo: { t: 4, valor: 23 }, maximo: 24, minimo: 21.5 });
  });

  it("sin lecturas, nada", () => {
    expect(resumenSerie([])).toEqual({ ultimo: null, maximo: null, minimo: null });
  });
});
