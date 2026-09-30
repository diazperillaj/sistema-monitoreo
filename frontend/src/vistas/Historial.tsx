/**
 * Historial de la casa (§11.2): alarmas (duración y quién las silenció) y eventos, con filtros
 * y "Cargar más" por cursor. El WebSocket lo invalida cuando llega algo nuevo.
 */
import * as Pestanas from "@radix-ui/react-tabs";
import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router";
import { mensajeDe } from "../api/cliente";
import { useAlarmas, useEventos, type FiltrosAlarmas } from "../api/consultas";
import { Lampara } from "../componentes/Lampara";
import { Boton } from "../componentes/ui/Boton";
import { Palanca } from "../componentes/ui/Palanca";
import { NODOS, type Alarma, type Evento } from "../dominio/protocolo";
import { dia, duracion, hora } from "../dominio/tiempo";
import { cn } from "../lib/utils";
import { useCasaActual } from "../tiempo-real/casaActual";

// ------------------------------------------------------------------ piezas comunes
function porDia<T>(items: T[], momento: (item: T) => string): [string, T[]][] {
  const grupos = new Map<string, T[]>();
  for (const item of items) {
    const clave = dia(momento(item));
    grupos.set(clave, [...(grupos.get(clave) ?? []), item]);
  }
  return [...grupos.entries()];
}

function Cargando() {
  return (
    <ul
      aria-busy="true"
      aria-label="Cargando"
      className="placa divide-y divide-filo rounded-[10px]"
    >
      {[0, 1, 2, 3].map((i) => (
        <li key={i} className="flex gap-3 px-4 py-3.5">
          <span className="mt-1.5 size-2.5 rounded-full ring-1 ring-marca ring-inset" />
          <div className="flex-1 space-y-1.5">
            <div className="h-4 w-2/3 rounded-[3px] bg-cara-2" />
            <div className="h-3.5 w-1/3 rounded-[3px] bg-cara-2" />
          </div>
        </li>
      ))}
    </ul>
  );
}

interface PaginasProps {
  cargando: boolean;
  error: unknown;
  vacio: boolean;
  textoVacio: string;
  hayMas: boolean;
  trayendoMas: boolean;
  traerMas: () => void;
  reintentar: () => void;
  children: ReactNode;
}

function Paginas(p: PaginasProps) {
  if (p.cargando) return <Cargando />;
  if (p.error && p.vacio) {
    return (
      <div className="placa space-y-3 rounded-[10px] px-4 py-5">
        <p className="text-tinta-2">{mensajeDe(p.error)}</p>
        <Boton variante="secundario" onClick={p.reintentar}>
          Reintentar
        </Boton>
      </div>
    );
  }
  if (p.vacio) {
    return <p className="placa rounded-[10px] px-4 py-5 text-tinta-2">{p.textoVacio}</p>;
  }
  return (
    <div className="space-y-5">
      {p.children}
      {p.hayMas ? (
        <Boton
          variante="secundario"
          className="w-full"
          onClick={p.traerMas}
          ocupado={p.trayendoMas && "Cargando…"}
        >
          Cargar más
        </Boton>
      ) : (
        <p className="text-center text-sm text-tinta-3">No hay más.</p>
      )}
    </div>
  );
}

function Grupo({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="px-1 text-sm font-semibold text-tinta-2">{titulo}</h2>
      <ul className="placa divide-y divide-filo overflow-hidden rounded-[10px]">{children}</ul>
    </section>
  );
}

function Interruptor({
  etiqueta,
  activo,
  alCambiar,
}: {
  etiqueta: string;
  activo: boolean;
  alCambiar: (activo: boolean) => void;
}) {
  const id = `filtro-${etiqueta.replace(/\s+/g, "-").toLowerCase()}`;
  return (
    <div className="flex min-h-11 items-center gap-3">
      <label htmlFor={id} className="text-sm font-medium">
        {etiqueta}
      </label>
      <Palanca id={id} etiqueta={etiqueta} activa={activo} alCambiar={alCambiar} />
    </div>
  );
}

// ------------------------------------------------------------------ alarmas
function cierre(alarma: Alarma): string {
  switch (alarma.cerrada_por) {
    case "usuario":
      return `Silenciada por ${alarma.cerrada_por_usuario?.nombre ?? "alguien de la casa"}`;
    case "central":
      return "Se apagó en la casa";
    case "automatica":
      return "Se cerró al volver la conexión";
    default:
      return "Cerrada";
  }
}

function FilaAlarma({ alarma }: { alarma: Alarma }) {
  const abierta = alarma.fin_en === null;
  const avisos = alarma.avisos_enviados === 1 ? "1 aviso" : `${alarma.avisos_enviados} avisos`;
  const detalle = abierta
    ? `Abierta · lleva ${duracion(alarma.duracion_s)}`
    : `Duró ${duracion(alarma.duracion_s)} · ${cierre(alarma)}`;
  return (
    <li className="flex gap-3 px-4 py-3">
      <Lampara luz={abierta ? "alarma" : "apagada"} fija className="mt-1.5" />
      <div className="min-w-0 flex-1">
        <p className="leading-6">
          <span className="font-semibold">{alarma.nodo_nombre}</span>
          <span className="text-tinta-2"> · </span>
          {alarma.texto}
        </p>
        <p className={cn("text-sm", abierta ? "font-medium text-alarma" : "text-tinta-2")}>
          {detalle}
          {alarma.avisos_enviados > 0 && <span className="text-tinta-3"> · {avisos}</span>}
        </p>
      </div>
      <time dateTime={alarma.inicio_en} className="cifras shrink-0 pt-0.5 text-sm text-tinta-2">
        {hora(alarma.inicio_en)}
      </time>
    </li>
  );
}

function ListaAlarmas({ casaId }: { casaId: number }) {
  const [parametros, setParametros] = useSearchParams();
  const filtros: FiltrosAlarmas = {
    abiertas: parametros.get("abiertas") === "1" || undefined,
    nodo: parametros.has("nodo") ? Number(parametros.get("nodo")) : undefined,
  };
  const consulta = useAlarmas(casaId, filtros);
  const items = consulta.data?.pages.flatMap((p) => p.items) ?? [];

  function cambiar(clave: string, valor: string | null) {
    setParametros(
      (previos) => {
        const nuevos = new URLSearchParams(previos);
        if (valor === null) nuevos.delete(clave);
        else nuevos.set(clave, valor);
        return nuevos;
      },
      { replace: true },
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="relative">
          <label htmlFor="filtro-nodo" className="sr-only">
            Nodo
          </label>
          <select
            id="filtro-nodo"
            value={filtros.nodo ?? ""}
            onChange={(e) => cambiar("nodo", e.target.value === "" ? null : e.target.value)}
            className="h-11 appearance-none rounded-[6px] bg-cara pr-10 pl-3 font-medium ring-1 ring-filo ring-inset"
          >
            <option value="">Todos los nodos</option>
            {NODOS.map((nombre, id) => (
              <option key={id} value={id}>
                {nombre}
              </option>
            ))}
          </select>
          <ChevronDown
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-tinta-3"
          />
        </div>
        <Interruptor
          etiqueta="Solo abiertas"
          activo={filtros.abiertas === true}
          alCambiar={(activo) => cambiar("abiertas", activo ? "1" : null)}
        />
      </div>

      <Paginas
        cargando={consulta.isPending}
        error={consulta.error}
        vacio={items.length === 0}
        textoVacio={
          filtros.abiertas
            ? "No hay alarmas abiertas."
            : filtros.nodo !== undefined
              ? "Este nodo no tiene alarmas en el historial."
              : "Todavía no hay alarmas en el historial."
        }
        hayMas={consulta.hasNextPage}
        trayendoMas={consulta.isFetchingNextPage}
        traerMas={() => void consulta.fetchNextPage()}
        reintentar={() => void consulta.refetch()}
      >
        {porDia(items, (a) => a.inicio_en).map(([titulo, grupo]) => (
          <Grupo key={titulo} titulo={titulo}>
            {grupo.map((alarma) => (
              <FilaAlarma key={alarma.id} alarma={alarma} />
            ))}
          </Grupo>
        ))}
      </Paginas>
    </div>
  );
}

// ------------------------------------------------------------------ eventos
function FilaEvento({ evento }: { evento: Evento }) {
  const luz = evento.es_alarma ? "alarma" : evento.tipo === "alarma_resuelta" ? "apagada" : null;
  return (
    <li className="flex gap-3 px-4 py-3">
      <span className="mt-1.5 flex size-2.5 shrink-0">{luz && <Lampara luz={luz} fija />}</span>
      <div className="min-w-0 flex-1">
        <p className="leading-6">{evento.texto}</p>
        {evento.usuario && <p className="text-sm text-tinta-3">{evento.usuario.nombre}</p>}
      </div>
      <time dateTime={evento.ocurrido_en} className="cifras shrink-0 pt-0.5 text-sm text-tinta-2">
        {hora(evento.ocurrido_en)}
      </time>
    </li>
  );
}

function ListaEventos({ casaId }: { casaId: number }) {
  const [parametros, setParametros] = useSearchParams();
  const soloAlarmas = parametros.get("solo") === "alarmas";
  const consulta = useEventos(casaId, soloAlarmas);
  const items = consulta.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Interruptor
          etiqueta="Solo alarmas"
          activo={soloAlarmas}
          alCambiar={(activo) =>
            setParametros(
              (previos) => {
                const nuevos = new URLSearchParams(previos);
                if (activo) nuevos.set("solo", "alarmas");
                else nuevos.delete("solo");
                return nuevos;
              },
              { replace: true },
            )
          }
        />
      </div>
      <Paginas
        cargando={consulta.isPending}
        error={consulta.error}
        vacio={items.length === 0}
        textoVacio={soloAlarmas ? "No hay eventos de alarma." : "Todavía no hay eventos."}
        hayMas={consulta.hasNextPage}
        trayendoMas={consulta.isFetchingNextPage}
        traerMas={() => void consulta.fetchNextPage()}
        reintentar={() => void consulta.refetch()}
      >
        {porDia(items, (e) => e.ocurrido_en).map(([titulo, grupo]) => (
          <Grupo key={titulo} titulo={titulo}>
            {grupo.map((evento) => (
              <FilaEvento key={evento.id} evento={evento} />
            ))}
          </Grupo>
        ))}
      </Paginas>
    </div>
  );
}

// ------------------------------------------------------------------ vista
const PESTANA =
  "pulsable h-11 rounded-[6px] text-sm font-semibold text-tinta-2 data-[state=active]:bg-cara data-[state=active]:text-tinta data-[state=active]:shadow-[0_0_0_1px_var(--filo),0_1px_2px_rgb(var(--sombra)/0.12)]";

export default function Historial() {
  const { casaId } = useCasaActual();
  const [parametros, setParametros] = useSearchParams();
  const pestana = parametros.get("ver") === "eventos" ? "eventos" : "alarmas";
  if (casaId === null) return null;

  return (
    <>
      <h1 className="text-xl font-semibold">Historial</h1>
      <Pestanas.Root
        value={pestana}
        onValueChange={(valor) => setParametros(valor === "eventos" ? { ver: "eventos" } : {})}
        className="space-y-4"
      >
        <Pestanas.List
          aria-label="Qué ver"
          className="grid grid-cols-2 gap-1 rounded-[8px] bg-cara-2 p-1 ring-1 ring-filo ring-inset"
        >
          <Pestanas.Trigger value="alarmas" className={PESTANA}>
            Alarmas
          </Pestanas.Trigger>
          <Pestanas.Trigger value="eventos" className={PESTANA}>
            Eventos
          </Pestanas.Trigger>
        </Pestanas.List>
        <Pestanas.Content value="alarmas" className="focus-visible:outline-offset-4">
          <ListaAlarmas casaId={casaId} />
        </Pestanas.Content>
        <Pestanas.Content value="eventos" className="focus-visible:outline-offset-4">
          <ListaEventos casaId={casaId} />
        </Pestanas.Content>
      </Pestanas.Root>
    </>
  );
}
