/** Miembros (§8.6) e invitaciones (§8.2) desde la vista del admin. */
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { enLaCasa, renderizarRutas } from "../test/renderizar";
import { API, servidor } from "../test/servidor";
import Miembros from "./Miembros";

const MIEMBROS = [
  {
    usuario: { id: 1, nombre: "Ana Lucía", email: "ana@ejemplo.com" },
    rol: "admin",
    creado_en: "2026-09-01T12:00:00Z",
  },
  {
    usuario: { id: 2, nombre: "Tomás", email: "tomas@ejemplo.com" },
    rol: "cuidador",
    creado_en: "2026-09-02T12:00:00Z",
  },
];

interface Vigente {
  id: number;
  rol: string;
  email: string | null;
  creada_en: string;
  expira_en: string;
  creada_por: { id: number; nombre: string } | null;
}

let miembros: typeof MIEMBROS;
let vigentes: Vigente[];
let quitados: number[];
let creadas: unknown[];

// Las listas cambian de verdad: quien se quita desaparece de la pantalla, como en la app
beforeEach(() => {
  miembros = structuredClone(MIEMBROS);
  vigentes = [];
  quitados = [];
  creadas = [];
  servidor.use(
    http.get(`${API}/casas/1/miembros`, () => HttpResponse.json(miembros)),
    http.get(`${API}/casas/1/invitaciones`, () => HttpResponse.json(vigentes)),
    http.delete(`${API}/casas/1/invitaciones/:id`, ({ params }) => {
      vigentes = vigentes.filter((v) => v.id !== Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
    http.delete(`${API}/casas/1/miembros/:id`, ({ params }) => {
      quitados.push(Number(params.id));
      miembros = miembros.filter((m) => m.usuario.id !== Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
    http.patch(`${API}/casas/1/miembros/:id`, async ({ params, request }) => {
      const { rol } = (await request.json()) as { rol: string };
      const miembro = miembros.find((m) => m.usuario.id === Number(params.id))!;
      miembro.rol = rol;
      return HttpResponse.json(miembro);
    }),
    http.post(`${API}/casas/1/invitaciones`, async ({ request }) => {
      const cuerpo = (await request.json()) as { rol: string; email?: string };
      creadas.push(cuerpo);
      vigentes = [
        {
          id: 7,
          rol: cuerpo.rol,
          email: cuerpo.email ?? null,
          creada_en: "2026-09-30T19:35:00Z",
          expira_en: "2026-10-03T19:35:00Z",
          creada_por: { id: 1, nombre: "Ana Lucía" },
        },
      ];
      return HttpResponse.json(
        {
          id: 7,
          url: "http://localhost:3000/invitacion/abc123",
          expira_en: "2026-10-03T19:35:00Z",
        },
        { status: 201 },
      );
    }),
  );
});

function montar() {
  return renderizarRutas(
    [{ path: "/casa/:casaId/miembros", element: enLaCasa(<Miembros />) }],
    "/casa/1/miembros",
  );
}

describe("Miembros", () => {
  it("la única admin no se puede bajar de rol ni quitar, y la pantalla dice por qué", async () => {
    montar();
    const ana = (await screen.findByText("Ana Lucía")).closest("li")!;
    expect(within(ana).getByText("Tú")).toBeInTheDocument();
    expect(within(ana).getByLabelText("Rol de Ana Lucía")).toBeDisabled();
    expect(within(ana).getByRole("button", { name: "Salir" })).toBeDisabled();
    expect(within(ana).getByText(/La casa necesita al menos un admin/)).toBeInTheDocument();

    const tomas = screen.getByText("Tomás").closest("li")!;
    expect(within(tomas).getByLabelText("Rol de Tomás")).toBeEnabled();
  });

  it("quitar a alguien pide confirmación", async () => {
    montar();
    const tomas = (await screen.findByText("Tomás")).closest("li")!;
    fireEvent.click(within(tomas).getByRole("button", { name: "Quitar" }));
    const dialogo = await screen.findByRole("dialog", { name: "¿Quitar a Tomás de la casa?" });
    expect(quitados).toEqual([]);
    fireEvent.click(within(dialogo).getByRole("button", { name: "Quitar de la casa" }));
    await waitFor(() => expect(quitados).toEqual([2]));
    // El aviso llega aunque su fila ya no esté
    expect(await screen.findByText("Tomás ya no es parte de la casa")).toBeInTheDocument();
    expect(screen.queryByText("Tomás")).not.toBeInTheDocument();
  });

  it("«Cancelar» cierra la confirmación sin quitar a nadie", async () => {
    montar();
    const tomas = (await screen.findByText("Tomás")).closest("li")!;
    fireEvent.click(within(tomas).getByRole("button", { name: "Quitar" }));
    const dialogo = await screen.findByRole("dialog", { name: "¿Quitar a Tomás de la casa?" });
    fireEvent.click(within(dialogo).getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(quitados).toEqual([]);
    expect(screen.getByText("Tomás")).toBeInTheDocument();
  });

  it("anular el enlace recién creado lo quita también de arriba", async () => {
    montar();
    fireEvent.click(await screen.findByRole("button", { name: "Crear enlace" }));
    await screen.findByLabelText("Enlace de invitación");
    const lista = await screen.findByRole("region", { name: "Enlaces sin usar" });
    fireEvent.click(within(lista).getByRole("button", { name: "Anular" }));
    expect(await screen.findByText("Enlace anulado: ya no sirve")).toBeInTheDocument();
    // Ya no se ofrece para copiar un enlace que no sirve: vuelve el formulario
    expect(screen.queryByLabelText("Enlace de invitación")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear enlace" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Enlaces sin usar")).not.toBeInTheDocument());
  });

  it("cambiar el rol lo confirma con un aviso", async () => {
    montar();
    const tomas = (await screen.findByText("Tomás")).closest("li")!;
    fireEvent.change(within(tomas).getByLabelText("Rol de Tomás"), {
      target: { value: "admin" },
    });
    expect(await screen.findByText("Tomás ahora es admin")).toBeInTheDocument();
    // Ya hay dos admins: Ana también puede cambiar su rol
    await waitFor(() => expect(screen.getByLabelText("Rol de Ana Lucía")).toBeEnabled());
  });

  it("invitar: crea el enlace y lo copia", async () => {
    const escribir = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: escribir },
      configurable: true,
    });
    montar();
    fireEvent.click(await screen.findByRole("radio", { name: /Admin/ }));
    fireEvent.change(screen.getByLabelText("Email (opcional)"), {
      target: { value: " camila@ejemplo.com " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear enlace" }));

    const campo = await screen.findByLabelText("Enlace de invitación");
    expect(campo).toHaveValue("http://localhost:3000/invitacion/abc123");
    expect(creadas).toEqual([{ rol: "admin", email: "camila@ejemplo.com" }]);
    expect(screen.getByText(/Sirve una sola vez y vence el/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Copiar enlace" }));
    await waitFor(() =>
      expect(escribir).toHaveBeenCalledWith("http://localhost:3000/invitacion/abc123"),
    );
    expect(await screen.findByText("Enlace copiado")).toBeInTheDocument();
  });
});
