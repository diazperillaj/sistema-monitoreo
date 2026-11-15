import { describe, expect, it } from "vitest";
import { situacion, textoAviso, type Entradas } from "./conexion";

const base: Entradas = {
  conexion: "en_vivo",
  hayDatos: true,
  consultaFallo: false,
  centralEnLinea: true,
  centralCambioEn: "2026-09-29T19:35:00Z",
  edadS: 2,
};

describe("qué tan al día está lo que se ve", () => {
  it("en vivo", () => {
    expect(situacion(base).tipo).toBe("en_vivo");
  });

  it("datos con retraso pasados los 20 s", () => {
    expect(situacion({ ...base, edadS: 21 })).toEqual({ tipo: "retraso", edadS: 21 });
  });

  it("la central desconectada pesa más que el retraso", () => {
    expect(situacion({ ...base, centralEnLinea: false, edadS: 500 }).tipo).toBe(
      "central_desconectada",
    );
  });

  it("sin WebSocket pero con el sondeo funcionando: cada 5 s", () => {
    expect(situacion({ ...base, conexion: "respaldo" }).tipo).toBe("respaldo");
  });

  it("sin WebSocket y con el sondeo fallando: sin conexión con el servidor", () => {
    expect(situacion({ ...base, conexion: "respaldo", consultaFallo: true }).tipo).toBe(
      "sin_servidor",
    );
  });

  it("el aviso de la central dice desde cuándo, con la hora de Bogotá", () => {
    const ahora = new Date("2026-09-29T20:00:00Z");
    expect(textoAviso({ tipo: "central_desconectada", desde: base.centralCambioEn }, ahora)).toBe(
      "La central está desconectada desde las 14:35. Lo que ves es lo último que mandó.",
    );
  });

  it("en vivo no hay aviso", () => {
    expect(textoAviso({ tipo: "en_vivo" })).toBeNull();
  });
});
