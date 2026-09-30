/** Datos del servidor con TanStack Query (§11.3). El WebSocket escribe en esta misma caché. */
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { estadoPush } from "../notificaciones/webpush";
import type { components } from "./tipos.gen";
import { api, ErrorApi, llamar } from "./cliente";

type Esquemas = components["schemas"];
export type Yo = Esquemas["Yo"];
export type Usuario = Esquemas["Usuario"];
export type ResumenCasa = Esquemas["ResumenCasa"];
export type EstadoCasa = Esquemas["EstadoCasa"];
export type Comando = Esquemas["Comando"];
export type Preferencias = Esquemas["Preferencias"];
export type SesionAbierta = Esquemas["SesionAbierta"];
export type TipoAlarma = Esquemas["Alarma"]["tipo"];

export const claves = {
  yo: ["yo"] as const,
  casas: ["casas"] as const,
  estado: (casaId: number) => ["casa", casaId, "estado"] as const,
  alarmas: (casaId: number) => ["casa", casaId, "alarmas"] as const,
  eventos: (casaId: number) => ["casa", casaId, "eventos"] as const,
  comando: (id: number) => ["comando", id] as const,
  preferencias: ["preferencias"] as const,
  sesiones: ["sesiones"] as const,
  pushDispositivo: ["push-dispositivo"] as const,
};

// ------------------------------------------------------------------ sesión
/** El usuario de la sesión, o null si no hay sesión (no es un error: lleva al login). */
export function useYo() {
  return useQuery({
    queryKey: claves.yo,
    queryFn: async (): Promise<Yo | null> => {
      try {
        return await llamar(() => api.GET("/api/v1/auth/yo"));
      } catch (error) {
        if (error instanceof ErrorApi && error.estado === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function useEntrar() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (credenciales: { email: string; clave: string }) =>
      llamar(() => api.POST("/api/v1/auth/login", { body: credenciales })),
    onSuccess: () => cliente.invalidateQueries({ queryKey: claves.yo }),
  });
}

export function useSalir() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: () => llamar(() => api.POST("/api/v1/auth/logout")),
    onSettled: () => {
      // Primero la sesión en null: la guarda la ve y lleva al login. Después se borran los datos
      // de la cuenta. Con clear() antes, la guarda se quedaba mirando una consulta ya borrada.
      cliente.setQueryData(claves.yo, null);
      cliente.removeQueries({ predicate: (consulta) => consulta.queryKey[0] !== claves.yo[0] });
    },
  });
}

export function useCambiarClave() {
  return useMutation({
    mutationFn: (datos: { clave_actual: string; clave_nueva: string }) =>
      llamar(() => api.POST("/api/v1/auth/cambiar-clave", { body: datos })),
  });
}

export function useSesiones() {
  return useQuery({
    queryKey: claves.sesiones,
    queryFn: () => llamar(() => api.GET("/api/v1/auth/sesiones")),
  });
}

export function useCerrarSesion() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (sesionId: number) =>
      llamar(() =>
        api.DELETE("/api/v1/auth/sesiones/{sesion_id}", {
          params: { path: { sesion_id: sesionId } },
        }),
      ),
    onSettled: () => cliente.invalidateQueries({ queryKey: claves.sesiones }),
  });
}

/** Cierra varias sesiones de una vez (las de otros dispositivos). */
export function useCerrarOtrasSesiones() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: async (ids: number[]) => {
      for (const id of ids) {
        await llamar(() =>
          api.DELETE("/api/v1/auth/sesiones/{sesion_id}", { params: { path: { sesion_id: id } } }),
        );
      }
    },
    onSettled: () => cliente.invalidateQueries({ queryKey: claves.sesiones }),
  });
}

// ------------------------------------------------------------------ casas y estado
export function useCasas() {
  return useQuery({
    queryKey: claves.casas,
    queryFn: () => llamar(() => api.GET("/api/v1/casas")),
  });
}

/** El estado en vivo. `respaldo` activa el sondeo cada 5 s cuando el WebSocket falla (§9). */
export function useEstadoCasa(casaId: number | null, respaldo = false) {
  return useQuery({
    queryKey: claves.estado(casaId ?? 0),
    queryFn: () =>
      llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/estado", {
          params: { path: { casa_id: casaId ?? 0 } },
        }),
      ),
    enabled: casaId !== null,
    refetchInterval: respaldo ? 5000 : false,
    // Al sondear, el sondeo mismo es el reintento: un fallo se muestra ya ("Sin conexión")
    retry: respaldo ? false : undefined,
    staleTime: Infinity, // el WebSocket la mantiene al día
  });
}

// ------------------------------------------------------------------ historial
export interface FiltrosAlarmas {
  abiertas?: boolean;
  nodo?: number;
}

export function useAlarmas(casaId: number, filtros: FiltrosAlarmas) {
  return useInfiniteQuery({
    queryKey: [...claves.alarmas(casaId), filtros],
    queryFn: ({ pageParam }) =>
      llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/alarmas", {
          params: {
            path: { casa_id: casaId },
            query: { ...filtros, limit: 30, antes_de_id: pageParam ?? undefined },
          },
        }),
      ),
    initialPageParam: null as number | null,
    getNextPageParam: (pagina) => pagina.siguiente,
  });
}

export function useEventos(casaId: number, soloAlarmas: boolean) {
  return useInfiniteQuery({
    queryKey: [...claves.eventos(casaId), soloAlarmas],
    queryFn: ({ pageParam }) =>
      llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/eventos", {
          params: {
            path: { casa_id: casaId },
            query: { solo_alarmas: soloAlarmas, limit: 50, antes_de_id: pageParam ?? undefined },
          },
        }),
      ),
    initialPageParam: null as number | null,
    getNextPageParam: (pagina) => pagina.siguiente,
  });
}

// ------------------------------------------------------------------ comandos
export interface NuevoComando {
  nodo: number;
  accion: "activar" | "desactivar" | "silenciar";
  sub?: 0 | 1;
}

/** POST /comandos: responde 202 con el comando "pendiente"; lo resuelve la central (§8.4). */
export function pedirComando(casaId: number, comando: NuevoComando): Promise<Comando> {
  return llamar(() =>
    api.POST("/api/v1/casas/{casa_id}/comandos", {
      params: { path: { casa_id: casaId } },
      body: { sub: 0, ...comando },
    }),
  );
}

export function pedirSilenciarTodo(casaId: number): Promise<Comando> {
  return llamar(() =>
    api.POST("/api/v1/casas/{casa_id}/comandos/silenciar-todo", {
      params: { path: { casa_id: casaId } },
    }),
  );
}

export function guardarComando(cliente: QueryClient, comando: Comando): void {
  cliente.setQueryData(claves.comando(comando.id), comando);
}

/**
 * Sigue un comando hasta que la central lo confirma o vence (8 s). El WebSocket lo actualiza
 * al instante; si el WebSocket no está, se consulta cada 2 s.
 */
export function useComando(casaId: number, comandoId: number | null) {
  return useQuery({
    queryKey: claves.comando(comandoId ?? 0),
    queryFn: () =>
      llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/comandos/{comando_id}", {
          params: { path: { casa_id: casaId, comando_id: comandoId ?? 0 } },
        }),
      ),
    enabled: comandoId !== null,
    refetchInterval: (consulta) => (consulta.state.data?.estado === "pendiente" ? 2000 : false),
    staleTime: Infinity,
  });
}

// ------------------------------------------------------------------ notificaciones
export function usePreferencias() {
  return useQuery({
    queryKey: claves.preferencias,
    queryFn: () => llamar(() => api.GET("/api/v1/notificaciones/preferencias")),
  });
}

/** Si este dispositivo tiene Web Push (lo sabe el navegador, no la API). */
export function useEstadoPush() {
  return useQuery({
    queryKey: claves.pushDispositivo,
    queryFn: estadoPush,
    staleTime: 30_000,
  });
}

export function useCambiarPreferencias() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (cambio: { webpush?: boolean }) =>
      llamar(() => api.PATCH("/api/v1/notificaciones/preferencias", { body: cambio })),
    onSuccess: (preferencias) => cliente.setQueryData(claves.preferencias, preferencias),
  });
}
