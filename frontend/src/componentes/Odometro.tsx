/**
 * Cifras de odómetro: cada dígito es una rueda que gira al cambiar, como en un contador de agua.
 * Al volver a cero, todas las ruedas regresan juntas. Con "reducir movimiento" solo cambian.
 * El texto se lee una sola vez, para el lector de pantalla, en un span aparte.
 */
import { cn } from "../lib/utils";

const DIGITOS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

function Rueda({ digito }: { digito: number }) {
  return (
    <span className="relative inline-block">
      {/* Un dígito invisible da el tamaño y la línea base; la rueda gira encima. La ventana se
          recorta a la franja de la cifra (de 0,19 a 0,91 em en Barlow Semi Condensed, con
          interlineado 1): a mitad del giro nada asoma por encima ni por debajo del número */}
      <span className="invisible">0</span>
      <span className="absolute inset-0 overflow-hidden [clip-path:inset(0.17em_0_0.07em_0)] contain-paint">
        <span
          className="absolute inset-x-0 top-0 flex flex-col transition-transform duration-200 ease-[var(--ease-salida)]"
          style={{ transform: `translateY(calc(-1lh * ${digito}))` }}
        >
          {DIGITOS.map((d) => (
            <span key={d} className="block h-[1lh]">
              {d}
            </span>
          ))}
        </span>
      </span>
    </span>
  );
}

export function Odometro({ texto, className }: { texto: string; className?: string }) {
  const caracteres = texto.split("");
  return (
    // Interlineado 1: la ventana de cada rueda mide lo que mide la cifra, y a mitad del giro
    // las dos mitades quedan dentro de la franja del número
    <span className={cn("cifras whitespace-nowrap leading-none", className)}>
      <span className="sr-only">{texto}</span>
      <span aria-hidden="true">
        {caracteres.map((c, i) => {
          // La clave va desde la derecha: las unidades siguen siendo la misma rueda aunque
          // el texto crezca ("59:59" → "1:00:00")
          const clave = caracteres.length - i;
          return /\d/.test(c) ? (
            <Rueda key={clave} digito={Number(c)} />
          ) : (
            <span key={clave}>{c}</span>
          );
        })}
      </span>
    </span>
  );
}
