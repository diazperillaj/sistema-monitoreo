/**
 * Confirmación antes de algo que no se deshace solo (quitar a alguien de la casa). Radix Dialog:
 * foco atrapado, Escape cierra y el foco vuelve al botón que la abrió.
 */
import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";
import { Boton } from "./Boton";

export interface ConfirmarProps {
  abierto: boolean;
  alCambiar: (abierto: boolean) => void;
  titulo: string;
  descripcion: ReactNode;
  accion: string;
  ocupado?: string | false;
  alConfirmar: () => void;
}

export function Confirmar({
  abierto,
  alCambiar,
  titulo,
  descripcion,
  accion,
  ocupado = false,
  alConfirmar,
}: ConfirmarProps) {
  return (
    <Dialog.Root open={abierto} onOpenChange={alCambiar}>
      <Dialog.Portal>
        <Dialog.Overlay className="aparece fixed inset-0 z-40 bg-tinta/30" />
        <Dialog.Content className="aparece placa fixed inset-x-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-50 mx-auto max-w-sm space-y-3 rounded-[10px] p-5 sm:top-1/2 sm:bottom-auto sm:-translate-y-1/2">
          <Dialog.Title className="text-lg font-semibold">{titulo}</Dialog.Title>
          <Dialog.Description className="text-tinta-2">{descripcion}</Dialog.Description>
          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <Dialog.Close asChild>
              <Boton variante="discreto">Cancelar</Boton>
            </Dialog.Close>
            <Boton ocupado={ocupado} onClick={alConfirmar}>
              {accion}
            </Boton>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
