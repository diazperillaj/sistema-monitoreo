import { describe, expect, it } from "vitest";
import { central, FL, HAB, nodo } from "../test/datos";
import { franja } from "./momento";

const conBanderas = (
  flPuerta: number,
  flHabitacion: number,
  habHabitacion: number = HAB.PRINCIPAL,
) =>
  central([
    nodo(0, { fl: FL.HORA_VALIDA | flPuerta }),
    nodo(1, { fl: FL.HORA_VALIDA | flHabitacion, hab: habHabitacion }),
    nodo(2),
    nodo(3),
    nodo(4),
  ]);

describe("franja del momento, según las banderas de la central", () => {
  it("de día", () => {
    expect(franja(conBanderas(0, 0)).momento).toBe("dia");
  });

  it("de noche con la habitación en pausa", () => {
    const f = franja(conBanderas(0, FL.HORARIO_NOCTURNO, 0));
    expect(f.momento).toBe("noche");
    expect(f.texto).toBe("Noche: la habitación está en pausa hasta las 6:00");
  });

  it("de noche con la habitación reactivada por alguien", () => {
    expect(franja(conBanderas(0, FL.HORARIO_NOCTURNO)).texto).toMatch(/vigila porque la activaron/);
  });

  it("de madrugada: la puerta vigila", () => {
    const f = franja(conBanderas(FL.MADRUGADA, FL.HORARIO_NOCTURNO, 0));
    expect(f.momento).toBe("madrugada");
    expect(f.texto).toMatch(
      /^Madrugada: la puerta vigila movimiento y la habitación está en pausa/,
    );
  });

  it("sin hora válida, los horarios no funcionan y lo dice", () => {
    expect(franja({ ...conBanderas(0, 0), horaValida: false }).momento).toBe("sin_hora");
  });
});
