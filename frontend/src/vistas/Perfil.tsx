/**
 * Perfil (§11.2, §11.4): notificaciones de este dispositivo y de la cuenta, instalación, clave,
 * sesiones abiertas y salir. Telegram aparece aquí cuando exista (F4b, `disponible`).
 */
import { useQueryClient } from "@tanstack/react-query";
import { BellRing, CircleAlert, Download, LogOut } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { mensajeDe } from "../api/cliente";
import {
  claves,
  useCambiarClave,
  useCambiarPreferencias,
  useCerrarOtrasSesiones,
  useCerrarSesion,
  useEstadoPush,
  usePreferencias,
  useSalir,
  useSesiones,
  useYo,
} from "../api/consultas";
import { GuiaInstalacionIOS } from "../componentes/GuiaInstalacionIOS";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { Palanca } from "../componentes/ui/Palanca";
import { cuando } from "../dominio/tiempo";
import { describirDispositivo } from "../lib/dispositivo";
import { fijarTema, useTema, type PreferenciaTema } from "../lib/tema";
import { cn } from "../lib/utils";
import { useInstalacion } from "../notificaciones/instalacion";
import {
  activarPush,
  desactivarPush,
  esIOS,
  instalada,
  mensajeDePush,
  probarPush,
} from "../notificaciones/webpush";

/** Una tarjeta del perfil; su título es el de su primer bloque, no un rótulo encima. */
function Seccion({ id, titulo, children }: { id?: string; titulo: string; children: ReactNode }) {
  return (
    <section
      id={id}
      aria-label={titulo}
      className="placa scroll-mt-20 divide-y divide-filo rounded-[10px]"
    >
      {children}
    </section>
  );
}

// ------------------------------------------------------------------ notificaciones
function PushDeEsteCelular() {
  const cliente = useQueryClient();
  const push = useEstadoPush();
  const [accion, setAccion] = useState<"activando" | "probando" | "desactivando" | null>(null);
  // El error queda junto al botón hasta el próximo intento: un aviso que se va a los 4 s se pierde
  const [fallo, setFallo] = useState<string | null>(null);

  async function hacer(tipo: NonNullable<typeof accion>, trabajo: () => Promise<void>) {
    setAccion(tipo);
    setFallo(null);
    try {
      await trabajo();
    } catch (error) {
      setFallo(mensajeDePush(error));
    } finally {
      setAccion(null);
      await cliente.invalidateQueries({ queryKey: claves.pushDispositivo });
      await cliente.invalidateQueries({ queryKey: claves.preferencias });
    }
  }

  let contenido: ReactNode;
  switch (push.data) {
    case undefined:
      contenido = <p className="text-tinta-3">Revisando este dispositivo…</p>;
      break;
    case "requiere_instalar":
      contenido = <GuiaInstalacionIOS />;
      break;
    case "no_soportado":
      contenido = (
        <p className="text-tinta-2">
          Este navegador no puede recibir notificaciones. Prueba con Chrome en Android o con la app
          instalada en iPhone.
        </p>
      );
      break;
    case "bloqueado":
      contenido = (
        <p className="text-tinta-2">
          Las notificaciones están bloqueadas para este sitio. Permítelas en los ajustes del
          navegador y vuelve aquí.
        </p>
      );
      break;
    case "inactivo":
      contenido = (
        <div className="space-y-3">
          <p className="text-tinta-2">
            Actívalas para que una alarma te avise aunque la app esté cerrada.
          </p>
          <Boton
            icono={<BellRing aria-hidden="true" className="size-4" />}
            ocupado={accion === "activando" && "Activando…"}
            onClick={() =>
              void hacer("activando", async () => {
                await activarPush();
                toast.success("Listo: este dispositivo recibirá las alertas");
              })
            }
          >
            Activar en este dispositivo
          </Boton>
        </div>
      );
      break;
    case "activo":
      contenido = (
        <div className="space-y-3">
          <p className="flex items-center gap-2 font-medium">
            <span aria-hidden="true" className="size-2.5 rounded-full bg-verdin" />
            Este dispositivo recibe las alertas
          </p>
          <div className="flex flex-wrap gap-2">
            <Boton
              variante="secundario"
              ocupado={accion === "probando" && "Enviando…"}
              disabled={accion !== null}
              onClick={() =>
                void hacer("probando", async () => {
                  const enviados = await probarPush();
                  toast.success(
                    enviados === 1
                      ? "Prueba enviada a 1 dispositivo"
                      : `Prueba enviada a ${enviados} dispositivos`,
                  );
                })
              }
            >
              Enviar una prueba
            </Boton>
            <Boton
              variante="discreto"
              ocupado={accion === "desactivando" && "Desactivando…"}
              disabled={accion !== null}
              onClick={() => void hacer("desactivando", desactivarPush)}
            >
              Desactivar aquí
            </Boton>
          </div>
        </div>
      );
      break;
  }

  return (
    <div className="space-y-2 px-4 py-4">
      <h2 className="font-semibold">Alertas en este dispositivo</h2>
      {contenido}
      {fallo && (
        <p role="alert" className="flex items-start gap-1.5 text-sm font-medium">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {fallo}
        </p>
      )}
    </div>
  );
}

function PausaDeLaCuenta() {
  const preferencias = usePreferencias();
  const cambiar = useCambiarPreferencias();
  if (!preferencias.data) return null;
  const { activo, dispositivos } = preferencias.data.webpush;
  return (
    <div className="flex items-center gap-4 px-4 py-4">
      <div className="min-w-0 flex-1">
        <label htmlFor="pausa-webpush" className="font-semibold">
          Alertas por notificación
        </label>
        <p className="text-sm text-tinta-2">
          {dispositivos === 0
            ? "Todavía no las activaste en ningún dispositivo."
            : `${activo ? "Activas" : "En pausa"} en ${
                dispositivos === 1 ? "tu dispositivo" : `tus ${dispositivos} dispositivos`
              }. Pausarlas no borra nada.`}
        </p>
      </div>
      <Palanca
        id="pausa-webpush"
        etiqueta="Alertas por notificación en todos tus dispositivos"
        activa={cambiar.isPending ? (cambiar.variables.webpush ?? activo) : activo}
        enviando={cambiar.isPending}
        alCambiar={(valor) =>
          cambiar.mutate({ webpush: valor }, { onError: (e) => toast.error(mensajeDe(e)) })
        }
      />
    </div>
  );
}

function Instalar() {
  const instalacion = useInstalacion();
  if (instalada()) {
    return (
      <div className="space-y-1 px-4 py-4">
        <h2 className="font-semibold">App instalada</h2>
        <p className="text-tinta-2">Se abre desde su ícono, sin la barra del navegador.</p>
      </div>
    );
  }
  if (instalacion.disponible) {
    return (
      <div className="space-y-3 px-4 py-4">
        <h2 className="font-semibold">Instalar la app</h2>
        <p className="text-tinta-2">
          Queda como una app más: se abre sola, sin la barra del navegador.
        </p>
        <Boton
          variante="secundario"
          icono={<Download aria-hidden="true" className="size-4" />}
          onClick={() => void instalacion.instalar()}
        >
          Instalar app
        </Boton>
      </div>
    );
  }
  return null;
}

// ------------------------------------------------------------------ seguridad
function CambiarClave() {
  const cliente = useQueryClient();
  const cambiar = useCambiarClave();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [intento, setIntento] = useState(false);

  const corta = nueva.length > 0 && nueva.length < 10;
  const distinta = repetida.length > 0 && repetida !== nueva;

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setIntento(true);
    if (nueva.length < 10 || repetida !== nueva) return;
    cambiar.mutate(
      { clave_actual: actual, clave_nueva: nueva },
      {
        onSuccess: () => {
          toast.success("Clave cambiada", { description: "Cerramos tus otras sesiones." });
          setActual("");
          setNueva("");
          setRepetida("");
          setIntento(false);
          void cliente.invalidateQueries({ queryKey: claves.sesiones });
        },
      },
    );
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-4 px-4 py-4">
      <h2 className="font-semibold">Cambiar la clave</h2>
      <Campo
        etiqueta="Clave actual"
        clave
        autoComplete="current-password"
        value={actual}
        onChange={(e) => setActual(e.target.value)}
        error={cambiar.isError ? mensajeDe(cambiar.error) : null}
      />
      <Campo
        etiqueta="Clave nueva"
        clave
        autoComplete="new-password"
        ayuda="Mínimo 10 caracteres. Una frase corta es más fácil de recordar."
        value={nueva}
        onChange={(e) => setNueva(e.target.value)}
        error={(intento || corta) && nueva.length < 10 ? "Le faltan caracteres: mínimo 10." : null}
      />
      <Campo
        etiqueta="Repite la clave nueva"
        clave
        autoComplete="new-password"
        value={repetida}
        onChange={(e) => setRepetida(e.target.value)}
        error={
          (intento || distinta) && repetida !== nueva ? "No coincide con la clave nueva." : null
        }
      />
      <Boton
        type="submit"
        disabled={!actual || !nueva || !repetida}
        ocupado={cambiar.isPending && "Cambiando…"}
      >
        Cambiar clave
      </Boton>
    </form>
  );
}

function Sesiones() {
  const sesiones = useSesiones();
  const cerrar = useCerrarSesion();
  const cerrarOtras = useCerrarOtrasSesiones();
  if (sesiones.isPending) return <p className="px-4 py-4 text-tinta-3">Cargando sesiones…</p>;
  if (sesiones.isError)
    return <p className="px-4 py-4 text-tinta-2">{mensajeDe(sesiones.error)}</p>;
  const otras = sesiones.data.filter((s) => !s.actual).map((s) => s.id);
  return (
    <div className="px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h2 className="font-semibold">Sesiones abiertas</h2>
        {otras.length > 1 && (
          <Boton
            variante="discreto"
            tamano="compacto"
            className="-mr-3"
            ocupado={cerrarOtras.isPending && "Cerrando…"}
            onClick={() =>
              cerrarOtras.mutate(otras, {
                onSuccess: () => toast.success("Quedó abierta solo esta sesión"),
                onError: (e) => toast.error(mensajeDe(e)),
              })
            }
          >
            Cerrar las otras {otras.length}
          </Boton>
        )}
      </div>
      <ul className="mt-2 divide-y divide-filo">
        {sesiones.data.map((sesion) => (
          <li key={sesion.id} className="flex items-center gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">
                {describirDispositivo(sesion.user_agent)}
                {sesion.actual && (
                  <span className="ml-2 rounded-[4px] bg-verdin-fondo px-1.5 py-0.5 text-xs font-semibold text-verdin">
                    Esta sesión
                  </span>
                )}
              </p>
              <p className="text-sm text-tinta-3">
                Último uso: <span className="cifras">{cuando(sesion.ultimo_uso_en)}</span>
                {sesion.ip && <> · {sesion.ip}</>}
              </p>
            </div>
            {!sesion.actual && (
              <Boton
                variante="discreto"
                tamano="compacto"
                ocupado={cerrar.isPending && cerrar.variables === sesion.id && "Cerrando…"}
                onClick={() =>
                  cerrar.mutate(sesion.id, { onError: (e) => toast.error(mensajeDe(e)) })
                }
              >
                Cerrar
              </Boton>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ------------------------------------------------------------------ vista
export default function Perfil() {
  const yo = useYo().data;
  const salir = useSalir();
  const navegar = useNavigate();
  const ios = esIOS();

  return (
    <>
      <div>
        <h1 className="text-xl font-semibold">{yo?.usuario.nombre ?? "Perfil"}</h1>
        <p className="text-tinta-2">{yo?.usuario.email}</p>
      </div>

      <Seccion id="notificaciones" titulo="Alertas">
        <PushDeEsteCelular />
        <PausaDeLaCuenta />
      </Seccion>

      {!ios && <InstalarSiHace />}

      <Seccion titulo="Apariencia">
        <Apariencia />
      </Seccion>

      <Seccion titulo="Seguridad">
        <CambiarClave />
        <Sesiones />
      </Seccion>

      <Boton
        variante="secundario"
        className="w-full"
        icono={<LogOut aria-hidden="true" className="size-4" />}
        ocupado={salir.isPending && "Saliendo…"}
        // Salir por gusto lleva a la entrada sin ?volver=: quien entre después empieza en su casa
        onClick={() =>
          salir.mutate(undefined, { onSettled: () => navegar("/login", { replace: true }) })
        }
      >
        Salir de esta cuenta
      </Boton>
    </>
  );
}

const OPCIONES_TEMA: [PreferenciaTema, string][] = [
  ["sistema", "Automático"],
  ["claro", "Claro"],
  ["oscuro", "Oscuro"],
];

/** Claro, oscuro o como el dispositivo. Se guarda en este dispositivo, no en la cuenta. */
function Apariencia() {
  const { preferencia } = useTema();
  return (
    <div className="space-y-3 px-4 py-4">
      <h2 id="titulo-apariencia" className="font-semibold">
        Apariencia
      </h2>
      <div
        role="radiogroup"
        aria-labelledby="titulo-apariencia"
        className="grid grid-cols-3 gap-1 rounded-[8px] bg-cara-2 p-1 ring-1 ring-filo ring-inset"
      >
        {OPCIONES_TEMA.map(([valor, texto]) => (
          <label
            key={valor}
            className={cn(
              "pulsable flex h-11 cursor-pointer items-center justify-center rounded-[6px] text-sm font-semibold text-tinta-2",
              "has-[:checked]:bg-cara has-[:checked]:text-tinta",
              "has-[:checked]:shadow-[0_0_0_1px_var(--filo),0_1px_2px_rgb(var(--sombra)/0.12)]",
              "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-tinta",
            )}
          >
            <input
              type="radio"
              name="tema"
              value={valor}
              checked={preferencia === valor}
              onChange={() => fijarTema(valor)}
              className="sr-only"
            />
            {texto}
          </label>
        ))}
      </div>
      <p className="text-sm text-tinta-2">
        {preferencia === "sistema"
          ? "Sigue el modo claro u oscuro de este dispositivo."
          : "Se queda así en este dispositivo, aunque el sistema cambie."}
      </p>
    </div>
  );
}

/** La sección de instalación solo si hay algo que decir (en iPhone la guía va en Alertas). */
function InstalarSiHace() {
  const instalacion = useInstalacion();
  if (!instalada() && !instalacion.disponible) return null;
  return (
    <Seccion titulo="App">
      <Instalar />
    </Seccion>
  );
}
