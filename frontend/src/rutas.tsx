/**
 * Tabla de rutas y guardas (§11.2). El tablero carga de una; lo demás, cuando se abre
 * (React.lazy), para que el tablero pese poco. La invitación también va diferida: se abre una
 * sola vez por persona.
 */
import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate, Outlet, useLocation, useParams } from "react-router";
import { mensajeDe } from "./api/cliente";
import { useYo } from "./api/consultas";
import { Layout } from "./componentes/Layout";
import { Boton } from "./componentes/ui/Boton";
import { esMiembro } from "./tiempo-real/casaActual";
import Casas from "./vistas/Casas";
import NoEncontrado from "./vistas/NoEncontrado";
import Tablero from "./vistas/Tablero";

const Login = lazy(() => import("./vistas/Login"));
const Historial = lazy(() => import("./vistas/Historial"));
const Perfil = lazy(() => import("./vistas/Perfil"));
const Invitacion = lazy(() => import("./vistas/Invitacion"));
const Graficas = lazy(() => import("./vistas/Graficas"));
const Ajustes = lazy(() => import("./vistas/Ajustes"));
const Miembros = lazy(() => import("./vistas/Miembros"));

function Diferida({ children }: { children: ReactNode }) {
  return <Suspense fallback={<CargandoVista />}>{children}</Suspense>;
}

function Arrancando() {
  return (
    <div aria-busy="true" className="grid min-h-dvh place-items-center text-tinta-3">
      Cargando…
    </div>
  );
}

function CargandoVista() {
  return <p className="py-8 text-center text-tinta-3">Cargando…</p>;
}

/** Sin sesión, al login con ?volver= para regresar a donde iba. */
export function RequiereSesion() {
  const yo = useYo();
  const lugar = useLocation();
  if (yo.isPending) return <Arrancando />;
  if (yo.isError) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-3 px-4">
        <h1 className="text-xl font-semibold">No se pudo conectar</h1>
        <p className="text-tinta-2">{mensajeDe(yo.error)}</p>
        <Boton
          className="w-fit"
          ocupado={yo.isFetching && "Reintentando…"}
          onClick={() => void yo.refetch()}
        >
          Reintentar
        </Boton>
      </main>
    );
  }
  if (!yo.data) {
    const volver = encodeURIComponent(lugar.pathname + lugar.search);
    return <Navigate to={`/login?volver=${volver}`} replace />;
  }
  return <Outlet />;
}

/** Una casa que no es suya lleva al inicio (el backend igual lo rechazaría, §12.5). */
export function RequiereMiembro() {
  const yo = useYo().data;
  const { casaId } = useParams();
  const id = Number(casaId);
  if (!yo || !Number.isInteger(id) || id <= 0 || !esMiembro(yo, id)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

/** Solo admin de la casa (o superadmin); si no, al tablero. Lo usan Miembros y Ajustes (F6). */
export function RequiereAdmin() {
  const yo = useYo().data;
  const { casaId } = useParams();
  const id = Number(casaId);
  const admin =
    yo?.usuario.es_superadmin || yo?.casas.some((c) => c.id === id && c.rol === "admin");
  if (!admin) return <Navigate to={`/casa/${casaId}`} replace />;
  return <Outlet />;
}

export const rutas = [
  {
    path: "/login",
    element: (
      <Suspense fallback={<Arrancando />}>
        <Login />
      </Suspense>
    ),
  },
  {
    path: "/invitacion/:token",
    element: (
      <Suspense fallback={<Arrancando />}>
        <Invitacion />
      </Suspense>
    ),
  },
  {
    element: <RequiereSesion />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: "/", element: <Casas /> },
          {
            path: "/casa/:casaId",
            element: <RequiereMiembro />,
            children: [
              { index: true, element: <Tablero /> },
              {
                path: "historial",
                element: (
                  <Diferida>
                    <Historial />
                  </Diferida>
                ),
              },
              {
                path: "graficas",
                element: (
                  <Diferida>
                    <Graficas />
                  </Diferida>
                ),
              },
              {
                element: <RequiereAdmin />,
                children: [
                  {
                    path: "ajustes",
                    element: (
                      <Diferida>
                        <Ajustes />
                      </Diferida>
                    ),
                  },
                  {
                    path: "miembros",
                    element: (
                      <Diferida>
                        <Miembros />
                      </Diferida>
                    ),
                  },
                ],
              },
            ],
          },
          {
            path: "/perfil",
            element: (
              <Diferida>
                <Perfil />
              </Diferida>
            ),
          },
        ],
      },
    ],
  },
  { path: "*", element: <NoEncontrado /> },
];

export function crearRouter() {
  return createBrowserRouter(rutas);
}
