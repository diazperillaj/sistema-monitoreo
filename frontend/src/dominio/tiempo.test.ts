import { describe, expect, it } from "vitest";
import { cuando, desde, dia, duracion, hace, hora } from "./tiempo";

// 29/09/2026 15:00 en Bogotá (UTC-5)
const ahora = new Date("2026-09-29T20:00:00Z");

describe("horas y duraciones en español, con la hora de Bogotá", () => {
  it("la hora es la de Bogotá, no la del equipo", () => {
    expect(hora("2026-09-29T19:35:00Z")).toBe("14:35");
  });

  it("cuándo: hoy, ayer o con fecha", () => {
    expect(cuando("2026-09-29T19:35:00Z", ahora)).toBe("14:35");
    expect(cuando("2026-09-28T19:35:00Z", ahora)).toBe("ayer 14:35");
    expect(cuando("2026-09-26T19:35:00Z", ahora)).toMatch(/^26 .+ 14:35$/);
  });

  it("el día para agrupar el historial", () => {
    expect(dia("2026-09-29T13:00:00Z", ahora)).toBe("Hoy");
    // 04:00 UTC del 29 son las 23:00 del 28 en Bogotá
    expect(dia("2026-09-29T04:00:00Z", ahora)).toBe("Ayer");
    expect(dia("2026-09-26T15:00:00Z", ahora)).toMatch(/^Sábado, 26 de septiembre$/i);
  });

  it("desde cuándo", () => {
    expect(desde("2026-09-29T19:35:00Z", ahora)).toBe("desde las 14:35");
    expect(desde("2026-09-28T19:35:00Z", ahora)).toBe("desde ayer a las 14:35");
  });

  it("duraciones", () => {
    expect(duracion(45)).toBe("45 s");
    expect(duracion(180)).toBe("3 min");
    expect(duracion(3900)).toBe("1 h 5 min");
    expect(duracion(7200)).toBe("2 h");
    expect(duracion(183_600)).toBe("2 d 3 h");
    expect(hace(3)).toBe("ahora");
    expect(hace(12)).toBe("hace 12 s");
  });
});
