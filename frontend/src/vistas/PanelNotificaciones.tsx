/**
 * Panel mínimo de F4 para probar Web Push: entrar, activar en este dispositivo y enviar una
 * prueba. En F5 lo reemplazan el login y la sección Notificaciones del perfil (§11.4).
 */
import { useEffect, useState, type FormEvent } from "react";
import type { components } from "../api/tipos.gen";
import * as push from "../push/dispositivo";

type Usuario = components["schemas"]["Usuario"];
type Yo = components["schemas"]["Yo"];

const boton =
  "rounded-lg px-4 py-2 font-medium disabled:opacity-50 bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900";
const campo =
  "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900";

const TEXTOS: Record<push.EstadoPush, string> = {
  no_soportado: "Este navegador no permite notificaciones push.",
  bloqueado:
    "Las notificaciones están bloqueadas para este sitio en la configuración del navegador.",
  inactivo: "Este dispositivo todavía no recibe notificaciones.",
  activo: "Este dispositivo recibe las notificaciones.",
};

function Entrar({ alEntrar }: { alEntrar: (usuario: Usuario) => void }) {
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function entrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const datos = new FormData(evento.currentTarget);
    setEnviando(true);
    setError(null);
    const respuesta = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: datos.get("email"), clave: datos.get("clave") }),
    }).catch(() => null);
    setEnviando(false);
    if (respuesta?.ok) {
      alEntrar((await respuesta.json()) as Usuario);
    } else {
      setError(respuesta ? "Email o clave incorrectos." : "No hay conexión con el servidor.");
    }
  }

  return (
    <form onSubmit={entrar} className="mt-4 space-y-3">
      <label className="block">
        Email
        <input name="email" type="email" autoComplete="username" required className={campo} />
      </label>
      <label className="block">
        Clave
        <input
          name="clave"
          type="password"
          autoComplete="current-password"
          required
          className={campo}
        />
      </label>
      {error && (
        <p role="alert" className="text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <button type="submit" disabled={enviando} className={boton}>
        Entrar
      </button>
    </form>
  );
}

export default function PanelNotificaciones() {
  const [usuario, setUsuario] = useState<Usuario | null | undefined>(undefined); // undefined: cargando
  const [estado, setEstado] = useState<push.EstadoPush | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    fetch("/api/v1/auth/yo")
      .then(async (r) => setUsuario(r.ok ? ((await r.json()) as Yo).usuario : null))
      .catch(() => setUsuario(null));
  }, []);

  useEffect(() => {
    if (usuario) void push.estado().then(setEstado);
  }, [usuario]);

  async function hacer(accion: () => Promise<string>) {
    setOcupado(true);
    setMensaje(null);
    try {
      setMensaje(await accion());
    } catch (error) {
      setMensaje(error instanceof Error ? error.message : "Algo salió mal.");
    } finally {
      setEstado(await push.estado());
      setOcupado(false);
    }
  }

  if (usuario === undefined) return <p className="mt-6 text-slate-500">Cargando…</p>;

  return (
    <section className="mt-8 rounded-xl border border-slate-200 p-4 dark:border-slate-800">
      <h2 className="text-lg font-semibold">Notificaciones (prueba)</h2>
      {usuario === null ? (
        <Entrar alEntrar={setUsuario} />
      ) : (
        <div className="mt-2 space-y-3">
          <p>Hola, {usuario.nombre}.</p>
          {estado && <p className="text-slate-600 dark:text-slate-400">{TEXTOS[estado]}</p>}
          {(estado === "inactivo" || estado === "activo") && (
            <div className="flex flex-wrap gap-2">
              {estado === "inactivo" ? (
                <button
                  className={boton}
                  disabled={ocupado}
                  onClick={() =>
                    void hacer(async () => {
                      await push.activar();
                      return "Listo: este dispositivo quedó suscrito.";
                    })
                  }
                >
                  Activar notificaciones en este dispositivo
                </button>
              ) : (
                <>
                  <button
                    className={boton}
                    disabled={ocupado}
                    onClick={() =>
                      void hacer(async () => {
                        const dispositivos = await push.probar();
                        return `Prueba enviada a ${dispositivos} dispositivo(s).`;
                      })
                    }
                  >
                    Enviar notificación de prueba
                  </button>
                  <button
                    className={boton}
                    disabled={ocupado}
                    onClick={() =>
                      void hacer(async () => {
                        await push.desactivar();
                        return "Este dispositivo ya no recibirá notificaciones.";
                      })
                    }
                  >
                    Desactivar en este dispositivo
                  </button>
                </>
              )}
            </div>
          )}
          {mensaje && <p role="status">{mensaje}</p>}
        </div>
      )}
    </section>
  );
}
