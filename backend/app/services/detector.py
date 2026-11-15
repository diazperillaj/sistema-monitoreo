"""Detector de transiciones (§6.4). FUNCIÓN PURA: sin I/O, todo lo que decide está aquí."""

from dataclasses import dataclass
from typing import Literal

from app.protocolo import (
    ALARMAS_DE_SENSOR,
    BAT_BAJA,
    BAT_LLENA,
    FL_HORARIO_NOCTURNO,
    NODO_HABITACION,
    EstadoCentral,
    NodoCentral,
    TipoAlarma,
    limite_de,
    valor_de,
)

TipoTransicion = Literal[
    "alarma_abre",
    "alarma_cierra",
    "nodo_offline",
    "nodo_online",
    "habilitado_cambia",
    "bateria_baja",
    "bateria_llena",
]
Abiertas = set[tuple[int | None, str]]  # (nodo_id, tipo) de las alarmas abiertas en la BD


@dataclass(frozen=True)
class Transicion:
    tipo: TipoTransicion
    nodo_id: int
    tipo_alarma: TipoAlarma | None = None
    valor: float | None = None  # temperatura al abrir TEMPERATURA; % en las de batería
    limite_s: int | None = None  # l1 o l2 al abrir
    hab_previo: int | None = None
    hab_nuevo: int | None = None
    por_horario: bool = False  # nodo 1: hab cambió junto con FL_HORARIO_NOCTURNO
    hace_s: int = 0  # nodo_offline: segundos sin datos del nodo


def detectar(
    previo: EstadoCentral | None, nuevo: EstadoCentral, abiertas: Abiertas
) -> list[Transicion]:
    """Compara con las alarmas abiertas en la BD (no con `previo`): así el resultado es el
    mismo aunque el backend se haya reiniciado. `previo` solo sirve para los cambios de hab."""
    transiciones: list[Transicion] = []
    for nodo in nuevo.nodos:
        transiciones += _conexion(nodo, abiertas)
        if nodo.conocido:  # si no, su estado es desconocido: ni se abre ni se cierra nada
            transiciones += _alarmas_de_sensor(nodo, abiertas)
            if previo is not None:
                transiciones += _habilitado(previo.nodos[nodo.id], nodo)
                transiciones += _bateria(previo.nodos[nodo.id], nodo)
    return transiciones


def _conexion(nodo: NodoCentral, abiertas: Abiertas) -> list[Transicion]:
    abierta = (nodo.id, "NODO_SIN_CONEXION") in abiertas
    if nodo.visto and not nodo.en_linea and not abierta:
        return [Transicion("nodo_offline", nodo.id, "NODO_SIN_CONEXION", hace_s=nodo.hace)]
    if nodo.en_linea and abierta:
        return [Transicion("nodo_online", nodo.id, "NODO_SIN_CONEXION")]
    return []  # visto = false: la central acaba de reiniciar y aún no lo oye


def _alarmas_de_sensor(nodo: NodoCentral, abiertas: Abiertas) -> list[Transicion]:
    transiciones = []
    for bit, tipo in ALARMAS_DE_SENSOR.items():
        activa = bool(nodo.al & bit)
        abierta = (nodo.id, tipo) in abiertas
        if activa and not abierta:
            transiciones.append(
                Transicion(
                    "alarma_abre",
                    nodo.id,
                    tipo,
                    valor=valor_de(nodo, tipo),
                    limite_s=limite_de(nodo, tipo),
                )
            )
        elif abierta and not activa:
            transiciones.append(Transicion("alarma_cierra", nodo.id, tipo))
    return transiciones


def _habilitado(antes: NodoCentral, ahora: NodoCentral) -> list[Transicion]:
    if not antes.conocido or antes.hab == ahora.hab:
        return []
    por_horario = ahora.id == NODO_HABITACION and bool((antes.fl ^ ahora.fl) & FL_HORARIO_NOCTURNO)
    return [
        Transicion(
            "habilitado_cambia",
            ahora.id,
            hab_previo=antes.hab,
            hab_nuevo=ahora.hab,
            por_horario=por_horario,
        )
    ]


def _bateria(antes: NodoCentral, ahora: NodoCentral) -> list[Transicion]:
    """Un aviso cuando el nodo enciende BAT_BAJA o BAT_LLENA. El nodo las mantiene con
    histéresis, así que cruzar el umbral avisa una vez, no a cada lectura. Necesita `previo`:
    tras reiniciar el backend, la comparación sigue con el estado guardado (§6.3)."""
    if not antes.conocido or not ahora.con_bateria:
        return []
    nuevas = ahora.bfl & ~antes.bfl
    transiciones = []
    if nuevas & BAT_BAJA:
        transiciones.append(Transicion("bateria_baja", ahora.id, valor=ahora.bat))
    if nuevas & BAT_LLENA:
        transiciones.append(Transicion("bateria_llena", ahora.id, valor=ahora.bat))
    return transiciones
