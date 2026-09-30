/**
 * Consultas de F6 (§8.2, §8.3, §8.5, §8.6): invitaciones, miembros, ajustes de la casa,
 * lecturas y resumen. Van aparte de consultas.ts para que no pesen en el chunk del tablero:
 * solo las usan vistas que cargan diferidas.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, llamar } from "./cliente";
import { claves as clavesBase } from "./consultas";
import type { components } from "./tipos.gen";

type Esquemas = components["schemas"];
export type MiembroCasa = Esquemas["MiembroCasa"];
export type Rol = MiembroCasa["rol"];
export type InvitacionVigente = Esquemas["InvitacionVigente"];
export type InvitacionCreada = Esquemas["InvitacionCreada"];
export type InvitacionPublica = Esquemas["InvitacionPublica"];
export type Casa = Esquemas["Casa"];
export type Ajustes = Esquemas["Ajustes"];
export type CambioAjustes = Esquemas["CambioAjustes"];
export type Punto = Esquemas["Punto"];
export type Resumen = Esquemas["Resumen"];
export type Metrica = "temperatura" | "gas" | "caudal";
export type Periodo = "24h" | "7d";

export const claves = {
  miembros: (casaId: number) => ["casa", casaId, "miembros"] as const,
  invitaciones: (casaId: number) => ["casa", casaId, "invitaciones"] as const,
  casa: (casaId: number) => ["casa", casaId, "datos"] as const,
  lecturas: (casaId: number, nodo: number, metrica: Metrica, periodo: Periodo) =>
    ["casa", casaId, "lecturas", nodo, metrica, periodo] as const,
  resumen: (casaId: number, dias: number) => ["casa", casaId, "resumen", dias] as const,
  invitacion: (token: string) => ["invitacion", token] as const,
};

// ------------------------------------------------------------------ miembros
export function useMiembros(casaId: number) {
  return useQuery({
    queryKey: claves.miembros(casaId),
    queryFn: () =>
      llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/miembros", { params: { path: { casa_id: casaId } } }),
      ),
  });
}

/** Tras cambiar un rol o quitar a alguien: la lista, y "yo" por si el cambio fue propio. */
function useAlCambiarMiembros(casaId: number) {
  const cliente = useQueryClient();
  return async () => {
    await cliente.invalidateQueries({ queryKey: claves.miembros(casaId) });
    await cliente.invalidateQueries({ queryKey: clavesBase.yo });
  };
}

export function useCambiarRol(casaId: number) {
  const alCambiar = useAlCambiarMiembros(casaId);
  return useMutation({
    mutationFn: ({ usuarioId, rol }: { usuarioId: number; rol: Rol }) =>
      llamar(() =>
        api.PATCH("/api/v1/casas/{casa_id}/miembros/{usuario_id}", {
          params: { path: { casa_id: casaId, usuario_id: usuarioId } },
          body: { rol },
        }),
      ),
    onSettled: alCambiar,
  });
}

export function useQuitarMiembro(casaId: number) {
  const alCambiar = useAlCambiarMiembros(casaId);
  return useMutation({
    mutationFn: (usuarioId: number) =>
      llamar(() =>
        api.DELETE("/api/v1/casas/{casa_id}/miembros/{usuario_id}", {
          params: { path: { casa_id: casaId, usuario_id: usuarioId } },
        }),
      ),
    onSettled: alCambiar,
  });
}

// ------------------------------------------------------------------ invitaciones (admin)
export function useInvitaciones(casaId: number) {
  return useQuery({
    queryKey: claves.invitaciones(casaId),
    queryFn: () =>
      llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/invitaciones", {
          params: { path: { casa_id: casaId } },
        }),
      ),
  });
}

export function useCrearInvitacion(casaId: number) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (datos: { rol: Rol; email?: string }) =>
      llamar(() =>
        api.POST("/api/v1/casas/{casa_id}/invitaciones", {
          params: { path: { casa_id: casaId } },
          body: datos,
        }),
      ),
    onSettled: () => cliente.invalidateQueries({ queryKey: claves.invitaciones(casaId) }),
  });
}

export function useAnularInvitacion(casaId: number) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (invitacionId: number) =>
      llamar(() =>
        api.DELETE("/api/v1/casas/{casa_id}/invitaciones/{invitacion_id}", {
          params: { path: { casa_id: casaId, invitacion_id: invitacionId } },
        }),
      ),
    onSettled: () => cliente.invalidateQueries({ queryKey: claves.invitaciones(casaId) }),
  });
}

// ------------------------------------------------------------------ invitación (quien la abre)
export function useInvitacionPublica(token: string) {
  return useQuery({
    queryKey: claves.invitacion(token),
    queryFn: () =>
      llamar(() => api.GET("/api/v1/invitaciones/{token}", { params: { path: { token } } })),
    retry: false,
    staleTime: Infinity,
  });
}

export function useAceptarInvitacion(token: string) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (datos: { nombre?: string; email?: string; clave?: string }) =>
      llamar(() =>
        api.POST("/api/v1/invitaciones/{token}/aceptar", {
          params: { path: { token } },
          body: datos,
        }),
      ),
    // La cookie ya llegó: "yo" trae la casa nueva y las guardas dejan pasar
    onSuccess: async () => {
      await cliente.invalidateQueries({ queryKey: clavesBase.yo });
      await cliente.invalidateQueries({ queryKey: clavesBase.casas });
    },
  });
}

// ------------------------------------------------------------------ la casa y sus ajustes
export function useCasa(casaId: number) {
  return useQuery({
    queryKey: claves.casa(casaId),
    queryFn: () =>
      llamar(() => api.GET("/api/v1/casas/{casa_id}", { params: { path: { casa_id: casaId } } })),
  });
}

export function useGuardarCasa(casaId: number) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: async ({ nombre, ajustes }: { nombre?: string; ajustes: CambioAjustes }) => {
      if (nombre !== undefined) {
        await llamar(() =>
          api.PATCH("/api/v1/casas/{casa_id}", {
            params: { path: { casa_id: casaId } },
            body: { nombre },
          }),
        );
      }
      if (Object.keys(ajustes).length > 0) {
        await llamar(() =>
          api.PATCH("/api/v1/casas/{casa_id}/ajustes", {
            params: { path: { casa_id: casaId } },
            body: ajustes,
          }),
        );
      }
    },
    onSettled: async () => {
      await cliente.invalidateQueries({ queryKey: claves.casa(casaId) });
      await cliente.invalidateQueries({ queryKey: clavesBase.casas }); // el nombre, arriba
      await cliente.invalidateQueries({ queryKey: clavesBase.yo });
    },
  });
}

// ------------------------------------------------------------------ gráficas
const PERIODOS: Record<Periodo, { ms: number; agregacion: "5m" | "1h" }> = {
  "24h": { ms: 24 * 3600_000, agregacion: "5m" }, // 288 puntos
  "7d": { ms: 7 * 24 * 3600_000, agregacion: "1h" }, // 168 puntos
};

export function useLecturas(casaId: number, nodo: number, metrica: Metrica, periodo: Periodo) {
  return useQuery({
    queryKey: claves.lecturas(casaId, nodo, metrica, periodo),
    queryFn: () => {
      const hasta = new Date();
      const desde = new Date(hasta.getTime() - PERIODOS[periodo].ms);
      return llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/lecturas", {
          params: {
            path: { casa_id: casaId },
            query: {
              nodo,
              metrica,
              desde: desde.toISOString(),
              hasta: hasta.toISOString(),
              agregacion: PERIODOS[periodo].agregacion,
            },
          },
        }),
      );
    },
    refetchInterval: 60_000, // §11.3
    placeholderData: keepPreviousData, // al cambiar de periodo, la gráfica anterior queda
  });
}

export function useResumen(casaId: number, dias: number) {
  return useQuery({
    queryKey: claves.resumen(casaId, dias),
    queryFn: () =>
      llamar(() =>
        api.GET("/api/v1/casas/{casa_id}/resumen", {
          params: { path: { casa_id: casaId }, query: { dias } },
        }),
      ),
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}
