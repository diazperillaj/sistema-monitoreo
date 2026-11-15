/**
 * La tira-instrumento de un nodo (§11.4, antes TarjetaNodo). Arriba la luz, el nombre y la
 * palanca; debajo, sus escalas y sus datos con rótulo de placa. "Vigilando" lo dicen la luz y la
 * palanca; en palabras solo va lo que no es normal. Lo que no vigila va rayado.
 */
import { TriangleAlert } from "lucide-react";
import { instrumento, lecturaEnVivo, type Distintivo } from "../dominio/instrumento";
import type { NodoCentral } from "../dominio/protocolo";
import { hace } from "../dominio/tiempo";
import { cn } from "../lib/utils";
import { Escala } from "./Escala";
import { InterruptorNodo } from "./InterruptorNodo";
import { Lampara, type Luz } from "./Lampara";

type Aspecto = Distintivo | "sin_datos";

const LUZ: Record<Aspecto, Luz> = {
  vigilando: "vigilando",
  alarma: "alarma",
  desactivado: "apagada",
  sin_conexion: "apagada",
  esperando: "apagada",
  sin_datos: "incierta",
};

const COLOR_TEXTO: Record<Aspecto, string> = {
  vigilando: "text-verdin",
  alarma: "font-semibold tracking-wide text-alarma",
  desactivado: "text-tinta-2",
  sin_conexion: "text-tinta-2",
  esperando: "text-tinta-2",
  sin_datos: "text-tinta-2",
};

export interface InstrumentoProps {
  casaId: number;
  nodo: NodoCentral;
  /** La central está en línea y sus datos llegan: si no, nada de lo que se ve está al día. */
  vivo: boolean;
  /** Segundos que tiene el dato, para que los contadores avancen entre reportes (§11.3). */
  edadS: number;
}

export function Instrumento({ casaId, nodo, vivo, edadS }: InstrumentoProps) {
  const ins = instrumento(nodo);
  const aspecto: Aspecto = vivo ? ins.distintivo : "sin_datos";
  const quieta = aspecto === "sin_conexion" || aspecto === "esperando" || aspecto === "sin_datos";
  const rayado = quieta || aspecto === "desactivado";
  const mandos = vivo && nodo.visto && nodo.enLinea;
  const [principal, ...otros] = ins.interruptores;

  let texto = vivo ? ins.texto : "Sin datos";
  if (aspecto === "sin_conexion" && ins.ultimoDatoHaceS !== null) {
    texto += ` · último dato ${hace(ins.ultimoDatoHaceS)}`;
  }

  const escala = (i: number) => {
    const e = ins.escalas[i];
    if (!e) return null;
    const lectura = lecturaEnVivo(e, {
      antiguedadS: edadS,
      segundosDesdeLlegada: 0,
      enVivo: vivo && nodo.enLinea,
    });
    return <Escala key={e.etiqueta} escala={e} lectura={lectura} quieta={quieta} />;
  };

  return (
    <li
      data-nodo={nodo.id}
      data-distintivo={aspecto}
      className={cn("space-y-2 px-4 pt-1.5 pb-3", rayado && "rayado")}
    >
      <div className="flex min-h-11 items-center gap-3">
        <Lampara luz={LUZ[aspecto]} />
        <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2">
          <h3 className="min-w-0 truncate font-semibold">{ins.nombre}</h3>
          {aspecto === "vigilando" ? (
            <span className="sr-only">{texto}</span>
          ) : (
            <span className={cn("text-sm", COLOR_TEXTO[aspecto])}>{texto}</span>
          )}
          {ins.movimiento && !quieta && <span className="rotulo text-tinta">Movimiento ahora</span>}
        </div>
        {principal && (
          <InterruptorNodo
            casaId={casaId}
            nodo={nodo.id}
            interruptor={principal}
            deshabilitado={!mandos}
          />
        )}
      </div>

      {vivo && ins.alarmas.length > 0 && (
        <p className="text-sm font-medium text-alarma">{ins.alarmas.join(" · ")}</p>
      )}

      {ins.ayuda && <p className="text-sm text-tinta-2">{ins.ayuda}</p>}

      {escala(0)}

      {/* Los datos van con el instrumento principal, antes del sub-instrumento (la presencia) */}
      {!quieta && ins.datos.length > 0 && (
        <dl className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5">
          {ins.datos.map((dato) => (
            <div key={dato.etiqueta} className="flex items-baseline gap-1.5">
              <dt className="rotulo">{dato.etiqueta}</dt>
              <dd
                className={cn(
                  "text-sm tabular-nums",
                  dato.aviso ? "inline-flex items-center gap-1 font-semibold" : "font-medium",
                )}
              >
                {dato.aviso && <TriangleAlert aria-hidden="true" className="size-3.5" />}
                {dato.valor}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {otros.map((interruptor) => (
        <InterruptorNodo
          key={interruptor.sub}
          casaId={casaId}
          nodo={nodo.id}
          interruptor={interruptor}
          deshabilitado={!mandos}
          conRotulo
        />
      ))}

      {ins.escalas.slice(1).map((_, i) => escala(i + 1))}
    </li>
  );
}
