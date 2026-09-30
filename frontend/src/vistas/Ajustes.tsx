/**
 * Ajustes de la casa (§8.3, solo admin): el nombre, los recordatorios y los avisos. Cada campo
 * dice qué cambia en la vida real; se guarda solo lo que cambió.
 */
import { CircleAlert } from "lucide-react";
import { useId, useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { useCasa, useGuardarCasa, type Casa, type CambioAjustes } from "../api/administracion";
import { mensajeDe } from "../api/cliente";
import { CabeceraAjustes } from "../componentes/CabeceraAjustes";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { Palanca } from "../componentes/ui/Palanca";
import { useCasaActual } from "../tiempo-real/casaActual";

/** Minutos, con la misma forma de error que `Campo`: en tinta, con su ícono, debajo de la ayuda. */
function CampoMinutos({
  etiqueta,
  nombre,
  ayuda,
  valor,
  alCambiar,
  error,
}: {
  etiqueta: string;
  nombre: string;
  ayuda: string;
  valor: string;
  alCambiar: (valor: string) => void;
  error: string | null;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">
        {etiqueta}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          name={nombre}
          inputMode="numeric"
          pattern="[0-9]*"
          value={valor}
          onChange={(e) => alCambiar(e.target.value.replace(/\D/g, ""))}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-ayuda ${id}-error` : `${id}-ayuda`}
          className="cifras h-12 w-24 rounded-[6px] bg-cara px-3 text-right text-lg text-tinta ring-1 ring-filo ring-inset focus-visible:ring-2 focus-visible:ring-tinta focus-visible:outline-none aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-tinta-2"
        />
        <span className="text-tinta-2">min</span>
      </div>
      <p id={`${id}-ayuda`} className="text-sm text-tinta-3">
        {ayuda}
      </p>
      {error && (
        <p id={`${id}-error`} className="flex items-start gap-1.5 text-sm font-medium text-tinta">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}

function Interruptor({
  etiqueta,
  ayuda,
  activo,
  alCambiar,
}: {
  etiqueta: string;
  ayuda: ReactNode;
  activo: boolean;
  alCambiar: (activo: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1">
        <label htmlFor={id} className="font-medium">
          {etiqueta}
        </label>
        <p className="text-sm text-tinta-3">{ayuda}</p>
      </div>
      <Palanca id={id} etiqueta={etiqueta} activa={activo} alCambiar={alCambiar} />
    </div>
  );
}

function minutos(texto: string, minimo: number): number | null {
  const n = Number(texto);
  return texto !== "" && Number.isInteger(n) && n >= minimo && n <= 1440 ? n : null;
}

function Formulario({ casa }: { casa: Casa }) {
  const guardar = useGuardarCasa(casa.id);
  const [nombre, setNombre] = useState(casa.nombre);
  const [recordatorio, setRecordatorio] = useState(String(casa.ajustes.recordatorio_min));
  const [conexion, setConexion] = useState(String(casa.ajustes.recordatorio_conexion_min));
  const [caida, setCaida] = useState(String(casa.ajustes.minutos_central_caida));
  const [avisarNodo, setAvisarNodo] = useState(casa.ajustes.avisar_nodo_sin_conexion);
  const [avisarResueltas, setAvisarResueltas] = useState(casa.ajustes.avisar_resueltas);

  const numeros = {
    recordatorio_min: minutos(recordatorio, 0),
    recordatorio_conexion_min: minutos(conexion, 0),
    minutos_central_caida: minutos(caida, 1),
  };
  const cambios: CambioAjustes = {};
  for (const [campo, valor] of Object.entries(numeros) as [keyof typeof numeros, number | null][]) {
    if (valor !== null && valor !== casa.ajustes[campo]) cambios[campo] = valor;
  }
  if (avisarNodo !== casa.ajustes.avisar_nodo_sin_conexion) {
    cambios.avisar_nodo_sin_conexion = avisarNodo;
  }
  if (avisarResueltas !== casa.ajustes.avisar_resueltas) cambios.avisar_resueltas = avisarResueltas;
  const nombreNuevo = nombre.trim() !== casa.nombre ? nombre.trim() : undefined;
  // "Guardar" solo se bloquea si no se tocó nada. Con un valor por corregir sigue habilitado
  // (DESIGN.md: la validación es por campo) y, al tocarlo, lleva a ese campo
  const tocado =
    nombre !== casa.nombre ||
    recordatorio !== String(casa.ajustes.recordatorio_min) ||
    conexion !== String(casa.ajustes.recordatorio_conexion_min) ||
    caida !== String(casa.ajustes.minutos_central_caida) ||
    avisarNodo !== casa.ajustes.avisar_nodo_sin_conexion ||
    avisarResueltas !== casa.ajustes.avisar_resueltas;

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const porCorregir =
      nombre.trim() === ""
        ? "nombre"
        : (Object.keys(numeros) as (keyof typeof numeros)[]).find((c) => numeros[c] === null);
    if (porCorregir) {
      const campo = evento.currentTarget.elements.namedItem(porCorregir);
      if (campo instanceof HTMLInputElement) campo.focus();
      return;
    }
    if (nombreNuevo === undefined && Object.keys(cambios).length === 0) return; // "05" es 5
    guardar.mutate(
      { nombre: nombreNuevo, ajustes: cambios },
      {
        onSuccess: () => {
          setNombre(nombre.trim());
          toast.success("Ajustes guardados");
        },
        onError: (error) => toast.error(mensajeDe(error)),
      },
    );
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-4">
      <section className="placa space-y-4 rounded-[10px] px-4 py-4">
        <h2 className="font-semibold">La casa</h2>
        <Campo
          etiqueta="Nombre"
          name="nombre"
          ayuda="Así aparece en la app y en los avisos."
          value={nombre}
          maxLength={80}
          onChange={(e) => setNombre(e.target.value)}
          error={nombre.trim() === "" ? "Escribe un nombre para la casa." : null}
        />
      </section>

      <section className="placa space-y-5 rounded-[10px] px-4 py-4">
        <h2 className="font-semibold">Recordatorios</h2>
        <CampoMinutos
          etiqueta="Repetir el aviso de una alarma cada"
          nombre="recordatorio_min"
          ayuda="Mientras nadie la silencie. Con 0 se avisa una sola vez."
          valor={recordatorio}
          alCambiar={setRecordatorio}
          error={numeros.recordatorio_min === null ? "Un número entre 0 y 1440." : null}
        />
        <CampoMinutos
          etiqueta="Repetir el aviso de conexión cada"
          nombre="recordatorio_conexion_min"
          ayuda="Para un nodo sin conexión o la central desconectada. Con 0 se avisa una sola vez."
          valor={conexion}
          alCambiar={setConexion}
          error={numeros.recordatorio_conexion_min === null ? "Un número entre 0 y 1440." : null}
        />
        <CampoMinutos
          etiqueta="Avisar que la central se desconectó después de"
          nombre="minutos_central_caida"
          ayuda="Así un corte corto de internet no despierta a nadie."
          valor={caida}
          alCambiar={setCaida}
          error={numeros.minutos_central_caida === null ? "Un número entre 1 y 1440." : null}
        />
      </section>

      <section className="placa space-y-5 rounded-[10px] px-4 py-4">
        <h2 className="font-semibold">Qué más se avisa</h2>
        <Interruptor
          etiqueta="Nodo sin conexión"
          ayuda="Cuando un sensor deja de comunicarse con la central."
          activo={avisarNodo}
          alCambiar={setAvisarNodo}
        />
        <Interruptor
          etiqueta="Alarma resuelta"
          ayuda="Cuando alguien silencia una alarma o se apaga sola."
          activo={avisarResueltas}
          alCambiar={setAvisarResueltas}
        />
      </section>

      <div className="flex items-center gap-3">
        <Boton type="submit" disabled={!tocado} ocupado={guardar.isPending && "Guardando…"}>
          Guardar cambios
        </Boton>
        {!tocado && <p className="text-sm text-tinta-3">Sin cambios por guardar.</p>}
      </div>
    </form>
  );
}

export default function Ajustes() {
  const { casaId } = useCasaActual();
  const casa = useCasa(casaId ?? 0);
  if (casaId === null) return null;
  return (
    <>
      <CabeceraAjustes casaId={casaId} />
      {casa.isPending ? (
        <div
          aria-busy="true"
          aria-label="Cargando los ajustes"
          className="placa h-72 rounded-[10px]"
        />
      ) : casa.isError ? (
        <div className="placa space-y-3 rounded-[10px] px-4 py-5">
          <p className="text-tinta-2">{mensajeDe(casa.error)}</p>
          <Boton variante="secundario" onClick={() => void casa.refetch()}>
            Reintentar
          </Boton>
        </div>
      ) : (
        <Formulario casa={casa.data} />
      )}
    </>
  );
}
