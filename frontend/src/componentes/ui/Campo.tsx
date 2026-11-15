/**
 * Un campo de formulario: rótulo arriba, ayuda y error abajo. El error va en tinta con su ícono,
 * no en rojo: en esta app el rojo es solo de alarma.
 */
import { CircleAlert, Eye, EyeOff } from "lucide-react";
import { useId, useState, type InputHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export interface CampoProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  etiqueta: string;
  ayuda?: string;
  error?: string | null;
  /** Para claves: agrega el botón de mostrar u ocultar. */
  clave?: boolean;
}

export function Campo({
  etiqueta,
  ayuda,
  error,
  clave = false,
  className,
  type,
  ...resto
}: CampoProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const idAyuda = ayuda ? `${id}-ayuda` : undefined;
  const idError = error ? `${id}-error` : undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium">
        {etiqueta}
      </label>
      <div className="relative">
        <input
          id={id}
          type={clave ? (visible ? "text" : "password") : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={[idAyuda, idError].filter(Boolean).join(" ") || undefined}
          className={cn(
            "h-12 w-full rounded-[6px] bg-cara px-3 text-tinta ring-1 ring-filo ring-inset",
            "transition-shadow duration-150 placeholder:text-tinta-3",
            "focus-visible:ring-2 focus-visible:ring-tinta focus-visible:outline-none",
            "aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-tinta-2",
            "disabled:opacity-55",
            clave && "pr-12",
          )}
          {...resto}
        />
        {clave && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? "Ocultar clave" : "Mostrar clave"}
            aria-pressed={visible}
            className="absolute inset-y-0 right-0 grid w-12 place-items-center rounded-r-[6px] text-tinta-3 hover:text-tinta"
          >
            {visible ? (
              <EyeOff aria-hidden="true" className="size-5" />
            ) : (
              <Eye aria-hidden="true" className="size-5" />
            )}
          </button>
        )}
      </div>
      {ayuda && (
        <p id={idAyuda} className="text-sm text-tinta-3">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={idError} className="flex items-start gap-1.5 text-sm font-medium text-tinta">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}
