/**
 * El WebSocket de una casa (§9, §11.3): cada mensaje actualiza la caché de TanStack Query.
 * Reconecta a los 1, 2, 5, 10 y 30 s; tras 3 fallos seguidos pide el estado cada 5 s mientras
 * sigue intentando. 4401 lleva al login y 4403 corta sin reintentar.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useEffectEvent, useState } from "react";
import { claves, type Comando, type EstadoCasa } from "../api/consultas";

export type Conexion = "conectando" | "en_vivo" | "reconectando" | "respaldo" | "sin_acceso";

const ESPERAS_S = [1, 2, 5, 10, 30];
const FALLOS_PARA_RESPALDO = 3;
const PING_CADA_MS = 25_000;

type Mensaje =
  | { tipo: "estado"; data: EstadoCasa }
  | { tipo: "central"; online: boolean; cambio_en: string }
  | { tipo: "alarma"; evento: "abre" | "cierra"; data: { nodo_id: number | null; tipo: string } }
  | { tipo: "evento"; data: unknown }
  | { tipo: "comando"; data: Comando }
  | { tipo: "pong" };

export interface OpcionesEnVivo {
  /** Se llama cuando se abre una alarma de sensor (para el pitido y la vibración). */
  alAbrirAlarma?: () => void;
}

export function direccionWs(casaId: number, lugar: Location = window.location): string {
  const protocolo = lugar.protocol === "https:" ? "wss:" : "ws:";
  return `${protocolo}//${lugar.host}/ws/v1/casas/${casaId}`;
}

/** Sin casa (una cuenta sin casas) no abre nada. */
export function useCasaEnVivo(casaId: number | null, opciones: OpcionesEnVivo = {}): Conexion {
  const cliente = useQueryClient();
  const [conexion, setConexion] = useState<Conexion>("conectando");
  const [casaDeLaConexion, setCasaDeLaConexion] = useState(casaId);
  const alAbrirAlarma = useEffectEvent(() => opciones.alAbrirAlarma?.());

  // Otra casa: la conexión anterior no dice nada de esta
  if (casaId !== casaDeLaConexion) {
    setCasaDeLaConexion(casaId);
    setConexion("conectando");
  }

  useEffect(() => {
    if (casaId === null) return;
    const casa = casaId;
    let ws: WebSocket | null = null;
    let fallos = 0;
    let terminado = false;
    let reintento: ReturnType<typeof setTimeout> | undefined;
    let ping: ReturnType<typeof setInterval> | undefined;

    function recibir(evento: MessageEvent<string>) {
      let mensaje: Mensaje;
      try {
        mensaje = JSON.parse(evento.data) as Mensaje;
      } catch {
        return;
      }
      switch (mensaje.tipo) {
        case "estado":
          cliente.setQueryData(claves.estado(casa), mensaje.data);
          break;
        case "central":
          cliente.setQueryData<EstadoCasa>(claves.estado(casa), (previo) =>
            previo
              ? { ...previo, online: mensaje.online, online_cambio_en: mensaje.cambio_en }
              : previo,
          );
          break;
        case "alarma":
          void cliente.invalidateQueries({ queryKey: claves.alarmas(casa) });
          if (mensaje.evento === "abre" && mensaje.data.nodo_id !== null) {
            const deSensor = !["NODO_SIN_CONEXION", "CENTRAL_DESCONECTADA"].includes(
              mensaje.data.tipo,
            );
            if (deSensor) alAbrirAlarma();
          }
          break;
        case "evento":
          void cliente.invalidateQueries({ queryKey: claves.eventos(casa) });
          break;
        case "comando":
          cliente.setQueryData(claves.comando(mensaje.data.id), mensaje.data);
          break;
      }
    }

    function programarReintento() {
      fallos += 1;
      setConexion(fallos >= FALLOS_PARA_RESPALDO ? "respaldo" : "reconectando");
      const espera = ESPERAS_S[Math.min(fallos - 1, ESPERAS_S.length - 1)];
      reintento = setTimeout(conectar, espera * 1000);
    }

    function conectar() {
      if (terminado) return;
      clearTimeout(reintento);
      ws = new WebSocket(direccionWs(casa));
      ws.onopen = () => {
        fallos = 0;
        setConexion("en_vivo");
        ping = setInterval(() => ws?.send(JSON.stringify({ tipo: "ping" })), PING_CADA_MS);
      };
      ws.onmessage = recibir;
      ws.onclose = (evento) => {
        clearInterval(ping);
        ws = null;
        if (terminado) return;
        if (evento.code === 4401) {
          terminado = true;
          cliente.setQueryData(claves.yo, null); // la guarda de sesión lleva al login
          return;
        }
        if (evento.code === 4403) {
          terminado = true;
          setConexion("sin_acceso");
          return;
        }
        programarReintento();
      };
    }

    // Al volver a la app (celular desbloqueado) o al recuperar internet, reconecta ya
    function reintentarAhora() {
      if (!terminado && ws === null && document.visibilityState === "visible") {
        clearTimeout(reintento);
        conectar();
      }
    }

    conectar();
    document.addEventListener("visibilitychange", reintentarAhora);
    window.addEventListener("online", reintentarAhora);
    return () => {
      terminado = true;
      clearTimeout(reintento);
      clearInterval(ping);
      document.removeEventListener("visibilitychange", reintentarAhora);
      window.removeEventListener("online", reintentarAhora);
      ws?.close(1000);
    };
  }, [casaId, cliente]);

  return conexion;
}
