/**
 * Lo último que anotó la central en su bitácora (hasta 15 eventos, el más reciente primero,
 * §4.3): conexiones, alarmas y silencios, con la hora de la central. El historial completo
 * está en su pantalla.
 */
import { Link } from "react-router";
import type { EstadoCentral } from "../dominio/protocolo";
import { cn } from "../lib/utils";
import { Lampara } from "./Lampara";

const CUANTOS = 8;

/** La luz roja ya dice que es una alarma: "ALARMA Baño: …" se lee "Baño: …". */
function sinPrefijo(texto: string): string {
  return texto.replace(/^ALARMA\s+/, "");
}

/** "27/09 14:04:58" → "14:04". Sin hora válida la central anota "+<s>s": va tal cual. */
function horaDe(t: string): string {
  return /(\d{2}:\d{2}):\d{2}$/.exec(t)?.[1] ?? t;
}

export function BitacoraCentral({ central }: { central: EstadoCentral }) {
  const eventos = central.eventos.slice(0, CUANTOS);
  if (eventos.length === 0) return null;
  return (
    <section aria-labelledby="titulo-bitacora" className="placa rounded-[10px] px-4 pt-3 pb-2">
      <h2 id="titulo-bitacora" className="font-semibold">
        Lo último en la central
      </h2>
      <ol className="mt-2 divide-y divide-filo">
        {eventos.map((evento, i) => (
          <li key={`${evento.t}-${i}`} className="flex items-baseline gap-3 py-2 text-sm">
            <span className="cifras w-11 shrink-0 text-tinta-3">{horaDe(evento.t)}</span>
            <span className="flex min-w-0 flex-1 items-baseline gap-2">
              {evento.a && <Lampara luz="alarma" fija className="translate-y-px" />}
              <span className={cn("text-pretty", evento.a ? "font-medium" : "text-tinta-2")}>
                {evento.a ? sinPrefijo(evento.x) : evento.x}
              </span>
            </span>
          </li>
        ))}
      </ol>
      <Link
        to="historial"
        className="flex min-h-11 items-center text-sm font-semibold underline-offset-4 hover:underline"
      >
        Ver el historial completo
      </Link>
    </section>
  );
}
