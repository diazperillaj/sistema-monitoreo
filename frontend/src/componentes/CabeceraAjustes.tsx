/**
 * Cabecera de los ajustes de la casa (solo admin): título y dos pestañas con su propia URL,
 * /ajustes (avisos) y /miembros (§11.2). Se ven como las pestañas del historial.
 */
import { NavLink } from "react-router";
import { cn } from "../lib/utils";

const PESTANA =
  "pulsable grid h-11 place-items-center rounded-[6px] text-sm font-semibold text-tinta-2";
const ACTIVA =
  "bg-cara text-tinta shadow-[0_0_0_1px_var(--filo),0_1px_2px_rgb(var(--sombra)/0.12)]";

export function CabeceraAjustes({ casaId }: { casaId: number }) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Ajustes de la casa</h1>
      <nav
        aria-label="Ajustes"
        className="grid grid-cols-2 gap-1 rounded-[8px] bg-cara-2 p-1 ring-1 ring-filo ring-inset"
      >
        <NavLink
          to={`/casa/${casaId}/ajustes`}
          className={({ isActive }) => cn(PESTANA, isActive && ACTIVA)}
        >
          Avisos
        </NavLink>
        <NavLink
          to={`/casa/${casaId}/miembros`}
          className={({ isActive }) => cn(PESTANA, isActive && ACTIVA)}
        >
          Miembros
        </NavLink>
      </nav>
    </div>
  );
}
