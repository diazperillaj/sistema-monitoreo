import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { renderizarRutas } from "../test/renderizar";
import { API, preferenciasBase, servidor } from "../test/servidor";
import Perfil from "./Perfil";

const sesiones = [
  {
    id: 10,
    user_agent:
      "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0 Mobile Safari/537.36",
    ip: "190.24.8.17",
    creada_en: "2026-09-20T12:00:00Z",
    ultimo_uso_en: "2026-09-29T19:00:00Z",
    expira_en: "2026-10-20T12:00:00Z",
    actual: true,
  },
  {
    id: 11,
    user_agent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0 Safari/537.36 Edg/154.0",
    ip: "181.51.3.200",
    creada_en: "2026-09-18T12:00:00Z",
    ultimo_uso_en: "2026-09-27T01:00:00Z",
    expira_en: "2026-10-18T12:00:00Z",
    actual: false,
  },
];

let cerradas: number[];

beforeEach(() => {
  cerradas = [];
  servidor.use(
    http.get(`${API}/auth/sesiones`, () => HttpResponse.json(sesiones)),
    http.delete(`${API}/auth/sesiones/:id`, ({ params }) => {
      cerradas.push(Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
});

function montar() {
  return renderizarRutas([{ path: "/perfil", element: <Perfil /> }], "/perfil");
}

describe("Perfil", () => {
  it("sin Telegram disponible no muestra nada de Telegram", async () => {
    montar();
    await screen.findByText("Alertas por notificación");
    expect(screen.queryByText(/telegram/i)).not.toBeInTheDocument();
  });

  it("en un navegador sin Web Push lo dice en vez de ofrecer un botón que no sirve", async () => {
    montar();
    expect(
      await screen.findByText(/Este navegador no puede recibir notificaciones/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Activar en este dispositivo/ }),
    ).not.toBeInTheDocument();
  });

  it("pausar las alertas de la cuenta manda webpush: false", async () => {
    let cambio: unknown;
    servidor.use(
      http.patch(`${API}/notificaciones/preferencias`, async ({ request }) => {
        cambio = await request.json();
        return HttpResponse.json({
          ...preferenciasBase,
          webpush: { activo: false, dispositivos: 1 },
        });
      }),
    );
    montar();
    const palanca = await screen.findByRole("switch", {
      name: "Alertas por notificación en todos tus dispositivos",
    });
    fireEvent.click(palanca);
    await waitFor(() => expect(palanca).not.toBeChecked());
    expect(cambio).toEqual({ webpush: false });
    expect(await screen.findByText(/En pausa en tu dispositivo/)).toBeInTheDocument();
  });

  it("las sesiones dicen de qué dispositivo son y se pueden cerrar las otras", async () => {
    montar();
    const actual = (await screen.findByText("Chrome en Android")).closest("li")!;
    expect(within(actual).getByText("Esta sesión")).toBeInTheDocument();
    expect(within(actual).queryByRole("button", { name: "Cerrar" })).not.toBeInTheDocument();

    const otra = screen.getByText("Edge en Windows").closest("li")!;
    fireEvent.click(within(otra).getByRole("button", { name: "Cerrar" }));
    await waitFor(() => expect(cerradas).toEqual([11]));
  });

  it("la clave nueva necesita 10 caracteres y repetirse igual", async () => {
    montar();
    fireEvent.change(await screen.findByLabelText("Clave actual"), {
      target: { value: "clave vieja" },
    });
    fireEvent.change(screen.getByLabelText("Clave nueva"), { target: { value: "corta" } });
    fireEvent.change(screen.getByLabelText("Repite la clave nueva"), {
      target: { value: "otra" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cambiar clave" }));
    expect(screen.getByText("Le faltan caracteres: mínimo 10.")).toBeInTheDocument();
    expect(screen.getByText("No coincide con la clave nueva.")).toBeInTheDocument();
  });
});
