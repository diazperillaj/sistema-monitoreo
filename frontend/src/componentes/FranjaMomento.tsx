/**
 * La franja del momento: qué vigila la casa a esta hora (madrugada, noche o día), según las
 * banderas de la central y con su reloj, no con el del celular.
 */
import { ClockAlert, Moon, MoonStar, Sun, type LucideIcon } from "lucide-react";
import { franja, type Momento } from "../dominio/momento";
import type { EstadoCentral } from "../dominio/protocolo";
import { cn } from "../lib/utils";

const ICONO: Record<Momento, LucideIcon> = {
  madrugada: MoonStar,
  noche: Moon,
  dia: Sun,
  sin_hora: ClockAlert,
};

/** "27/09/2026 14:05:10" → "14:05". Sin hora válida la central manda "+<s>s". */
function horaDeLaCentral(texto: string): string | null {
  return /\b(\d{2}:\d{2}):\d{2}$/.exec(texto)?.[1] ?? null;
}

export function FranjaMomento({ central, vivo }: { central: EstadoCentral; vivo: boolean }) {
  const { momento, texto } = franja(central);
  const Icono = ICONO[momento];
  const horaCentral = central.horaValida && vivo ? horaDeLaCentral(central.hora) : null;

  return (
    <div
      data-momento={momento}
      className={cn(
        "flex items-start gap-2.5 text-sm leading-5",
        momento === "sin_hora" ? "font-medium text-tinta" : "text-tinta-2",
      )}
    >
      <Icono aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <p className="min-w-0 flex-1">{texto}</p>
      {horaCentral && (
        <p className="cifras shrink-0 text-tinta-3">
          <span className="sr-only">Hora de la central: </span>
          {horaCentral}
        </p>
      )}
    </div>
  );
}
