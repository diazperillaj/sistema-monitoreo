/**
 * Escala calibrada de un contador: cuánto falta para la alarma, no solo si sonó.
 * Veinte marcas finas y tres escalones (25, 50 y 75 %) que se encienden al cruzarlos; el último
 * tramo en ámbar y el límite en rojo. Una aguja de tinta marca la lectura: avanza al ritmo del
 * reloj y, al reiniciarse el contador (silencio, movimiento), vuelve a cero rápido, como un
 * contador mecánico. La lectura va en cifras de odómetro.
 */
import { useState } from "react";
import type { Escala as ModeloEscala } from "../dominio/instrumento";
import { mmss } from "../dominio/textos";
import { duracion } from "../dominio/tiempo";
import { cn } from "../lib/utils";
import { Odometro } from "./Odometro";

const TRAMOS = 20;
const MARCAS = Array.from({ length: TRAMOS - 1 }, (_, i) => (i + 1) / TRAMOS);
const esEscalon = (posicion: number) =>
  [0.25, 0.5, 0.75].some((e) => Math.abs(e - posicion) < 1e-9);

export interface EscalaProps {
  escala: ModeloEscala;
  lectura: number; // segundos, ya interpolados
  quieta?: boolean; // sin datos al día: la escala se ve, pero no mide
}

export function Escala({ escala, lectura, quieta = false }: EscalaProps) {
  const limite = Math.max(1, escala.limite);
  const midiendo = !quieta && (escala.contando || escala.enAlarma);
  const fraccion = midiendo ? Math.min(1, Math.max(0, lectura / limite)) : 0;
  const tramo =
    midiendo && (escala.enAlarma || fraccion >= 1)
      ? "limite"
      : fraccion >= 0.75
        ? "ultimo"
        : "normal";

  // Subir es lineal, al ritmo del reloj; bajar es un regreso corto a cero
  const [anterior, setAnterior] = useState(fraccion);
  const [bajando, setBajando] = useState(false);
  if (fraccion !== anterior) {
    setBajando(fraccion < anterior);
    setAnterior(fraccion);
  }
  const movimiento = bajando
    ? "duration-300 ease-[var(--ease-salida)]"
    : "duration-1000 ease-linear";

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="rotulo">{escala.etiqueta}</span>
        {midiendo ? (
          <span className="whitespace-nowrap">
            <Odometro
              texto={mmss(lectura)}
              className={cn(
                "text-xl font-semibold",
                tramo === "limite" && "text-alarma",
                tramo === "ultimo" && "text-ambar-tinta",
              )}
            />
            <span className="cifras text-sm text-tinta-3"> / {mmss(limite)}</span>
          </span>
        ) : (
          <span className="text-right text-sm leading-7 text-tinta-3">
            {quieta ? "Sin medir" : escala.enReposo}
          </span>
        )}
      </div>

      <div
        role="meter"
        aria-label={escala.etiqueta}
        aria-valuemin={0}
        aria-valuemax={limite}
        aria-valuenow={Math.round(midiendo ? lectura : 0)}
        aria-valuetext={
          midiendo
            ? `${duracion(lectura)} de ${duracion(limite)}`
            : quieta
              ? "Sin medir"
              : escala.enReposo
        }
        className="relative mt-0.5 h-5"
      >
        {MARCAS.map((posicion) => {
          const escalon = esEscalon(posicion);
          return (
            <span
              key={posicion}
              aria-hidden="true"
              className={cn(
                "absolute top-0 w-px -translate-x-1/2 transition-colors duration-200",
                escalon ? "h-2" : "h-1",
                escalon && fraccion >= posicion ? "bg-tinta" : "bg-marca",
              )}
              style={{ left: `${posicion * 100}%` }}
            />
          );
        })}

        {/* La pista, con el último tramo en ámbar y el recorrido hecho en tono suave */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-2.5 h-2 overflow-hidden rounded-[2px] bg-cara-2 ring-1 ring-filo ring-inset"
        >
          <div className="absolute inset-y-0 right-0 left-3/4 bg-ambar-fondo" />
          <div
            className={cn(
              "absolute inset-y-0 left-0 w-full origin-left transition-transform",
              tramo === "limite" ? "bg-alarma" : tramo === "ultimo" ? "bg-ambar" : "bg-tinta/25",
              movimiento,
            )}
            style={{ transform: `scaleX(${fraccion})` }}
          />
        </div>

        {/* El límite: donde suena */}
        <span
          aria-hidden="true"
          className="absolute top-0 right-0 h-5 w-0.5 rounded-full bg-alarma"
        />

        {/* La aguja: una raya de tinta en la lectura, que viaja sobre la escala */}
        {midiendo && tramo !== "limite" && (
          <div
            aria-hidden="true"
            className={cn("absolute inset-x-0 top-1 h-4 transition-transform", movimiento)}
            style={{ transform: `translateX(${fraccion * 100}%)` }}
          >
            <span className="absolute top-0 left-0 h-full w-0.5 -translate-x-1/2 rounded-full bg-tinta" />
          </div>
        )}
      </div>
    </div>
  );
}
