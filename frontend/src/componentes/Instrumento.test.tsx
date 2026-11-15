import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AL, FL, HAB, nodo } from "../test/datos";
import { renderizar } from "../test/renderizar";
import { Instrumento } from "./Instrumento";

function tira(n: ReturnType<typeof nodo>, vivo = true, edadS = 0) {
  renderizar(
    <ul>
      <Instrumento casaId={1} nodo={n} vivo={vivo} edadS={edadS} />
    </ul>,
  );
  return screen.getByRole("listitem");
}

describe("Instrumento (antes TarjetaNodo)", () => {
  it.each([
    ["ALARMA", nodo(2, { al: AL.SIN_MOVIMIENTO })],
    ["Desactivado", nodo(2, { hab: 0 })],
    ["Sin conexión", nodo(2, { enLinea: false, hace: 300 })],
    ["Esperando nodo", nodo(2, { visto: false })],
    ["Vigilando", nodo(2)],
  ])("muestra el distintivo %s", (texto, n) => {
    const li = tira(n);
    expect(within(li).getByText(new RegExp(`^${texto}`))).toBeInTheDocument();
  });

  it("sin conexión dice hace cuánto llegó el último dato y va rayado", () => {
    const li = tira(nodo(2, { enLinea: false, hace: 300 }));
    expect(li).toHaveTextContent("Sin conexión · último dato hace 5 min");
    expect(li).toHaveClass("rayado");
  });

  it("el contador avanza con la edad del dato y se lee como medidor", () => {
    tira(nodo(2, { fl: FL.HORA_VALIDA | FL.CONTANDO1, c1: 120 }), true, 15);
    const medidor = screen.getByRole("meter", { name: "Sin movimiento" });
    expect(medidor).toHaveAttribute("aria-valuenow", "135");
    expect(medidor).toHaveAttribute("aria-valuemax", "600");
    expect(screen.getByText("02:15")).toBeInTheDocument();
  });

  it("en alarma, la escala queda llena y dice por qué", () => {
    const li = tira(nodo(2, { al: AL.SIN_MOVIMIENTO }));
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "600");
    expect(li).toHaveTextContent("Sin movimiento por 10 min");
  });

  it("dice 'Movimiento ahora' solo si lo hay, y no muestra la lectura cruda del gas", () => {
    const li = tira(nodo(4, { mov: 1, v2: 1950 }));
    expect(li).toHaveTextContent("Movimiento ahora");
    expect(li).not.toHaveTextContent("1950");
  });

  it("el agua no confunde la llave abierta con una persona", () => {
    const li = tira(nodo(3, { mov: 1 }));
    expect(li).not.toHaveTextContent("Movimiento ahora");
    expect(li).toHaveTextContent("Llave abierta");
  });

  it("el nodo 4 tiene sus dos interruptores", () => {
    tira(nodo(4, { hab: HAB.PRINCIPAL }));
    expect(screen.getByRole("switch", { name: "Gas y temperatura" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "Presencia (inactividad)" })).not.toBeChecked();
  });

  it("sin la central, nada se da por bueno: sin datos y sin mandos", () => {
    const li = tira(nodo(2), false);
    expect(li).toHaveTextContent("Sin datos");
    expect(screen.getByRole("switch", { name: "Vigilancia del baño" })).toBeDisabled();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuetext", "Sin medir");
  });
});
