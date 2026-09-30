/**
 * Botones del tablero. Esquinas cortas (6 px), como las teclas de un aparato, y respuesta al
 * presionar, no al soltar. Cada botón nombra su acción; mientras trabaja dice qué está haciendo.
 */
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/utils";

type Variante = "primario" | "secundario" | "sobre-alarma" | "contorno-alarma" | "discreto";
type Tamano = "normal" | "grande" | "compacto";

const VARIANTES: Record<Variante, string> = {
  primario: "bg-tinta text-cara hover:bg-tinta/90",
  secundario: "bg-cara text-tinta ring-1 ring-inset ring-filo hover:bg-cara-2",
  "sobre-alarma": "bg-sobre-alarma text-alarma-campo hover:bg-sobre-alarma/90",
  "contorno-alarma":
    "bg-transparent text-sobre-alarma ring-1 ring-inset ring-sobre-alarma/55 hover:bg-sobre-alarma/10",
  discreto: "bg-transparent text-tinta-2 hover:bg-cara-2 hover:text-tinta",
};

const TAMANOS: Record<Tamano, string> = {
  compacto: "h-11 px-3 text-sm", // angosto, pero con los 44 px táctiles
  normal: "h-11 px-4 text-base",
  grande: "h-14 px-6 text-lg",
};

export interface BotonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamano?: Tamano;
  /** Texto mientras trabaja: "Silenciando…". El botón queda deshabilitado. */
  ocupado?: string | false;
  icono?: ReactNode;
}

export function Boton({
  variante = "primario",
  tamano = "normal",
  ocupado = false,
  icono,
  className,
  children,
  disabled,
  type = "button",
  ...resto
}: BotonProps) {
  return (
    <button
      type={type}
      disabled={disabled || !!ocupado}
      aria-busy={ocupado ? true : undefined}
      className={cn(
        "pulsable inline-flex items-center justify-center gap-2 rounded-[6px] font-semibold whitespace-nowrap",
        "disabled:cursor-not-allowed disabled:opacity-55",
        VARIANTES[variante],
        TAMANOS[tamano],
        className,
      )}
      {...resto}
    >
      {icono}
      <span>{ocupado || children}</span>
    </button>
  );
}
