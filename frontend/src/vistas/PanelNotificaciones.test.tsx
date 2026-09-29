import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PanelNotificaciones from "./PanelNotificaciones";

/** Una API falsa: responde según la ruta y el método. */
function api(respuestas: Record<string, { estado: number; cuerpo?: unknown }>) {
  const llamadas: { ruta: string; metodo: string; cuerpo?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (ruta: string, opciones?: RequestInit) => {
      const metodo = opciones?.method ?? "GET";
      llamadas.push({
        ruta,
        metodo,
        cuerpo: opciones?.body ? JSON.parse(String(opciones.body)) : undefined,
      });
      const respuesta = respuestas[`${metodo} ${ruta}`] ?? { estado: 404 };
      return new Response(JSON.stringify(respuesta.cuerpo ?? {}), { status: respuesta.estado });
    }),
  );
  return llamadas;
}

const ANA = { id: 1, email: "ana@ejemplo.com", nombre: "Ana", es_superadmin: false };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PanelNotificaciones (prueba de Web Push en F4)", () => {
  it("sin sesión pide entrar y entra con email y clave", async () => {
    const llamadas = api({
      "GET /api/v1/auth/yo": { estado: 401 },
      "POST /api/v1/auth/login": { estado: 200, cuerpo: ANA },
    });
    render(<PanelNotificaciones />);
    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "ana@ejemplo.com" },
    });
    fireEvent.change(screen.getByLabelText("Clave"), { target: { value: "clave-de-ana" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Hola, Ana.")).toBeInTheDocument();
    expect(llamadas.at(-1)).toEqual({
      ruta: "/api/v1/auth/login",
      metodo: "POST",
      cuerpo: { email: "ana@ejemplo.com", clave: "clave-de-ana" },
    });
  });

  it("una clave equivocada muestra el error", async () => {
    api({
      "GET /api/v1/auth/yo": { estado: 401 },
      "POST /api/v1/auth/login": { estado: 401 },
    });
    render(<PanelNotificaciones />);
    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "ana@ejemplo.com" },
    });
    fireEvent.change(screen.getByLabelText("Clave"), { target: { value: "otra" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email o clave incorrectos.");
  });

  it("avisa si el navegador no permite notificaciones push", async () => {
    api({ "GET /api/v1/auth/yo": { estado: 200, cuerpo: { usuario: ANA, casas: [] } } });
    render(<PanelNotificaciones />); // jsdom no tiene service worker ni PushManager
    expect(
      await screen.findByText("Este navegador no permite notificaciones push."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
