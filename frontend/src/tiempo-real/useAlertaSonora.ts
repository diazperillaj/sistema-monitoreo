/**
 * Alertas en primer plano (§11.6): con la app abierta, un pitido y una vibración cada segundo
 * mientras haya alarmas. El navegador exige un toque para permitir el sonido, como en la app
 * local de la central (mismo tono: 880 Hz).
 */
import { useCallback, useEffect, useRef, useState } from "react";

type ContextoAudio = typeof AudioContext;

function contextoDeAudio(): ContextoAudio | undefined {
  if (typeof window === "undefined") return undefined;
  return (
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: ContextoAudio }).webkitAudioContext
  );
}

function pitido(audio: AudioContext, duracion: number) {
  const oscilador = audio.createOscillator();
  const volumen = audio.createGain();
  oscilador.type = "square";
  oscilador.frequency.value = 880;
  volumen.gain.value = 0.15;
  oscilador.connect(volumen);
  volumen.connect(audio.destination);
  oscilador.start();
  oscilador.stop(audio.currentTime + duracion);
}

export interface AlertaSonora {
  soportada: boolean;
  activa: boolean;
  activar: () => void; // llamarla desde un toque del usuario
  apagar: () => void;
  avisar: () => void; // un pitido corto, para una alarma recién abierta
}

export function useAlertaSonora(hayAlarmas: boolean): AlertaSonora {
  const [activa, setActiva] = useState(false);
  const audio = useRef<AudioContext | null>(null);
  const Contexto = contextoDeAudio();

  const activar = useCallback(() => {
    if (!Contexto) return;
    audio.current ??= new Contexto();
    void audio.current.resume();
    setActiva(true);
    pitido(audio.current, 0.12);
  }, [Contexto]);

  const apagar = useCallback(() => setActiva(false), []);

  // Sonido y vibración van juntos: los dos esperan el toque del usuario (el navegador bloquea
  // la vibración sin él)
  const avisar = useCallback(() => {
    if (!activa || !audio.current) return;
    pitido(audio.current, 0.2);
    navigator.vibrate?.([400, 200, 400]);
  }, [activa]);

  useEffect(() => {
    if (!hayAlarmas || !activa) return;
    const repetir = setInterval(() => {
      if (audio.current) pitido(audio.current, 0.4);
      navigator.vibrate?.(400);
    }, 1000);
    return () => clearInterval(repetir);
  }, [hayAlarmas, activa]);

  return { soportada: !!Contexto, activa, activar, apagar, avisar };
}
