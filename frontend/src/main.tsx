import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { Toaster } from "sonner";
import { cuandoSePierdaLaSesion, ErrorApi } from "./api/cliente";
import { claves } from "./api/consultas";
import { AvisoNuevaVersion } from "./componentes/AvisoNuevaVersion";
import "./estilos.css";
import "./lib/tema"; // retoma el tema de public/tema.js y sigue los cambios del sistema
import "./notificaciones/instalacion"; // escucha beforeinstallprompt desde el arranque
import { crearRouter } from "./rutas";

const cliente = new QueryClient({
  defaultOptions: {
    queries: {
      // Un 401, 403 o 404 no se arregla reintentando; un corte de red sí
      retry: (intentos, error) =>
        !(error instanceof ErrorApi && error.estado >= 400 && error.estado < 500) && intentos < 3,
    },
    mutations: { retry: false },
  },
});

// Cualquier 401 (sesión vencida o cerrada en otro lado): la guarda lleva a /login?volver= (§11.6)
cuandoSePierdaLaSesion(() => cliente.setQueryData(claves.yo, null));

const router = crearRouter();

const raiz = document.getElementById("root");
if (!raiz) throw new Error("Falta el elemento #root en index.html");

createRoot(raiz).render(
  <StrictMode>
    <QueryClientProvider client={cliente}>
      <RouterProvider router={router} />
      <Toaster
        position="top-center"
        offset={{ top: "calc(env(safe-area-inset-top) + 12px)" }}
        mobileOffset={{ top: "calc(env(safe-area-inset-top) + 8px)", left: "8px", right: "8px" }}
        toastOptions={{
          unstyled: true,
          classNames: {
            toast:
              "placa flex w-full items-start gap-3 rounded-[10px] px-4 py-3 text-tinta sm:w-[22rem]",
            title: "font-semibold leading-6",
            description: "text-sm text-tinta-2",
            icon: "mt-0.5 text-tinta-2",
            actionButton:
              "pulsable ml-auto h-11 shrink-0 self-center rounded-[6px] bg-tinta px-3 text-sm font-semibold text-cara",
            closeButton: "text-tinta-3",
          },
        }}
      />
      {import.meta.env.PROD && <AvisoNuevaVersion />}
    </QueryClientProvider>
  </StrictMode>,
);
