/** Renderizar con lo que la app pone alrededor: TanStack Query, el router y los avisos. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router";
import { Toaster } from "sonner";
import { ContextoCasa } from "../tiempo-real/casaActual";

export function clienteDePrueba(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

export function conProveedores(hijos: ReactNode, cliente = clienteDePrueba()) {
  return (
    <QueryClientProvider client={cliente}>
      {hijos}
      <Toaster />
    </QueryClientProvider>
  );
}

export function renderizar(hijos: ReactNode, cliente = clienteDePrueba()) {
  return { cliente, ...render(conProveedores(hijos, cliente)) };
}

export function renderizarRutas(rutas: RouteObject[], inicio: string, cliente = clienteDePrueba()) {
  const router = createMemoryRouter(rutas, { initialEntries: [inicio] });
  return {
    cliente,
    router,
    ...render(conProveedores(<RouterProvider router={router} />, cliente)),
  };
}

/** Para las vistas que viven dentro del Layout: la casa 1, en vivo y sin sonido. */
export function enLaCasa(hijos: ReactNode, casaId = 1) {
  const sonido = {
    soportada: false,
    activa: false,
    activar: () => {},
    apagar: () => {},
    avisar: () => {},
  };
  return <ContextoCasa value={{ casaId, conexion: "en_vivo", sonido }}>{hijos}</ContextoCasa>;
}
