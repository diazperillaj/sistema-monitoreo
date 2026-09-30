/**
 * El campo rojo (§11.4, antes BannerAlarmas): qué suena, dónde, desde cuándo, y "Silenciar".
 * Con una sola alarma, la lectura va en cifras grandes; con varias, una fila por nodo y
 * "Silenciar todas". El rojo de la app es solo esto.
 */
import { Volume2, VolumeOff } from "lucide-react";
import { pedirComando, pedirSilenciarTodo } from "../api/consultas";
import type { Alarma, NodoCentral } from "../dominio/protocolo";
import { reloj, textosAlarma } from "../dominio/textos";
import { hora } from "../dominio/tiempo";
import { useComandoEnCurso } from "../tiempo-real/useComandoEnCurso";
import type { AlertaSonora } from "../tiempo-real/useAlertaSonora";
import { Odometro } from "./Odometro";
import { Boton } from "./ui/Boton";

const DE_SENSOR = new Set<Alarma["tipo"]>([
  "INTRUSION",
  "SIN_MOVIMIENTO",
  "AGUA",
  "GAS",
  "TEMPERATURA",
]);

export interface CampoAlarmasProps {
  casaId: number;
  /** Los nodos con alguna alarma sonando (al ≠ 0), en el orden de la casa. */
  nodos: NodoCentral[];
  abiertas: Alarma[];
  /** Segundos desde que llegó el estado: la duración avanza con el reloj del celular. */
  desdeLlegadaS: number;
  centralEnLinea: boolean;
  sonido: AlertaSonora;
}

/** La alarma abierta más antigua del nodo: de ella salen el "desde" y la duración. */
function primeraAbierta(abiertas: Alarma[], nodoId: number): Alarma | undefined {
  return abiertas.find((a) => a.nodo_id === nodoId && DE_SENSOR.has(a.tipo));
}

function BotonSonido({ sonido }: { sonido: AlertaSonora }) {
  if (!sonido.soportada) return null;
  return sonido.activa ? (
    <Boton
      variante="contorno-alarma"
      tamano="compacto"
      onClick={sonido.apagar}
      icono={<VolumeOff aria-hidden="true" className="size-4" />}
    >
      Apagar sonido
    </Boton>
  ) : (
    <Boton
      variante="contorno-alarma"
      tamano="compacto"
      onClick={sonido.activar}
      icono={<Volume2 aria-hidden="true" className="size-4" />}
    >
      Activar sonido
    </Boton>
  );
}

function useSilencio(casaId: number, nodoId: number) {
  const comando = useComandoEnCurso(casaId, false);
  return {
    enviando: comando.enviando,
    silenciar: () =>
      comando.enviar(() => pedirComando(casaId, { nodo: nodoId, accion: "silenciar" }), true),
  };
}

interface AlarmaDeNodoProps {
  casaId: number;
  nodo: NodoCentral;
  alarma: Alarma | undefined;
  desdeLlegadaS: number;
  puedeSilenciar: boolean;
}

function AlarmaUnica({ casaId, nodo, alarma, desdeLlegadaS, puedeSilenciar }: AlarmaDeNodoProps) {
  const silencio = useSilencio(casaId, nodo.id);
  return (
    <div className="mt-3">
      <p className="text-lg leading-6 font-medium">{textosAlarma(nodo).join(" · ")}</p>
      {alarma && (
        <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <Odometro
            texto={reloj(alarma.duracion_s + desdeLlegadaS)}
            className="text-monumental font-semibold"
          />
          <span className="text-sm text-sobre-alarma-2">
            sonando desde las <span className="cifras">{hora(alarma.inicio_en)}</span>
          </span>
        </div>
      )}
      <Boton
        variante="sobre-alarma"
        tamano="grande"
        className="mt-5 w-full sm:w-auto sm:min-w-56"
        disabled={!puedeSilenciar}
        ocupado={silencio.enviando && "Silenciando…"}
        onClick={silencio.silenciar}
      >
        Silenciar
      </Boton>
    </div>
  );
}

function FilaAlarma({ casaId, nodo, alarma, desdeLlegadaS, puedeSilenciar }: AlarmaDeNodoProps) {
  const silencio = useSilencio(casaId, nodo.id);
  return (
    <li className="flex items-center gap-3 py-3">
      <div className="min-w-0 flex-1">
        <h3 className="leading-6 font-semibold">{nodo.nombre}</h3>
        <p className="text-sm text-sobre-alarma-2">
          {textosAlarma(nodo).join(" · ")}
          {alarma && (
            <>
              {" · desde "}
              <span className="cifras">{hora(alarma.inicio_en)}</span>
            </>
          )}
        </p>
      </div>
      {alarma && (
        <Odometro
          texto={reloj(alarma.duracion_s + desdeLlegadaS)}
          className="text-xl font-semibold"
        />
      )}
      <Boton
        variante="sobre-alarma"
        disabled={!puedeSilenciar}
        ocupado={silencio.enviando && "Silenciando…"}
        onClick={silencio.silenciar}
        aria-label={`Silenciar ${nodo.nombre}`}
      >
        Silenciar
      </Boton>
    </li>
  );
}

function SilenciarTodas({ casaId, puedeSilenciar }: { casaId: number; puedeSilenciar: boolean }) {
  const comando = useComandoEnCurso(casaId, false);
  return (
    <Boton
      variante="sobre-alarma"
      tamano="grande"
      className="mt-4 w-full sm:w-auto sm:min-w-56"
      disabled={!puedeSilenciar}
      ocupado={comando.enviando && "Silenciando todas…"}
      onClick={() => comando.enviar(() => pedirSilenciarTodo(casaId), true)}
    >
      Silenciar todas
    </Boton>
  );
}

export function CampoAlarmas({
  casaId,
  nodos,
  abiertas,
  desdeLlegadaS,
  centralEnLinea,
  sonido,
}: CampoAlarmasProps) {
  const unica = nodos.length === 1 ? nodos[0] : undefined;
  const puede = (nodo: NodoCentral) => centralEnLinea && nodo.enLinea;

  return (
    <section
      aria-labelledby="campo-alarmas"
      className="aparece -mx-4 bg-alarma-campo px-4 pt-3 pb-5 text-sobre-alarma sm:mx-0 sm:rounded-[10px] sm:px-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <h2 id="campo-alarmas" className="flex items-center gap-2.5 text-lg font-semibold">
          <span
            aria-hidden="true"
            className="size-2.5 rounded-full bg-sobre-alarma motion-safe:animate-latido"
          />
          {unica ? `Alarma · ${unica.nombre}` : `${nodos.length} alarmas`}
        </h2>
        <BotonSonido sonido={sonido} />
      </div>

      {unica ? (
        <AlarmaUnica
          casaId={casaId}
          nodo={unica}
          alarma={primeraAbierta(abiertas, unica.id)}
          desdeLlegadaS={desdeLlegadaS}
          puedeSilenciar={puede(unica)}
        />
      ) : (
        <>
          <ul className="mt-3 divide-y divide-sobre-alarma/25 border-y border-sobre-alarma/25">
            {nodos.map((nodo) => (
              <FilaAlarma
                key={nodo.id}
                casaId={casaId}
                nodo={nodo}
                alarma={primeraAbierta(abiertas, nodo.id)}
                desdeLlegadaS={desdeLlegadaS}
                puedeSilenciar={puede(nodo)}
              />
            ))}
          </ul>
          <SilenciarTodas casaId={casaId} puedeSilenciar={centralEnLinea} />
        </>
      )}

      {!centralEnLinea && (
        <p className="mt-3 text-sm text-sobre-alarma-2">
          La central está desconectada: no se puede silenciar desde aquí.
        </p>
      )}
    </section>
  );
}
