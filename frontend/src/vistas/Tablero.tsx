/**
 * El tablero de la casa (§11.2): la franja del momento, el campo rojo si algo suena y los cinco
 * instrumentos en una sola placa. Todo se mueve con el WebSocket y el reloj de 1 s.
 */
import { AvisoSinCanal } from "../componentes/AvisoSinCanal";
import { BitacoraCentral } from "../componentes/BitacoraCentral";
import { CampoAlarmas } from "../componentes/CampoAlarmas";
import { FranjaMomento } from "../componentes/FranjaMomento";
import { Instrumento } from "../componentes/Instrumento";
import { Boton } from "../componentes/ui/Boton";
import { mensajeDe } from "../api/cliente";
import { textosAlarma } from "../dominio/textos";
import { useCasaActual, useEstadoEnVivo } from "../tiempo-real/casaActual";

function TableroCargando() {
  return (
    <div aria-busy="true" aria-label="Cargando el tablero" className="space-y-4">
      <div className="h-5 w-3/4 rounded-[4px] bg-cara-2" />
      <ul className="placa divide-y divide-filo overflow-hidden rounded-[10px]">
        {[0, 1, 2, 3, 4].map((i) => (
          <li key={i} className="space-y-3 px-4 py-3.5">
            <div className="flex items-center gap-3">
              <span className="size-2.5 rounded-full ring-1 ring-marca ring-inset" />
              <div className="flex-1 space-y-1.5">
                <div className="h-4 w-32 rounded-[3px] bg-cara-2" />
                <div className="h-3.5 w-20 rounded-[3px] bg-cara-2" />
              </div>
              <div className="h-8 w-[3.25rem] rounded-[6px] bg-cara-2" />
            </div>
            {i > 0 && <div className="h-2 rounded-[2px] bg-cara-2" />}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Tablero() {
  const { casaId, conexion, sonido } = useCasaActual();
  const envivo = useEstadoEnVivo(casaId, conexion);
  const { consulta } = envivo;
  const estado = consulta.data;

  if (casaId === null) return null;
  if (consulta.isPending) return <TableroCargando />;
  if (!estado) {
    return (
      <div className="placa space-y-3 rounded-[10px] px-4 py-5">
        <h1 className="text-lg font-semibold">No se pudo cargar la casa</h1>
        <p className="text-tinta-2">{mensajeDe(consulta.error)}</p>
        <Boton
          variante="secundario"
          ocupado={consulta.isFetching && "Reintentando…"}
          onClick={() => void consulta.refetch()}
        >
          Reintentar
        </Boton>
      </div>
    );
  }

  const central = estado.central;
  if (!central) {
    return (
      <div className="placa space-y-2 rounded-[10px] px-4 py-5">
        <h1 className="text-lg font-semibold">La central todavía no se ha conectado</h1>
        <p className="text-tinta-2">
          Cuando se conecte, aquí verás la puerta, la habitación, el baño y la cocina, cada uno con
          su luz y su escala. Si ya está instalada, revisa que tenga internet.
        </p>
      </div>
    );
  }

  const enAlarma = central.nodos.filter((n) => n.al !== 0);
  const resumen = enAlarma
    .map((n) => `Alarma en ${n.nombre}: ${textosAlarma(n).join(", ")}.`)
    .join(" ");

  // En el celular, una columna: el momento, las alarmas, los instrumentos y la bitácora. En
  // pantallas anchas, el momento, las alarmas y la bitácora a la izquierda y la placa a la derecha
  return (
    <div className="space-y-4 lg:grid lg:grid-cols-[minmax(0,4fr)_minmax(0,7fr)] lg:grid-rows-[auto_1fr] lg:items-start lg:gap-x-6 lg:gap-y-4 lg:space-y-0">
      <h1 className="sr-only">Tablero</h1>
      <p aria-live="assertive" className="sr-only">
        {resumen}
      </p>

      <div className="space-y-4 lg:col-start-1 lg:row-start-1">
        <FranjaMomento central={central} vivo={envivo.vivo} />
        {enAlarma.length > 0 && (
          <CampoAlarmas
            casaId={casaId}
            nodos={enAlarma}
            abiertas={estado.alarmas_abiertas}
            desdeLlegadaS={envivo.desdeLlegadaS}
            centralEnLinea={envivo.vivo}
            sonido={sonido}
          />
        )}
        <AvisoSinCanal />
      </div>

      <section
        aria-labelledby="titulo-nodos"
        className="lg:col-start-2 lg:row-span-2 lg:row-start-1"
      >
        <h2 id="titulo-nodos" className="sr-only">
          Nodos de la casa
        </h2>
        <ul className="placa divide-y divide-filo overflow-hidden rounded-[10px]">
          {central.nodos.map((nodo) => (
            <Instrumento
              key={nodo.id}
              casaId={casaId}
              nodo={nodo}
              vivo={envivo.vivo}
              edadS={envivo.edadS}
            />
          ))}
        </ul>
      </section>

      <div className="lg:col-start-1 lg:row-start-2">
        <BitacoraCentral central={central} />
      </div>
    </div>
  );
}
