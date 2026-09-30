/**
 * En iPhone y iPad las notificaciones solo llegan con la app instalada en la pantalla de inicio
 * (iOS 16.4 o más reciente, §10.5). Estos son los tres pasos, con los íconos que se ven en Safari.
 */
import { Share, SquarePlus, BellRing } from "lucide-react";

const PASOS = [
  {
    Icono: Share,
    texto: "En Safari, toca el botón Compartir (abajo en el iPhone, arriba en el iPad).",
  },
  { Icono: SquarePlus, texto: "Elige “Agregar a inicio” y confirma con “Agregar”." },
  {
    Icono: BellRing,
    texto: "Abre la app desde el ícono nuevo, entra a Perfil y activa las notificaciones.",
  },
];

export function GuiaInstalacionIOS() {
  return (
    <div className="space-y-3">
      <p className="font-medium">Para recibir alertas en este iPhone, primero instala la app:</p>
      <ol className="space-y-2.5">
        {PASOS.map(({ Icono, texto }, i) => (
          <li key={i} className="flex items-start gap-3">
            <span className="cifras grid size-7 shrink-0 place-items-center rounded-[6px] bg-cara-2 text-sm font-semibold ring-1 ring-filo ring-inset">
              {i + 1}
            </span>
            <span className="flex-1 pt-0.5 text-tinta-2">
              <Icono aria-hidden="true" className="mr-1.5 inline size-4 align-[-2px] text-tinta" />
              {texto}
            </span>
          </li>
        ))}
      </ol>
      <p className="text-sm text-tinta-3">Necesita iOS 16.4 o más reciente.</p>
    </div>
  );
}
