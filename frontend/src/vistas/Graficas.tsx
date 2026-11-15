/**
 * Gráficas de la casa (§11.2): temperatura y sensor de gas de la cocina, caudal del agua y las
 * alarmas por día. Se cargan diferidas (Recharts no pesa en el tablero) y se refrescan cada 60 s.
 * Una gráfica por medida, nunca dos escalas en el mismo eje; cada una trae sus datos en tabla.
 */
import { useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  BarStack,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type XAxisTickContentProps,
} from "recharts";
import {
  useLecturas,
  useResumen,
  type Metrica,
  type Periodo,
  type Resumen,
} from "../api/administracion";
import { mensajeDe } from "../api/cliente";
import { Boton } from "../componentes/ui/Boton";
import {
  conHuecos,
  diaCorto,
  diaEnPartes,
  marcasDeTiempo,
  resumenSerie,
  type Muestra,
} from "../dominio/graficas";
import { cuando, duracion, hora } from "../dominio/tiempo";
import { cn } from "../lib/utils";
import { useCasaActual } from "../tiempo-real/casaActual";

const PERIODOS: Record<
  Periodo,
  { texto: string; lapso: string; ms: number; intervaloMs: number; pasoHoras: number }
> = {
  "24h": {
    texto: "24 horas",
    lapso: "en las últimas 24 horas",
    ms: 24 * 3600_000,
    intervaloMs: 5 * 60_000,
    pasoHoras: 6,
  },
  "7d": {
    texto: "7 días",
    lapso: "en los últimos 7 días",
    ms: 7 * 24 * 3600_000,
    intervaloMs: 3600_000,
    pasoHoras: 24,
  },
};

const EJE = { fill: "var(--tinta-3)", fontSize: 12, fontFamily: "var(--font-cifras)" };

const NOMBRES_TIPO: Record<string, string> = {
  INTRUSION: "Intrusión",
  SIN_MOVIMIENTO: "Sin movimiento",
  AGUA: "Agua",
  GAS: "Gas",
  TEMPERATURA: "Temperatura",
  NODO_SIN_CONEXION: "Nodo sin conexión",
  CENTRAL_DESCONECTADA: "Central desconectada",
};

interface Medida {
  titulo: string;
  explicacion: string;
  nodo: number;
  metrica: Metrica;
  unidad: string;
  decimales: number;
}

const MEDIDAS: Medida[] = [
  {
    titulo: "Temperatura de la cocina",
    explicacion: "Del sensor del nodo de gas.",
    nodo: 4,
    metrica: "temperatura",
    unidad: "°C",
    decimales: 1,
  },
  {
    titulo: "Sensor de gas",
    explicacion:
      "Lectura del sensor, de 0 a 4095. La central da alarma si se mantiene alta 4 minutos seguidos.",
    nodo: 4,
    metrica: "gas",
    unidad: "",
    decimales: 0,
  },
  {
    titulo: "Agua de la cocina",
    explicacion: "Caudal mientras la llave está abierta.",
    nodo: 3,
    metrica: "caudal",
    unidad: "L/min",
    decimales: 1,
  },
];

function conUnidad(valor: number, medida: Pick<Medida, "unidad" | "decimales">): string {
  return `${valor.toFixed(medida.decimales)}${medida.unidad ? ` ${medida.unidad}` : ""}`;
}

// ------------------------------------------------------------------ piezas comunes
function Placa({
  titulo,
  explicacion,
  resumen,
  children,
}: {
  titulo: string;
  explicacion: string;
  resumen?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={titulo}
      className="placa @container space-y-3 rounded-[10px] px-4 pt-4 pb-3"
    >
      <div className="space-y-0.5">
        <h2 className="font-semibold">{titulo}</h2>
        <p className="text-sm text-tinta-3">{explicacion}</p>
      </div>
      {resumen}
      {children}
    </section>
  );
}

/** En 7 días, cada día en dos líneas ("lun" y "28"): así caben los siete en un celular. */
function MarcaDia({ x, y, payload }: XAxisTickContentProps) {
  const { semana, numero } = diaEnPartes(Number(payload.value));
  return (
    <text x={x} y={y} textAnchor="middle" {...EJE}>
      <tspan x={x} dy="0.9em">
        {semana}
      </tspan>
      <tspan x={x} dy="1.25em">
        {numero}
      </tspan>
    </text>
  );
}

function Burbuja({ valor, detalle }: { valor: string; detalle: string }) {
  return (
    <div className="placa rounded-[6px] px-3 py-2 text-sm">
      <p className="cifras text-base font-semibold">{valor}</p>
      <p className="text-tinta-2">{detalle}</p>
    </div>
  );
}

function TablaDeDatos({
  encabezados,
  filas,
}: {
  encabezados: [string, string];
  filas: [string, string][];
}) {
  return (
    <details className="group">
      <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-tinta-2 hover:text-tinta">
        Ver los datos
      </summary>
      <div className="max-h-64 overflow-y-auto rounded-[6px] ring-1 ring-filo ring-inset">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-cara-2 text-left text-tinta-2">
            <tr>
              <th className="px-3 py-2 font-medium">{encabezados[0]}</th>
              <th className="px-3 py-2 text-right font-medium">{encabezados[1]}</th>
            </tr>
          </thead>
          <tbody className="cifras divide-y divide-filo">
            {filas.map(([a, b], i) => (
              <tr key={i}>
                <td className="px-3 py-1.5">{a}</td>
                <td className="px-3 py-1.5 text-right">{b}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ------------------------------------------------------------------ una medida en el tiempo
function GraficaMedida({
  casaId,
  medida,
  periodo,
}: {
  casaId: number;
  medida: Medida;
  periodo: Periodo;
}) {
  const lecturas = useLecturas(casaId, medida.nodo, medida.metrica, periodo);
  const { ms, intervaloMs, pasoHoras } = PERIODOS[periodo];
  const hasta = lecturas.dataUpdatedAt; // la hora en que llegaron: el eje termina ahí
  const desde = hasta - ms;

  if (lecturas.isPending) {
    return (
      <Placa titulo={medida.titulo} explicacion={medida.explicacion}>
        <div
          aria-busy="true"
          aria-label="Cargando la gráfica"
          className="h-48 rounded-[6px] bg-cara-2"
        />
      </Placa>
    );
  }
  if (lecturas.isError) {
    return (
      <Placa titulo={medida.titulo} explicacion={medida.explicacion}>
        <p className="text-tinta-2">{mensajeDe(lecturas.error)}</p>
        <Boton variante="secundario" onClick={() => void lecturas.refetch()}>
          Reintentar
        </Boton>
      </Placa>
    );
  }

  const muestras: Muestra[] = conHuecos(lecturas.data, intervaloMs);
  const { ultimo, maximo, minimo } = resumenSerie(muestras);
  if (!ultimo || maximo === null || minimo === null) {
    return (
      <Placa titulo={medida.titulo} explicacion={medida.explicacion}>
        <p className="rounded-[6px] bg-cara-2 px-3 py-6 text-center text-sm text-tinta-2">
          Sin lecturas {PERIODOS[periodo].lapso}. La central guarda una por minuto cuando el nodo
          está conectado.
        </p>
      </Placa>
    );
  }
  const reciente = hasta - ultimo.t < 2 * intervaloMs;
  const marcas = marcasDeTiempo(desde, hasta, pasoHoras);

  return (
    <Placa
      titulo={medida.titulo}
      explicacion={medida.explicacion}
      resumen={
        // En una placa angosta la última lectura va sola en su línea y Máx./Mín. debajo, juntos;
        // así las tres medidas se parten igual
        <dl className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
          <div className="flex basis-full items-baseline gap-1.5 @md:basis-auto">
            <dt className="rotulo">
              {reciente ? "Ahora" : `Último, ${cuando(new Date(ultimo.t))}`}
            </dt>
            <dd className="cifras text-xl font-semibold">{conUnidad(ultimo.valor, medida)}</dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="rotulo">Máx.</dt>
            <dd className="cifras font-medium">{conUnidad(maximo, medida)}</dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="rotulo">Mín.</dt>
            <dd className="cifras font-medium">{conUnidad(minimo, medida)}</dd>
          </div>
        </dl>
      }
    >
      <div
        className={cn(
          "h-48 transition-opacity duration-200 lg:h-56",
          lecturas.isPlaceholderData && "opacity-50",
        )}
        role="img"
        aria-label={`${medida.titulo}: de ${conUnidad(minimo, medida)} a ${conUnidad(maximo, medida)}; la última, ${conUnidad(ultimo.valor, medida)}.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={muestras} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--filo)" strokeWidth={1} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={[desde, hasta]}
              ticks={marcas}
              interval={0}
              height={periodo === "7d" ? 40 : 30}
              tick={
                periodo === "24h" ? EJE : (marca: XAxisTickContentProps) => <MarcaDia {...marca} />
              }
              tickFormatter={periodo === "24h" ? (t: number) => hora(new Date(t)) : undefined}
              tickLine={false}
              axisLine={{ stroke: "var(--filo)" }}
            />
            <YAxis
              width={44}
              domain={["auto", "auto"]}
              tickCount={4}
              tickFormatter={(v: number) => v.toFixed(medida.decimales)}
              tick={EJE}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ stroke: "var(--tinta-3)", strokeWidth: 1 }}
              isAnimationActive={false}
              content={({ active, payload }) => {
                const punto = payload?.[0]?.payload as Muestra | undefined;
                if (!active || !punto || punto.valor === null) return null;
                return (
                  <Burbuja
                    valor={conUnidad(punto.valor, medida)}
                    detalle={cuando(new Date(punto.t))}
                  />
                );
              }}
            />
            <Area
              dataKey="valor"
              type="monotone"
              stroke="var(--tinta)"
              strokeWidth={2}
              fill="var(--tinta)"
              fillOpacity={0.1}
              connectNulls={false}
              isAnimationActive={false}
              activeDot={{ r: 4, fill: "var(--tinta)", stroke: "var(--cara)", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <TablaDeDatos
        encabezados={["Hora", medida.unidad || "Lectura"]}
        filas={muestras
          .filter((m): m is { t: number; valor: number } => m.valor !== null)
          .reverse()
          .map((m) => [cuando(new Date(m.t)), m.valor.toFixed(medida.decimales)])}
      />
    </Placa>
  );
}

// ------------------------------------------------------------------ alarmas por día
function Leyenda() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-tinta-2">
      <li className="flex items-center gap-1.5">
        <span aria-hidden="true" className="size-2.5 rounded-[2px] bg-grafica-alarma" />
        De los sensores
      </li>
      <li className="flex items-center gap-1.5">
        <span aria-hidden="true" className="size-2.5 rounded-[2px] bg-tinta-3" />
        De conexión
      </li>
    </ul>
  );
}

function GraficaAlarmas({ resumen, cargando }: { resumen: Resumen; cargando: boolean }) {
  const datos = resumen.alarmas_por_dia.map((d) => ({
    ...d,
    t: Date.parse(`${d.dia}T12:00:00-05:00`),
    total: d.sensor + d.conexion,
  }));
  const total = datos.reduce((suma, d) => suma + d.total, 0);
  const porTipo = Object.entries(resumen.alarmas_por_tipo).sort((a, b) => b[1] - a[1]);
  const medio = resumen.tiempo_medio_respuesta_s;

  return (
    <Placa
      titulo={`Alarmas de los últimos ${resumen.dias} días`}
      explicacion="Cuántas se abrieron cada día."
      resumen={
        <div className="space-y-1.5">
          <dl className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
            <div className="flex items-baseline gap-1.5">
              <dt className="rotulo">En total</dt>
              <dd className="cifras text-xl font-semibold">{total}</dd>
            </div>
            <div className="flex items-baseline gap-1.5">
              <dt className="rotulo">Tiempo para silenciar</dt>
              <dd className="cifras font-medium">
                {medio === null ? "—" : `${duracion(medio)} en promedio`}
              </dd>
            </div>
          </dl>
          {porTipo.length > 0 && (
            <p className="text-sm text-tinta-2">
              {porTipo
                .map(([tipo, cantidad]) => `${NOMBRES_TIPO[tipo] ?? tipo} ${cantidad}`)
                .join(" · ")}
            </p>
          )}
        </div>
      }
    >
      {total === 0 ? (
        <p className="rounded-[6px] bg-cara-2 px-3 py-6 text-center text-sm text-tinta-2">
          Ninguna alarma en estos días.
        </p>
      ) : (
        <>
          <Leyenda />
          <div
            className={cn("h-44 transition-opacity duration-200", cargando && "opacity-50")}
            role="img"
            aria-label={`Alarmas por día: ${datos
              .map((d) => `${diaCorto(d.t)}, ${d.sensor} de sensores y ${d.conexion} de conexión`)
              .join("; ")}.`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={datos} margin={{ top: 16, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--filo)" strokeWidth={1} />
                <XAxis
                  dataKey="t"
                  tickFormatter={diaCorto}
                  tick={EJE}
                  tickLine={false}
                  axisLine={{ stroke: "var(--filo)" }}
                />
                <YAxis
                  width={28}
                  allowDecimals={false}
                  tick={EJE}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ fill: "var(--cara-2)" }}
                  isAnimationActive={false}
                  content={({ active, payload }) => {
                    const dia = payload?.[0]?.payload as (typeof datos)[number] | undefined;
                    if (!active || !dia) return null;
                    return (
                      <Burbuja
                        valor={`${dia.total} ${dia.total === 1 ? "alarma" : "alarmas"}`}
                        detalle={`${diaCorto(dia.t)} · ${dia.sensor} de sensores, ${dia.conexion} de conexión`}
                      />
                    );
                  }}
                />
                {/* Solo la punta de la pila va redondeada; entre tramos, 2 px del color de la placa */}
                <BarStack stackId="alarmas" radius={[4, 4, 0, 0]}>
                  <Bar
                    dataKey="sensor"
                    fill="var(--grafica-alarma)"
                    stroke="var(--cara)"
                    strokeWidth={2}
                    maxBarSize={24}
                    isAnimationActive={false}
                  />
                  <Bar
                    dataKey="conexion"
                    fill="var(--tinta-3)"
                    stroke="var(--cara)"
                    strokeWidth={2}
                    maxBarSize={24}
                    isAnimationActive={false}
                  />
                </BarStack>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <TablaDeDatos
            encabezados={["Día", "Sensores · conexión"]}
            filas={[...datos].reverse().map((d) => [diaCorto(d.t), `${d.sensor} · ${d.conexion}`])}
          />
        </>
      )}
    </Placa>
  );
}

function Alarmas({ casaId }: { casaId: number }) {
  const resumen = useResumen(casaId, 7);
  if (resumen.isPending) {
    return (
      <div
        aria-busy="true"
        aria-label="Cargando las alarmas"
        className="placa h-64 rounded-[10px]"
      />
    );
  }
  if (resumen.isError) {
    return (
      <div className="placa space-y-3 rounded-[10px] px-4 py-5">
        <p className="text-tinta-2">{mensajeDe(resumen.error)}</p>
        <Boton variante="secundario" onClick={() => void resumen.refetch()}>
          Reintentar
        </Boton>
      </div>
    );
  }
  return <GraficaAlarmas resumen={resumen.data} cargando={resumen.isPlaceholderData} />;
}

// ------------------------------------------------------------------ vista
/** Radios nativos, como Apariencia en Perfil: las flechas del teclado ya cambian el periodo. */
function SelectorPeriodo({
  periodo,
  alCambiar,
}: {
  periodo: Periodo;
  alCambiar: (periodo: Periodo) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Periodo de las lecturas"
      className="grid grid-cols-2 gap-1 rounded-[8px] bg-cara-2 p-1 ring-1 ring-filo ring-inset"
    >
      {(Object.keys(PERIODOS) as Periodo[]).map((opcion) => (
        <label
          key={opcion}
          className={cn(
            "pulsable flex h-11 cursor-pointer items-center justify-center rounded-[6px] text-sm font-semibold text-tinta-2",
            "has-[:checked]:bg-cara has-[:checked]:text-tinta",
            "has-[:checked]:shadow-[0_0_0_1px_var(--filo),0_1px_2px_rgb(var(--sombra)/0.12)]",
            "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-tinta",
          )}
        >
          <input
            type="radio"
            name="periodo"
            value={opcion}
            checked={periodo === opcion}
            onChange={() => alCambiar(opcion)}
            className="sr-only"
          />
          {PERIODOS[opcion].texto}
        </label>
      ))}
    </div>
  );
}

export default function Graficas() {
  const { casaId } = useCasaActual();
  const [periodo, setPeriodo] = useState<Periodo>("24h");
  if (casaId === null) return null;

  return (
    <>
      <h1 className="text-xl font-semibold">Gráficas</h1>
      {/* En pantallas anchas, las alarmas quedan quietas a la izquierda y las lecturas van a la
          derecha, una debajo de otra para que la misma hora caiga en el mismo lugar */}
      <div className="space-y-4 lg:grid lg:grid-cols-[minmax(0,4fr)_minmax(0,7fr)] lg:items-start lg:gap-x-6 lg:space-y-0">
        <div className="lg:sticky lg:top-[4.5rem]">
          <Alarmas casaId={casaId} />
        </div>
        <section aria-labelledby="titulo-lecturas" className="space-y-4">
          <h2 id="titulo-lecturas" className="px-1 pt-2 font-semibold lg:pt-0">
            Lecturas de los sensores
          </h2>
          {/* Un solo selector, justo arriba de todo lo que cambia con él */}
          <SelectorPeriodo periodo={periodo} alCambiar={setPeriodo} />
          {MEDIDAS.map((medida) => (
            <GraficaMedida key={medida.metrica} casaId={casaId} medida={medida} periodo={periodo} />
          ))}
        </section>
      </div>
    </>
  );
}
