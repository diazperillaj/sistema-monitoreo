/**
 * Gráficas (§11.2). En jsdom Recharts no dibuja (no hay tamaño), así que se prueba lo que sí se lee
 * sin mirar la gráfica: el resumen de cada medida, la tabla de datos y los estados vacíos.
 */
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { enLaCasa, renderizarRutas } from "../test/renderizar";
import { API, servidor } from "../test/servidor";
import Graficas from "./Graficas";

function hace(minutos: number): string {
  return new Date(Date.now() - minutos * 60_000).toISOString();
}

let pedidas: URLSearchParams[];

beforeEach(() => {
  pedidas = [];
  servidor.use(
    http.get(`${API}/casas/1/lecturas`, ({ request }) => {
      pedidas.push(new URL(request.url).searchParams);
      const metrica = new URL(request.url).searchParams.get("metrica");
      if (metrica === "temperatura") {
        return HttpResponse.json([
          { t: hace(15), valor: 22.4 },
          { t: hace(10), valor: 26.1 },
          { t: hace(5), valor: 24.6 },
        ]);
      }
      return HttpResponse.json([]);
    }),
    http.get(`${API}/casas/1/resumen`, () =>
      HttpResponse.json({
        dias: 7,
        alarmas_por_tipo: { SIN_MOVIMIENTO: 3, CENTRAL_DESCONECTADA: 1 },
        tiempo_medio_respuesta_s: 150,
        alarmas_por_dia: [
          ...["2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28"].map((dia) => ({
            dia,
            sensor: 0,
            conexion: 0,
          })),
          { dia: "2026-09-29", sensor: 1, conexion: 1 },
          { dia: "2026-09-30", sensor: 2, conexion: 0 },
        ],
      }),
    ),
  );
});

function montar() {
  renderizarRutas(
    [{ path: "/casa/:casaId/graficas", element: enLaCasa(<Graficas />) }],
    "/casa/1/graficas",
  );
}

describe("Gráficas", () => {
  it("cada medida dice su última lectura, el máximo y el mínimo", async () => {
    montar();
    const temperatura = await screen.findByRole("region", { name: "Temperatura de la cocina" });
    expect(await within(temperatura).findByText("24.6 °C")).toBeInTheDocument();
    expect(within(temperatura).getByText("Ahora")).toBeInTheDocument();
    expect(within(temperatura).getByText("26.1 °C")).toBeInTheDocument();
    expect(within(temperatura).getByText("22.4 °C")).toBeInTheDocument();
    // La tabla, para quien no puede ver la gráfica
    expect(within(temperatura).getByText("Ver los datos")).toBeInTheDocument();
    expect(within(temperatura).getAllByRole("row")).toHaveLength(4);
  });

  it("sin lecturas lo dice en vez de dibujar una gráfica vacía", async () => {
    montar();
    const agua = await screen.findByRole("region", { name: "Agua de la cocina" });
    expect(
      await within(agua).findByText(/Sin lecturas en las últimas 24 horas/),
    ).toBeInTheDocument();
  });

  it("el periodo cambia las tres medidas a la vez", async () => {
    montar();
    const semana = await screen.findByRole("radio", { name: "7 días" });
    expect(screen.getByRole("radio", { name: "24 horas" })).toBeChecked();
    fireEvent.click(semana);
    expect(semana).toBeChecked();
    const agua = screen.getByRole("region", { name: "Agua de la cocina" });
    expect(await within(agua).findByText(/Sin lecturas en los últimos 7 días/)).toBeInTheDocument();
    // Una hora por punto y una semana de ancho, para cada medida
    await waitFor(() =>
      expect(pedidas.filter((p) => p.get("agregacion") === "1h")).toHaveLength(3),
    );
    const semanal = pedidas.find((p) => p.get("agregacion") === "1h")!;
    const ancho = Date.parse(semanal.get("hasta")!) - Date.parse(semanal.get("desde")!);
    expect(ancho).toBe(7 * 24 * 3600_000);
  });

  it("el resumen de alarmas: total, tiempo para silenciar y por tipo", async () => {
    montar();
    const alarmas = await screen.findByRole("region", { name: "Alarmas de los últimos 7 días" });
    expect(await within(alarmas).findByText("4")).toBeInTheDocument();
    expect(within(alarmas).getByText("2 min en promedio")).toBeInTheDocument();
    expect(
      within(alarmas).getByText("Sin movimiento 3 · Central desconectada 1"),
    ).toBeInTheDocument();
    expect(within(alarmas).getByText("De los sensores")).toBeInTheDocument(); // la leyenda
  });
});
