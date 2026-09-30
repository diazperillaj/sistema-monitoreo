import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderizarRutas } from "../test/renderizar";
import { API, errorApi, servidor, yoAdmin } from "../test/servidor";
import Login, { rutaSegura } from "./Login";

describe("rutaSegura: tras entrar solo se vuelve a rutas de esta app", () => {
  it.each([
    ["/casa/1", "/casa/1"],
    ["/casa/1/historial?ver=eventos", "/casa/1/historial?ver=eventos"],
    [null, "/"],
    ["https://otro.sitio", "/"],
    ["//otro.sitio", "/"],
    ["/\\otro.sitio", "/"],
    ["/login?volver=/x", "/"],
  ])("%s → %s", (volver, esperado) => {
    expect(rutaSegura(volver)).toBe(esperado);
  });
});

describe("Login", () => {
  function llenar() {
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ana@ejemplo.com" } });
    fireEvent.change(screen.getByLabelText("Clave"), { target: { value: "una clave larga" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
  }

  it("con datos incorrectos lo dice junto al campo", async () => {
    servidor.use(
      http.get(`${API}/auth/yo`, () => errorApi(401, "no_autenticado", "Sin sesión")),
      http.post(`${API}/auth/login`, () =>
        errorApi(401, "credenciales_invalidas", "Email o clave incorrectos."),
      ),
    );
    renderizarRutas([{ path: "/login", element: <Login /> }], "/login");
    await screen.findByLabelText("Email");
    llenar();
    expect(await screen.findByText("Email o clave incorrectos.")).toBeInTheDocument();
    expect(screen.getByLabelText("Clave")).toHaveAttribute("aria-invalid", "true");
  });

  it("al entrar vuelve a ?volver=", async () => {
    let conSesion = false;
    servidor.use(
      http.get(`${API}/auth/yo`, () =>
        conSesion ? HttpResponse.json(yoAdmin) : errorApi(401, "no_autenticado", "Sin sesión"),
      ),
      http.post(`${API}/auth/login`, () => {
        conSesion = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { router } = renderizarRutas(
      [
        { path: "/login", element: <Login /> },
        { path: "/casa/1/historial", element: <p>Historial</p> },
      ],
      "/login?volver=%2Fcasa%2F1%2Fhistorial",
    );
    await screen.findByLabelText("Email");
    llenar();
    expect(await screen.findByText("Historial")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe("/casa/1/historial"));
  });
});

describe("Login sin datos", () => {
  it("el botón no se apaga: al tocarlo dice qué falta junto a cada campo", async () => {
    servidor.use(http.get(`${API}/auth/yo`, () => errorApi(401, "no_autenticado", "Sin sesión")));
    renderizarRutas([{ path: "/login", element: <Login /> }], "/login");
    const boton = await screen.findByRole("button", { name: "Entrar" });
    expect(boton).toBeEnabled();
    fireEvent.click(boton);
    expect(await screen.findByText("Escribe tu email.")).toBeInTheDocument();
    expect(screen.getByText("Escribe tu clave.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });
});
