/** Rutas y guardas (§13.5). */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RequiereAdmin, RequiereMiembro, RequiereSesion, rutas } from "./rutas";
import { renderizarRutas } from "./test/renderizar";
import { estadoCasa } from "./test/datos";
import { API, errorApi, servidor, yoCuidador } from "./test/servidor";
import { WsFalso } from "./test/wsFalso";

describe("rutas y guardas", () => {
  it("sin sesión, al login con ?volver= a donde iba", async () => {
    servidor.use(http.get(`${API}/auth/yo`, () => errorApi(401, "no_autenticado", "Sin sesión")));
    const { router } = renderizarRutas(rutas, "/casa/1/historial?ver=eventos");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.search).toBe(
      `?volver=${encodeURIComponent("/casa/1/historial?ver=eventos")}`,
    );
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("un cuidador que entra a una vista de admin vuelve al tablero", async () => {
    servidor.use(http.get(`${API}/auth/yo`, () => HttpResponse.json(yoCuidador)));
    const { router } = renderizarRutas(
      [
        {
          element: <RequiereSesion />,
          children: [
            { path: "/casa/:casaId", element: <p>Tablero</p> },
            {
              path: "/casa/:casaId/miembros",
              element: <RequiereAdmin />,
              children: [{ index: true, element: <p>Miembros</p> }],
            },
          ],
        },
      ],
      "/casa/1/miembros",
    );
    expect(await screen.findByText("Tablero")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/casa/1");
  });

  it("una casa que no es suya lleva al inicio", async () => {
    const { router } = renderizarRutas(
      [
        {
          element: <RequiereSesion />,
          children: [
            { path: "/", element: <p>Inicio</p> },
            {
              path: "/casa/:casaId",
              element: <RequiereMiembro />,
              children: [{ index: true, element: <p>Tablero</p> }],
            },
          ],
        },
      ],
      "/casa/7",
    );
    expect(await screen.findByText("Inicio")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("una ruta que no existe muestra la página de no encontrado", async () => {
    renderizarRutas(rutas, "/no/existe");
    expect(
      await screen.findByRole("heading", { name: "Esta página no existe" }),
    ).toBeInTheDocument();
  });
});

describe("vistas de admin, con las rutas reales", () => {
  beforeEach(() => {
    WsFalso.reiniciar();
    vi.stubGlobal("WebSocket", WsFalso);
    servidor.use(http.get(`${API}/casas/1/estado`, () => HttpResponse.json(estadoCasa())));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("el cuidador no ve Ajustes y, si escribe la dirección de Miembros, vuelve al tablero", async () => {
    servidor.use(http.get(`${API}/auth/yo`, () => HttpResponse.json(yoCuidador)));
    const { router } = renderizarRutas(rutas, "/casa/1/miembros");
    await waitFor(() => expect(router.state.location.pathname).toBe("/casa/1"));
    expect((await screen.findAllByRole("link", { name: "Gráficas" })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Ajustes" })).not.toBeInTheDocument();
  });

  it("el admin sí ve Ajustes", async () => {
    renderizarRutas(rutas, "/casa/1");
    expect((await screen.findAllByRole("link", { name: "Ajustes" })).length).toBeGreaterThan(0);
  });
});

describe("salir", () => {
  it("al salir de la cuenta lleva al login", async () => {
    let conSesion = true;
    servidor.use(
      http.get(`${API}/auth/yo`, () =>
        conSesion ? HttpResponse.json(yoCuidador) : errorApi(401, "no_autenticado", "Sin sesión"),
      ),
      http.post(`${API}/auth/logout`, () => {
        conSesion = false;
        return new HttpResponse(null, { status: 204 });
      }),
      http.get(`${API}/auth/sesiones`, () => HttpResponse.json([])),
    );
    const Perfil = (await import("./vistas/Perfil")).default;
    const { router } = renderizarRutas(
      [
        {
          element: <RequiereSesion />,
          children: [{ path: "/perfil", element: <Perfil /> }],
        },
        { path: "/login", element: <p>Pantalla de entrada</p> },
      ],
      "/perfil",
    );
    fireEvent.click(await screen.findByRole("button", { name: /Salir de esta cuenta/ }));
    expect(await screen.findByText("Pantalla de entrada")).toBeInTheDocument();
    // Sin ?volver=: quien entre después empieza en su casa, no en el perfil de otro
    await waitFor(() => expect(router.state.location.search).toBe(""));
    expect(router.state.location.pathname).toBe("/login");
  });
});
