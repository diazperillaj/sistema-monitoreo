/** La API simulada con MSW, tipada con los esquemas generados del OpenAPI. */
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { components } from "../api/tipos.gen";

type Esquemas = components["schemas"];

export const API = "http://localhost:3000/api/v1";

export const yoAdmin: Esquemas["Yo"] = {
  usuario: { id: 1, email: "ana@ejemplo.com", nombre: "Ana Lucía", es_superadmin: false },
  casas: [{ id: 1, nombre: "Casa de la abuela", rol: "admin" }],
};

export const yoCuidador: Esquemas["Yo"] = {
  usuario: { id: 2, email: "tomas@ejemplo.com", nombre: "Tomás", es_superadmin: false },
  casas: [{ id: 1, nombre: "Casa de la abuela", rol: "cuidador" }],
};

export const preferenciasBase: Esquemas["Preferencias"] = {
  webpush: { activo: true, dispositivos: 1 },
  telegram: {
    disponible: false,
    bot: null,
    vinculado: false,
    cuenta: null,
    vinculado_en: null,
    activo: false,
  },
};

/** Respuestas que casi toda prueba necesita; cada una cambia las suyas con servidor.use(). */
export const servidor = setupServer(
  http.get(`${API}/auth/yo`, () => HttpResponse.json(yoAdmin)),
  http.get(`${API}/casas`, () =>
    HttpResponse.json([
      {
        id: 1,
        codigo: "casa-abuela",
        nombre: "Casa de la abuela",
        rol: "admin",
        online: true,
        alarmas_abiertas: 0,
      },
    ]),
  ),
  http.get(`${API}/notificaciones/preferencias`, () => HttpResponse.json(preferenciasBase)),
);

export function errorApi(estado: number, codigo: string, mensaje: string) {
  return HttpResponse.json({ detail: { codigo, mensaje } }, { status: estado });
}
