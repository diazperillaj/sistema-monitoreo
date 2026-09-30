/**
 * El interruptor de un nodo (§11.4): manda activar o desactivar y espera a la central.
 * Mientras espera, la palanca queda a medio camino y dice "Enviando…".
 */
import { pedirComando } from "../api/consultas";
import type { Interruptor } from "../dominio/instrumento";
import { useComandoEnCurso } from "../tiempo-real/useComandoEnCurso";
import { Palanca } from "./ui/Palanca";

export interface InterruptorNodoProps {
  casaId: number;
  nodo: number;
  interruptor: Interruptor;
  deshabilitado?: boolean;
  /** Muestra el nombre del interruptor junto a la palanca (el del nodo 4, "Presencia"). */
  conRotulo?: boolean;
}

export function InterruptorNodo({
  casaId,
  nodo,
  interruptor,
  deshabilitado = false,
  conRotulo = false,
}: InterruptorNodoProps) {
  const comando = useComandoEnCurso(casaId, interruptor.activo);
  const id = `interruptor-${nodo}-${interruptor.sub}`;

  return (
    <div className="flex min-h-11 items-center justify-end gap-3">
      {conRotulo && (
        <label htmlFor={id} className="rotulo mr-auto">
          {interruptor.etiqueta}
        </label>
      )}
      <span aria-live="polite" className="text-xs text-tinta-3">
        {comando.enviando ? "Enviando…" : ""}
      </span>
      <Palanca
        id={id}
        etiqueta={interruptor.etiqueta}
        activa={comando.valor}
        enviando={comando.enviando}
        deshabilitada={deshabilitado}
        alCambiar={(activa) =>
          comando.enviar(
            () =>
              pedirComando(casaId, {
                nodo,
                accion: activa ? "activar" : "desactivar",
                sub: interruptor.sub,
              }),
            activa,
          )
        }
      />
    </div>
  );
}
