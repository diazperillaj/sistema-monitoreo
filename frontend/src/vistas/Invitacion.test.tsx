/** Quien abre un enlace de invitación (§8.2): con cuenta, sin cuenta y enlaces que no sirven. */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { renderizarRutas } from "../test/renderizar";
import { API, errorApi, servidor, yoAdmin, yoCuidador } from "../test/servidor";
import Invitacion from "./Invitacion";

const TOKEN = "token-de-prueba";

let aceptada: unknown;
let conSesion: boolean;

beforeEach(() => {
  aceptada = undefined;
  conSesion = false;
  servidor.use(
    http.get(`${API}/auth/yo`, () =>
      conSesion ? HttpResponse.json(yoCuidador) : errorApi(401, "no_autenticado", "Sin sesión"),
    ),
    http.get(`${API}/invitaciones/${TOKEN}`, () =>
      HttpResponse.json({
        casa_nombre: "Casa de la abuela",
        rol: "cuidador",
        email: "tomas@ejemplo.com",
      }),
    ),
    http.post(`${API}/invitaciones/${TOKEN}/aceptar`, async ({ request }) => {
      aceptada = await request.json();
      conSesion = true; // la API entrega la cookie
      return HttpResponse.json(yoCuidador.usuario);
    }),
  );
});

function montar() {
  return renderizarRutas(
    [
      { path: "/invitacion/:token", element: <Invitacion /> },
      { path: "/", element: <p>Inicio de la app</p> },
      { path: "/login", element: <p>Pantalla de entrada</p> },
    ],
    `/invitacion/${TOKEN}`,
  );
}

describe("Invitación", () => {
  it("sin cuenta: dice a qué casa invitan, crea la cuenta y entra", async () => {
    const { router } = montar();
    expect(
      await screen.findByRole("heading", { name: "Te invitaron a Casa de la abuela" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("tomas@ejemplo.com"); // lo trae el enlace

    fireEvent.change(screen.getByLabelText("Tu nombre"), { target: { value: " Tomás " } });
    fireEvent.change(screen.getByLabelText("Clave"), { target: { value: "una clave larga" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta y entrar" }));

    expect(await screen.findByText("Inicio de la app")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
    expect(aceptada).toEqual({
      nombre: "Tomás",
      email: "tomas@ejemplo.com",
      clave: "una clave larga",
    });
  });

  it("antes de enviar dice qué falta, junto a cada campo", async () => {
    montar();
    fireEvent.click(await screen.findByRole("button", { name: "Crear cuenta y entrar" }));
    expect(await screen.findByText("Escribe tu nombre.")).toBeInTheDocument();
    expect(screen.getByText("La clave necesita al menos 10 caracteres.")).toBeInTheDocument();
    expect(screen.getByLabelText("Tu nombre")).toHaveFocus(); // el primero por corregir
    expect(aceptada).toBeUndefined();
  });

  it("con un email que ya tiene cuenta, ofrece entrar con ella", async () => {
    servidor.use(
      http.post(`${API}/invitaciones/${TOKEN}/aceptar`, () =>
        errorApi(
          409,
          "email_en_uso",
          "Ya hay una cuenta con ese email. Entra con ella y vuelve a abrir este enlace.",
        ),
      ),
    );
    montar();
    fireEvent.change(await screen.findByLabelText("Tu nombre"), { target: { value: "Tomás" } });
    fireEvent.change(screen.getByLabelText("Clave"), { target: { value: "una clave larga" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta y entrar" }));
    const enlace = await screen.findByRole("link", { name: "Entrar con esa cuenta" });
    expect(enlace).toHaveAttribute(
      "href",
      `/login?volver=${encodeURIComponent(`/invitacion/${TOKEN}`)}`,
    );
  });

  it("con sesión: se une con su cuenta, sin formulario", async () => {
    conSesion = true;
    servidor.use(http.get(`${API}/auth/yo`, () => HttpResponse.json(yoAdmin)));
    montar();
    expect(await screen.findByText(/Vas a entrar con tu cuenta/)).toHaveTextContent("Ana Lucía");
    expect(screen.queryByLabelText("Clave")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Unirme a la casa" }));
    expect(await screen.findByText("Inicio de la app")).toBeInTheDocument();
    expect(aceptada).toEqual({});
  });

  it("un enlace vencido lo dice y lleva a la entrada", async () => {
    servidor.use(
      http.get(`${API}/invitaciones/${TOKEN}`, () =>
        errorApi(
          410,
          "invitacion_vencida",
          "Esta invitación venció. Pide una nueva a quien te invitó.",
        ),
      ),
    );
    montar();
    expect(
      await screen.findByRole("heading", { name: "Esta invitación venció" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Pide una nueva a quien te invitó/)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Ir a la entrada" })).toHaveAttribute(
        "href",
        "/login",
      ),
    );
  });
});
