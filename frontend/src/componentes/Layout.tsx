/**
 * El marco de la app con sesión (§11.1): barra superior con la casa y su luz de conexión,
 * navegación (abajo en el celular, arriba en pantallas anchas) y la conexión en vivo de la casa
 * que se está mirando, que sigue abierta al pasar al historial o al perfil.
 */
import { Gauge, History, UserRound, Volume2, VolumeOff, type LucideIcon } from "lucide-react";
import { useEffect } from "react";
import { Link, NavLink, Outlet, useMatch } from "react-router";
import { toast } from "sonner";
import { useCasas, useYo, type Yo } from "../api/consultas";
import { textoAviso, textoCorto, type Situacion } from "../dominio/conexion";
import type { NodoCentral } from "../dominio/protocolo";
import { cn } from "../lib/utils";
import {
  casaPorDefecto,
  ContextoCasa,
  esMiembro,
  recordarCasa,
  useEstadoEnVivo,
} from "../tiempo-real/casaActual";
import { useAlertaSonora, type AlertaSonora } from "../tiempo-real/useAlertaSonora";
import { useCasaEnVivo } from "../tiempo-real/useCasaEnVivo";
import { Lampara, type Luz } from "./Lampara";

const LUZ_CONEXION: Record<Situacion["tipo"], Luz> = {
  conectando: "incierta",
  sin_acceso: "apagada",
  sin_servidor: "apagada",
  central_desconectada: "apagada",
  reconectando: "incierta",
  respaldo: "incierta",
  retraso: "incierta",
  en_vivo: "vigilando",
};

function casaEnRuta(yo: Yo | null | undefined, valor: string | undefined): number | null {
  const id = Number(valor);
  return yo && Number.isInteger(id) && id > 0 && esMiembro(yo, id) ? id : null;
}

function BotonSonido({ sonido }: { sonido: AlertaSonora }) {
  if (!sonido.soportada) return null;
  const Icono = sonido.activa ? Volume2 : VolumeOff;
  return (
    <button
      type="button"
      aria-pressed={sonido.activa}
      aria-label="Sonido de alarmas en este celular"
      title={sonido.activa ? "Sonido activado" : "Sonido apagado"}
      onClick={() => {
        if (sonido.activa) {
          sonido.apagar();
          toast("Sonido apagado en este celular");
        } else {
          sonido.activar();
          toast("Sonido activado", {
            description: "Sonará mientras haya alarmas y la app esté abierta.",
          });
        }
      }}
      className={cn(
        "pulsable grid size-11 place-items-center rounded-[6px] hover:bg-cara-2",
        sonido.activa ? "text-tinta" : "text-tinta-3",
      )}
    >
      <Icono aria-hidden="true" className="size-5" />
    </button>
  );
}

interface Destino {
  a: string;
  texto: string;
  Icono: LucideIcon;
  fin?: boolean;
}

function destinos(casaId: number | null): Destino[] {
  const casa =
    casaId === null
      ? []
      : [
          { a: `/casa/${casaId}`, texto: "Tablero", Icono: Gauge, fin: true },
          { a: `/casa/${casaId}/historial`, texto: "Historial", Icono: History },
        ];
  return [...casa, { a: "/perfil", texto: "Perfil", Icono: UserRound }];
}

function Navegacion({
  casaId,
  alarma,
  className,
  enBarra = false,
}: {
  casaId: number | null;
  alarma: boolean;
  className?: string;
  enBarra?: boolean;
}) {
  return (
    <nav aria-label="Secciones" className={className}>
      <ul className={cn("flex", enBarra ? "gap-1" : "")}>
        {destinos(casaId).map(({ a, texto, Icono, fin }) => (
          <li key={a} className={enBarra ? "" : "flex-1"}>
            <NavLink
              to={a}
              end={fin}
              className={({ isActive }) =>
                cn(
                  "pulsable relative flex items-center justify-center font-medium",
                  enBarra
                    ? "h-11 gap-2 rounded-[6px] px-3 text-sm hover:bg-cara-2"
                    : "h-14 flex-col gap-0.5 text-xs",
                  isActive ? "text-tinta" : "text-tinta-3",
                  // La marca de la pestaña activa: una aguja corta, como en la escala
                  isActive &&
                    !enBarra &&
                    "before:absolute before:top-0 before:h-0.5 before:w-8 before:rounded-full before:bg-tinta",
                  isActive && enBarra && "bg-cara-2",
                )
              }
            >
              <span className="relative">
                <Icono aria-hidden="true" className="size-5" />
                {alarma && fin && (
                  <span
                    aria-hidden="true"
                    className="absolute -top-0.5 -right-1 size-2 rounded-full bg-alarma ring-2 ring-cara"
                  />
                )}
              </span>
              {texto}
              {alarma && fin && <span className="sr-only"> (hay una alarma)</span>}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function AvisoConexion({ situacion }: { situacion: Situacion }) {
  const texto = textoAviso(situacion);
  if (!texto) return null;
  const leve = situacion.tipo === "retraso";
  return (
    <div
      role="status"
      className={cn(
        "aparece -mx-4 px-4 py-2.5 text-sm sm:mx-0 sm:rounded-[6px]",
        leve ? "bg-cara-2 text-tinta-2 ring-1 ring-filo ring-inset" : "bg-aviso text-sobre-aviso",
      )}
    >
      {texto}
    </div>
  );
}

function AlarmaFueraDelTablero({ casaId, nodos }: { casaId: number; nodos: NodoCentral[] }) {
  const nombres = nodos.map((n) => n.nombre).join(", ");
  return (
    <Link
      to={`/casa/${casaId}`}
      className="aparece -mx-4 flex min-h-11 items-center gap-2.5 bg-alarma-campo px-4 py-2 text-sm font-semibold text-sobre-alarma sm:mx-0 sm:rounded-[6px]"
    >
      <span
        aria-hidden="true"
        className="size-2 rounded-full bg-sobre-alarma motion-safe:animate-latido"
      />
      <span className="flex-1">
        {nodos.length === 1 ? `Alarma: ${nombres}` : `${nodos.length} alarmas: ${nombres}`}
      </span>
      <span className="underline underline-offset-4">Ver tablero</span>
    </Link>
  );
}

export function Layout() {
  const yo = useYo().data; // RequiereSesion ya lo cargó
  const coincide = useMatch("/casa/:casaId/*");
  const enTablero = useMatch("/casa/:casaId") !== null;

  const enRuta = casaEnRuta(yo, coincide?.params.casaId);
  const casaId = enRuta ?? (yo ? casaPorDefecto(yo) : null);
  useEffect(() => {
    if (enRuta !== null) recordarCasa(enRuta);
  }, [enRuta]);

  const conexion = useCasaEnVivo(casaId, { alAbrirAlarma: () => sonido.avisar() });
  const envivo = useEstadoEnVivo(casaId, conexion);
  const nodosEnAlarma = envivo.consulta.data?.central?.nodos.filter((n) => n.al !== 0) ?? [];
  const sonido = useAlertaSonora(nodosEnAlarma.length > 0);

  const casas = useCasas().data;
  const nombre =
    casas?.find((c) => c.id === casaId)?.nombre ??
    yo?.casas.find((c) => c.id === casaId)?.nombre ??
    "Monitoreo del hogar";
  const variasCasas = (casas?.length ?? yo?.casas.length ?? 0) > 1;

  return (
    <ContextoCasa value={{ casaId, conexion, sonido }}>
      <div className="flex min-h-dvh flex-col">
        <header className="sticky top-0 z-20 border-b border-filo bg-cara pt-[env(safe-area-inset-top)]">
          <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-3 pr-2 pl-4">
            <div className="min-w-0 flex-1">
              {variasCasas ? (
                <Link to="/" className="block truncate font-semibold hover:underline">
                  {nombre}
                  <span className="sr-only"> (cambiar de casa)</span>
                </Link>
              ) : (
                <p className="truncate font-semibold">{nombre}</p>
              )}
            </div>
            <Navegacion
              casaId={casaId}
              alarma={nodosEnAlarma.length > 0 && !enTablero}
              enBarra
              className="hidden md:block"
            />
            {casaId !== null && (
              <p className="flex shrink-0 items-center gap-2 text-sm text-tinta-2">
                <Lampara luz={LUZ_CONEXION[envivo.situacion.tipo]} />
                {textoCorto(envivo.situacion)}
              </p>
            )}
            <BotonSonido sonido={sonido} />
          </div>
        </header>

        <main
          className={cn(
            "mx-auto w-full max-w-2xl flex-1 space-y-4 px-4 pt-4 pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:pb-12",
            enTablero && "lg:max-w-6xl",
          )}
        >
          {casaId !== null && <AvisoConexion situacion={envivo.situacion} />}
          {casaId !== null && !enTablero && nodosEnAlarma.length > 0 && (
            <AlarmaFueraDelTablero casaId={casaId} nodos={nodosEnAlarma} />
          )}
          <Outlet />
        </main>

        <Navegacion
          casaId={casaId}
          alarma={nodosEnAlarma.length > 0 && !enTablero}
          className="fixed inset-x-0 bottom-0 z-20 border-t border-filo bg-cara pb-[env(safe-area-inset-bottom)] md:hidden"
        />
      </div>
    </ContextoCasa>
  );
}
