"""Lecturas para las gráficas (§7.2): qué se guarda de cada estado. La consulta llega en F6."""

from app.protocolo import (
    FL_CALENTANDO,
    FL_ERROR_SENSOR,
    NODO_COCINA_AGUA,
    NODO_COCINA_GAS,
    EstadoCentral,
)

INTERVALO_S = 60  # una muestra por minuto y casa


def lecturas_de(estado: EstadoCentral) -> list[tuple[int, str, float]]:
    """(nodo, métrica, valor) de un estado. Función pura.

    Solo de nodos vistos y en línea: uno sin conexión sigue con su último valor congelado, y
    uno aún no visto tras un reinicio de la central llega en ceros. Ninguno es una lectura real.
    """
    lecturas: list[tuple[int, str, float]] = []
    agua = estado.nodos[NODO_COCINA_AGUA]
    if agua.conocido:
        lecturas.append((agua.id, "caudal", agua.v1))
    gas = estado.nodos[NODO_COCINA_GAS]
    if gas.conocido:
        if not gas.fl & FL_ERROR_SENSOR:
            lecturas.append((gas.id, "temperatura", gas.v1))
        if not gas.fl & FL_CALENTANDO:
            lecturas.append((gas.id, "gas", gas.v2))
    return lecturas
