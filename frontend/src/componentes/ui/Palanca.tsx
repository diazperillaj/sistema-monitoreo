/**
 * Interruptor accesible (Radix Switch) con forma de palanca de breaker: pista sin relleno y un
 * mando de grafito con su muesca. Encendida, el mando va a la derecha y se ve el piloto verde en
 * la ranura; apagada, el mando gris queda a la izquierda. "Enviando" es la palanca a medio camino,
 * esperando a la central.
 */
import * as Switch from "@radix-ui/react-switch";
import { cn } from "../../lib/utils";

export interface PalancaProps {
  activa: boolean;
  alCambiar: (activa: boolean) => void;
  etiqueta: string;
  enviando?: boolean;
  deshabilitada?: boolean;
  id?: string;
}

export function Palanca({
  activa,
  alCambiar,
  etiqueta,
  enviando = false,
  deshabilitada = false,
  id,
}: PalancaProps) {
  return (
    <Switch.Root
      id={id}
      checked={activa}
      onCheckedChange={alCambiar}
      disabled={deshabilitada || enviando}
      aria-label={etiqueta}
      aria-busy={enviando || undefined}
      data-enviando={enviando || undefined}
      className={cn(
        "group relative inline-flex h-8 w-[3.25rem] shrink-0 items-center rounded-[6px] p-[3px]",
        "bg-cara-2 ring-1 ring-filo ring-inset transition-shadow duration-150",
        "data-[state=checked]:ring-tinta-3",
        "disabled:cursor-not-allowed disabled:opacity-50 data-[enviando]:opacity-100",
        "before:absolute before:-inset-2 before:content-['']", // zona táctil de 48 px
      )}
    >
      {/* El piloto: una ranura verde que solo se ve con la palanca encendida */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 left-[9px] h-3 w-[3px] -translate-y-1/2 rounded-full bg-verdin opacity-0 transition-opacity duration-150 group-data-[state=checked]:opacity-100 group-data-[enviando]:opacity-0"
      />
      <Switch.Thumb
        className={cn(
          "relative block size-[1.625rem] rounded-[4px] bg-tinta-3 shadow-[0_1px_2px_rgb(var(--sombra)/0.35)]",
          "transition-[transform,background-color] duration-200 ease-[var(--ease-salida)]",
          "data-[state=checked]:translate-x-[1.25rem] data-[state=checked]:bg-tinta",
          "group-data-[enviando]:translate-x-[0.625rem] group-data-[enviando]:animate-pulse",
          // La muesca del mando, como en un breaker
          "after:absolute after:inset-x-[7px] after:top-1/2 after:h-px after:-translate-y-1/2 after:bg-cara/60 after:content-['']",
        )}
      />
    </Switch.Root>
  );
}
