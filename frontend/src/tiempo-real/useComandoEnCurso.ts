/**
 * Un comando desde el toque hasta la central (§11.3). Mientras no se resuelve, el control dice
 * "enviando…". Si se confirma, el control queda en el valor nuevo. Si no se confirma, vuelve al
 * valor real y avisa. Un 409 (central o nodo sin conexión) muestra el mensaje de la API.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { mensajeDe } from "../api/cliente";
import { guardarComando, useComando, type Comando } from "../api/consultas";
import { useAhora } from "./useAhora";

/** El WS avisa "confirmado" un instante antes de mandar el estado con el valor nuevo (§9). */
const GRACIA_MS = 3000;

export interface ComandoEnCurso<T> {
  enviar: (peticion: () => Promise<Comando>, objetivo: T) => void;
  enviando: boolean;
  /** Lo que el control muestra: el objetivo mientras espera a la central; si no, el valor real. */
  valor: T;
}

interface Orden<T> {
  id: number;
  objetivo: T;
}

export function useComandoEnCurso<T>(casaId: number, real: T): ComandoEnCurso<T> {
  const cliente = useQueryClient();
  const [orden, setOrden] = useState<Orden<T> | null>(null);
  const envio = useMutation({
    mutationFn: ({ peticion }: { peticion: () => Promise<Comando>; objetivo: T }) => peticion(),
    onSuccess: (comando, { objetivo }) => {
      guardarComando(cliente, comando);
      setOrden({ id: comando.id, objetivo });
    },
    onError: (error) => {
      toast.error(mensajeDe(error));
    },
  });
  const seguimiento = useComando(casaId, orden?.id ?? null);
  const ahora = useAhora();

  const estado = seguimiento.data?.estado;
  const cumplida = orden !== null && Object.is(real, orden.objetivo);
  const esperando =
    orden !== null &&
    !cumplida &&
    (estado === undefined ||
      estado === "pendiente" ||
      (estado === "confirmado" && ahora - seguimiento.dataUpdatedAt < GRACIA_MS));

  const ordenId = orden?.id;
  useEffect(() => {
    if (estado !== "sin_confirmar" || ordenId === undefined) return;
    toast.error("La central no confirmó el cambio", {
      id: `sin-confirmar-${ordenId}`,
      description:
        "Todo quedó como estaba. Puede que el nodo o la central estén sin conexión: vuelve a probar en un momento.",
    });
  }, [estado, ordenId]);

  const enviando = envio.isPending || esperando;
  return {
    enviar: (peticion, objetivo) => envio.mutate({ peticion, objetivo }),
    enviando,
    valor: esperando && orden ? orden.objetivo : real,
  };
}
