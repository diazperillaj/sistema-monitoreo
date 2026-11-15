/**
 * El botón de la barra superior: pasa de claro a oscuro y al revés, en este dispositivo.
 * Muestra lo que se va a poner (la luna de día, el sol de noche). "Automático" está en el perfil.
 */
import { Moon, Sun } from "lucide-react";
import { fijarTema, useTema } from "../lib/tema";

export function BotonTema() {
  const { tema } = useTema();
  const aOscuro = tema === "claro";
  const Icono = aOscuro ? Moon : Sun;
  const texto = aOscuro ? "Cambiar a modo oscuro" : "Cambiar a modo claro";
  return (
    <button
      type="button"
      onClick={() => fijarTema(aOscuro ? "oscuro" : "claro")}
      aria-label={texto}
      title={texto}
      className="pulsable grid size-11 shrink-0 place-items-center rounded-[6px] text-tinta-2 hover:bg-cara-2 hover:text-tinta"
    >
      <Icono aria-hidden="true" className="size-5" />
    </button>
  );
}
