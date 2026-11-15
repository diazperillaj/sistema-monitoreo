/**
 * Cliente HTTP tipado desde el OpenAPI de la API (§11.3): misma sesión (cookie), errores de la
 * API como ErrorApi {codigo, mensaje}, y un 401 lleva a iniciar sesión.
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./tipos.gen";

export class ErrorApi extends Error {
  readonly estado: number;
  readonly codigo: string;

  constructor(estado: number, codigo: string, mensaje: string) {
    super(mensaje);
    this.name = "ErrorApi";
    this.estado = estado;
    this.codigo = codigo;
  }
}

const MENSAJES: Record<number, string> = {
  0: "No hay conexión con el servidor. Revisa el internet del celular.",
  401: "Tu sesión terminó. Vuelve a entrar.",
  403: "No tienes permiso para hacer esto.",
  404: "No se encontró lo que buscabas.",
  429: "Demasiados intentos. Espera un momento y vuelve a probar.",
  503: "El servidor no está disponible en este momento.",
};

/** Quien arranca la app decide qué hacer con un 401 (ir al login con ?volver=). */
let alPerderSesion: (() => void) | null = null;
export function cuandoSePierdaLaSesion(accion: () => void): void {
  alPerderSesion = accion;
}

const sesion: Middleware = {
  onResponse({ request, response }) {
    const esLogin = request.url.endsWith("/api/v1/auth/login");
    const esYo = request.url.endsWith("/api/v1/auth/yo");
    if (response.status === 401 && !esLogin && !esYo) alPerderSesion?.();
    return response;
  },
};

export const api = createClient<paths>({
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  credentials: "same-origin",
  // El fetch del momento, no el de cuando cargó el módulo (en las pruebas, MSW lo reemplaza)
  fetch: (peticion) => globalThis.fetch(peticion),
});
api.use(sesion);

interface Resultado<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Los datos de una respuesta correcta, o un ErrorApi con el mensaje de la API. */
export function datos<T>({ data, error, response }: Resultado<T>): T {
  if (response.ok) return data as T;
  const detalle = (error as { detail?: { codigo?: string; mensaje?: string } } | undefined)?.detail;
  throw new ErrorApi(
    response.status,
    detalle?.codigo ?? "error",
    detalle?.mensaje ?? MENSAJES[response.status] ?? "Algo salió mal. Vuelve a intentarlo.",
  );
}

/** Ejecuta una llamada y convierte un fallo de red en ErrorApi. */
export async function llamar<T>(peticion: () => Promise<Resultado<T>>): Promise<T> {
  let resultado: Resultado<T>;
  try {
    resultado = await peticion();
  } catch {
    throw new ErrorApi(0, "sin_conexion", MENSAJES[0]);
  }
  return datos(resultado);
}

export function mensajeDe(error: unknown): string {
  return error instanceof ErrorApi ? error.message : "Algo salió mal. Vuelve a intentarlo.";
}
