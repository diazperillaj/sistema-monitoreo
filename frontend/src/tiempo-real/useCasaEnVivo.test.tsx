/**
 * useCasaEnVivo (§13.5): un mensaje "estado" actualiza la caché; si el WebSocket se cae, pasa a
 * consultar cada 5 s y vuelve a "en vivo" al reconectar.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { claves, useEstadoCasa } from "../api/consultas";
import { estadoCasa } from "../test/datos";
import { clienteDePrueba, conProveedores } from "../test/renderizar";
import { API, servidor } from "../test/servidor";
import { WsFalso } from "../test/wsFalso";
import { useCasaEnVivo } from "./useCasaEnVivo";

let consultas = 0;

beforeEach(() => {
  WsFalso.reiniciar();
  vi.stubGlobal("WebSocket", WsFalso);
  consultas = 0;
  servidor.use(
    http.get(`${API}/casas/1/estado`, () => {
      consultas += 1;
      return HttpResponse.json(estadoCasa());
    }),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function montar() {
  const cliente = clienteDePrueba();
  const resultado = renderHook(
    () => {
      const conexion = useCasaEnVivo(1);
      useEstadoCasa(1, conexion === "respaldo");
      return conexion;
    },
    { wrapper: ({ children }) => conProveedores(children, cliente) },
  );
  return { cliente, ...resultado };
}

describe("useCasaEnVivo", () => {
  it("abre el WebSocket de la casa en el mismo origen", () => {
    montar();
    expect(WsFalso.ultima().url).toBe("ws://localhost:3000/ws/v1/casas/1");
  });

  it("un mensaje 'estado' reemplaza el estado en la caché", async () => {
    const { cliente, result } = montar();
    act(() => WsFalso.ultima().abrir());
    expect(result.current).toBe("en_vivo");

    const nuevo = estadoCasa({ antiguedad_s: 0, online: false });
    act(() => WsFalso.ultima().recibir({ tipo: "estado", data: nuevo }));
    expect(cliente.getQueryData(claves.estado(1))).toEqual(nuevo);
  });

  it("'central' solo cambia la conexión de la central", async () => {
    const { cliente } = montar();
    await waitFor(() => expect(cliente.getQueryData(claves.estado(1))).toBeDefined());
    act(() =>
      WsFalso.ultima().recibir({
        tipo: "central",
        online: false,
        cambio_en: "2026-09-29T20:00:00Z",
      }),
    );
    expect(cliente.getQueryData(claves.estado(1))).toMatchObject({
      online: false,
      online_cambio_en: "2026-09-29T20:00:00Z",
    });
  });

  it("tras 3 fallos seguidos consulta cada 5 s, y vuelve a 'en vivo' al reconectar", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { result } = montar();
    act(() => WsFalso.ultima().abrir());
    await waitFor(() => expect(consultas).toBe(1)); // la carga inicial

    act(() => WsFalso.ultima().cortar());
    expect(result.current).toBe("reconectando");
    await act(() => vi.advanceTimersByTimeAsync(1000)); // reintento a 1 s
    act(() => WsFalso.ultima().cortar());
    await act(() => vi.advanceTimersByTimeAsync(2000)); // a 2 s
    act(() => WsFalso.ultima().cortar());
    expect(result.current).toBe("respaldo");

    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(consultas).toBeGreaterThanOrEqual(2); // ya consulta por HTTP

    await act(() => vi.advanceTimersByTimeAsync(5000)); // reintento a 5 s
    act(() => WsFalso.ultima().abrir());
    expect(result.current).toBe("en_vivo");
    const antes = consultas;
    await act(() => vi.advanceTimersByTimeAsync(11_000));
    expect(consultas).toBe(antes); // con el WebSocket de vuelta, deja de consultar
  });

  it("4401 lleva al login: la sesión queda en null", () => {
    const { cliente } = montar();
    act(() => WsFalso.ultima().cortar(4401));
    expect(cliente.getQueryData(claves.yo)).toBeNull();
  });

  it("4403 corta sin reintentar", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { result } = montar();
    act(() => WsFalso.ultima().cortar(4403));
    expect(result.current).toBe("sin_acceso");
    await act(() => vi.advanceTimersByTimeAsync(40_000));
    expect(WsFalso.instancias).toHaveLength(1);
  });
});
