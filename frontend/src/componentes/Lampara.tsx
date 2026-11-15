/**
 * La luz piloto de cada instrumento, como la de un breaker. El color nunca va solo: siempre la
 * acompaña una palabra ("Vigilando", "ALARMA", "Sin conexión").
 * Verde: vigila. Roja y latiendo: alarma. Anillo oscuro: no se sabe bien. Anillo tenue: apagada.
 */
import { cn } from "../lib/utils";

export type Luz = "vigilando" | "alarma" | "incierta" | "apagada";

const LUCES: Record<Luz, string> = {
  vigilando: "bg-verdin",
  alarma: "bg-alarma",
  incierta: "bg-transparent ring-2 ring-inset ring-tinta-2",
  apagada: "bg-transparent ring-1 ring-inset ring-marca",
};

/** `fija`: en el historial la alarma es un registro, no algo que está pasando: no late. */
export function Lampara({
  luz,
  fija = false,
  className,
}: {
  luz: Luz;
  fija?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      data-luz={luz}
      className={cn(
        "inline-block size-2.5 shrink-0 rounded-full",
        LUCES[luz],
        luz === "alarma" && !fija && "motion-safe:animate-latido",
        className,
      )}
    />
  );
}
