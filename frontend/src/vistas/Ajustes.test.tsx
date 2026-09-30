/** Ajustes de la casa (§8.3): se guarda solo lo que cambió, y los números fuera de rango se avisan. */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { enLaCasa, renderizarRutas } from "../test/renderizar";
import { API, servidor } from "../test/servidor";
import Ajustes from "./Ajustes";

const CASA = {
  id: 1,
  codigo: "casa-abuela",
  nombre: "Casa de la abuela",
  creada_en: "2026-09-01T12:00:00Z",
  ajustes: {
    recordatorio_min: 5,
    recordatorio_conexion_min: 60,
    minutos_central_caida: 1,
    avisar_nodo_sin_conexion: true,
    avisar_resueltas: true,
  },
};

let cambios: unknown[];

beforeEach(() => {
  cambios = [];
  servidor.use(
    http.get(`${API}/casas/1`, () => HttpResponse.json(CASA)),
    http.patch(`${API}/casas/1/ajustes`, async ({ request }) => {
      const cambio = (await request.json()) as Record<string, unknown>;
      cambios.push(cambio);
      return HttpResponse.json({ ...CASA.ajustes, ...cambio });
    }),
  );
});

function montar() {
  renderizarRutas(
    [{ path: "/casa/:casaId/ajustes", element: enLaCasa(<Ajustes />) }],
    "/casa/1/ajustes",
  );
}

describe("Ajustes", () => {
  it("guarda solo lo que cambió", async () => {
    montar();
    const guardar = await screen.findByRole("button", { name: "Guardar cambios" });
    expect(guardar).toBeDisabled(); // sin cambios todavía
    fireEvent.change(screen.getByLabelText("Repetir el aviso de una alarma cada"), {
      target: { value: "10" },
    });
    fireEvent.click(screen.getByRole("switch", { name: "Alarma resuelta" }));
    fireEvent.click(guardar);
    await waitFor(() =>
      expect(cambios).toEqual([{ recordatorio_min: 10, avisar_resueltas: false }]),
    );
    expect(await screen.findByText("Ajustes guardados")).toBeInTheDocument();
  });

  it("un número fuera de rango se avisa y, al guardar, lleva a él sin enviar nada", async () => {
    montar();
    const caida = await screen.findByLabelText("Avisar que la central se desconectó después de");
    fireEvent.change(caida, { target: { value: "0" } });
    expect(screen.getByText("Un número entre 1 y 1440.")).toBeInTheDocument();
    expect(caida).toHaveAccessibleDescription(/Un número entre 1 y 1440\./);
    // Como en el resto de la app, el botón sigue habilitado (DESIGN.md)
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(caida).toHaveFocus();
    expect(cambios).toEqual([]);
  });
});
