import { describe, expect, it } from "vitest";
import { AL, nodo } from "../test/datos";
import { minutos, mmss, reloj, textosAlarma } from "./textos";

describe("textosAlarma (portado de la app local)", () => {
  it("un texto por cada bit, en el orden de la app local", () => {
    expect(textosAlarma(nodo(0, { al: AL.INTRUSION }))).toEqual([
      "Movimiento en la entrada durante la madrugada",
    ]);
    expect(textosAlarma(nodo(2, { al: AL.SIN_MOVIMIENTO }))).toEqual(["Sin movimiento por 10 min"]);
    expect(textosAlarma(nodo(3, { al: AL.AGUA }))).toEqual(["Agua corriendo más de 8 min"]);
    expect(textosAlarma(nodo(4, { al: AL.GAS }))).toEqual(["Gas detectado por más de 4 min"]);
    expect(textosAlarma(nodo(4, { al: AL.TEMPERATURA, v1: 56.04 }))).toEqual([
      "Temperatura alta: 56.0 °C",
    ]);
  });

  it("nodo 4 con gas y temperatura a la vez: los dos textos", () => {
    expect(textosAlarma(nodo(4, { al: AL.GAS | AL.TEMPERATURA, v1: 61.3 }))).toEqual([
      "Gas detectado por más de 4 min",
      "Temperatura alta: 61.3 °C",
    ]);
  });

  it("la inactividad del nodo 4 usa su segundo límite (l2)", () => {
    expect(textosAlarma(nodo(4, { al: AL.SIN_MOVIMIENTO }))).toEqual(["Sin movimiento por 20 min"]);
  });

  it("sin alarmas, ningún texto", () => {
    expect(textosAlarma(nodo(1))).toEqual([]);
  });
});

describe("formatos de tiempo", () => {
  it("minutos enteros, como el firmware", () => {
    expect(minutos(599)).toBe(9);
    expect(minutos(600)).toBe(10);
    expect(minutos(-5)).toBe(0);
  });

  it("mm:ss sin tope de minutos", () => {
    expect(mmss(0)).toBe("00:00");
    expect(mmss(432.9)).toBe("07:12");
    expect(mmss(7500)).toBe("125:00");
  });

  it("reloj pasa a h:mm:ss desde la hora", () => {
    expect(reloj(192)).toBe("03:12");
    expect(reloj(3600)).toBe("1:00:00");
    expect(reloj(3912)).toBe("1:05:12");
  });
});
