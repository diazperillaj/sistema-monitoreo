/**
 * El interruptor de §13.5: clic → "enviando…" → el WebSocket dice confirmado (se queda) o
 * sin_confirmar (vuelve y avisa). Un 409 muestra el mensaje de la API.
 */
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEstadoCasa } from "../api/consultas";
import { HAB } from "../dominio/protocolo";
import { comando, estadoCasa, nodo, type Nodo } from "../test/datos";
import { renderizar } from "../test/renderizar";
import { API, errorApi, servidor } from "../test/servidor";
import { WsFalso } from "../test/wsFalso";
import { useCasaEnVivo } from "../tiempo-real/useCasaEnVivo";
import { InterruptorNodo } from "./InterruptorNodo";

function Arnes() {
  useCasaEnVivo(1);
  const estado = useEstadoCasa(1).data;
  const bano = estado?.central?.nodos[2];
  if (!bano) return <p>Cargando</p>;
  return (
    <InterruptorNodo
      casaId={1}
      nodo={2}
      interruptor={{ sub: 0, etiqueta: "Vigilancia del baño", activo: bano.hab === HAB.PRINCIPAL }}
    />
  );
}

const conBano = (cambios: Partial<Nodo>) =>
  estadoCasa({
    central: {
      ...estadoCasa().central!,
      nodos: [0, 1, 2, 3, 4].map((id) => nodo(id, id === 2 ? cambios : {})),
    },
  });

let pedidos: unknown[];

beforeEach(() => {
  WsFalso.reiniciar();
  vi.stubGlobal("WebSocket", WsFalso);
  pedidos = [];
  servidor.use(
    http.get(`${API}/casas/1/estado`, () => HttpResponse.json(conBano({}))),
    http.post(`${API}/casas/1/comandos`, async ({ request }) => {
      pedidos.push(await request.json());
      return HttpResponse.json(comando(), { status: 202 });
    }),
    http.get(`${API}/casas/1/comandos/41`, () => HttpResponse.json(comando())),
  );
});

afterEach(() => vi.unstubAllGlobals());

async function montar() {
  renderizar(<Arnes />);
  const palanca = await screen.findByRole("switch", { name: "Vigilancia del baño" });
  act(() => WsFalso.ultima().abrir());
  return palanca;
}

describe("InterruptorNodo", () => {
  it("confirmado: pasa por 'Enviando…' y se queda en el valor nuevo", async () => {
    const palanca = await montar();
    expect(palanca).toBeChecked();

    fireEvent.click(palanca);
    expect(await screen.findByText("Enviando…")).toBeInTheDocument();
    expect(palanca).toHaveAttribute("aria-busy", "true");
    expect(pedidos).toEqual([{ nodo: 2, accion: "desactivar", sub: 0 }]);

    // La central aplica el cambio: llega la confirmación y luego el estado nuevo (§9)
    act(() => {
      WsFalso.ultima().recibir({ tipo: "comando", data: comando({ estado: "confirmado" }) });
      WsFalso.ultima().recibir({ tipo: "estado", data: conBano({ hab: 0 }) });
    });
    await waitFor(() => expect(palanca).not.toHaveAttribute("aria-busy"));
    expect(palanca).not.toBeChecked();
    expect(screen.queryByText("Enviando…")).not.toBeInTheDocument();
  });

  it("sin confirmar: vuelve al valor de antes y avisa", async () => {
    const palanca = await montar();
    fireEvent.click(palanca);
    await screen.findByText("Enviando…");

    act(() =>
      WsFalso.ultima().recibir({ tipo: "comando", data: comando({ estado: "sin_confirmar" }) }),
    );
    expect(await screen.findByText("La central no confirmó el cambio")).toBeInTheDocument();
    await waitFor(() => expect(palanca).not.toHaveAttribute("aria-busy"));
    expect(palanca).toBeChecked();
  });

  it("un 409 muestra el mensaje de la API y no queda enviando", async () => {
    servidor.use(
      http.post(`${API}/casas/1/comandos`, () =>
        errorApi(409, "nodo_sin_conexion", "El baño no está conectado a la central."),
      ),
    );
    const palanca = await montar();
    fireEvent.click(palanca);
    expect(await screen.findByText("El baño no está conectado a la central.")).toBeInTheDocument();
    expect(palanca).toBeChecked();
    expect(palanca).not.toHaveAttribute("aria-busy");
  });
});
