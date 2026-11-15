/**
 * Las casas de la cuenta (§11.2). Con una sola, lleva directo a su tablero.
 */
import { ChevronRight } from "lucide-react";
import { Link, Navigate } from "react-router";
import { mensajeDe } from "../api/cliente";
import { useCasas } from "../api/consultas";
import { Lampara } from "../componentes/Lampara";
import { Boton } from "../componentes/ui/Boton";

export default function Casas() {
  const casas = useCasas();

  if (casas.isPending) {
    return (
      <div aria-busy="true" aria-label="Cargando tus casas" className="space-y-4">
        <div className="h-7 w-40 rounded-[4px] bg-cara-2" />
        <div className="placa h-32 rounded-[10px]" />
      </div>
    );
  }
  if (casas.isError) {
    return (
      <div className="placa space-y-3 rounded-[10px] px-4 py-5">
        <h1 className="text-lg font-semibold">No se pudieron cargar tus casas</h1>
        <p className="text-tinta-2">{mensajeDe(casas.error)}</p>
        <Boton variante="secundario" onClick={() => void casas.refetch()}>
          Reintentar
        </Boton>
      </div>
    );
  }
  if (casas.data.length === 1) return <Navigate to={`/casa/${casas.data[0].id}`} replace />;

  return (
    <>
      <h1 className="text-xl font-semibold">Tus casas</h1>
      {casas.data.length === 0 ? (
        <div className="placa space-y-2 rounded-[10px] px-4 py-5">
          <p className="font-medium">Tu cuenta todavía no tiene casas.</p>
          <p className="text-tinta-2">
            Pídele a quien administra la casa que te invite. Cuando lo haga, aparecerá aquí.
          </p>
        </div>
      ) : (
        <ul className="placa divide-y divide-filo overflow-hidden rounded-[10px]">
          {casas.data.map((casa) => (
            <li key={casa.id}>
              <Link
                to={`/casa/${casa.id}`}
                className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-cara-2"
              >
                <Lampara
                  luz={casa.alarmas_abiertas > 0 ? "alarma" : casa.online ? "vigilando" : "apagada"}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{casa.nombre}</span>
                  <span className="block text-sm text-tinta-2">
                    {casa.alarmas_abiertas > 0 ? (
                      <span className="font-semibold text-alarma">
                        {casa.alarmas_abiertas === 1
                          ? "1 alarma abierta"
                          : `${casa.alarmas_abiertas} alarmas abiertas`}
                      </span>
                    ) : casa.online ? (
                      "Central en línea"
                    ) : (
                      "Central desconectada"
                    )}
                    {" · "}
                    {casa.rol === "admin" ? "la administras" : "la cuidas"}
                  </span>
                </span>
                <ChevronRight aria-hidden="true" className="size-5 text-tinta-3" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
