"""Eventos nuevos de la bitácora de la central (§6.4). FUNCIÓN PURA: sin I/O."""

from collections.abc import Sequence

from app.protocolo import EventoCentral

# Estos el backend ya los registra con más contexto (usuario, duración): no se importan
PREFIJOS_PROPIOS = ("ALARMA ", "App remota:")
SUFIJOS_PROPIOS = ("conectado", "reconectado", "perdió la conexión")


def eventos_nuevos(
    anterior: Sequence[EventoCentral] | None, nueva: Sequence[EventoCentral]
) -> list[EventoCentral]:
    """Los eventos de `nueva` que no estaban en `anterior`, del más reciente al más antiguo.

    Las dos listas van del más reciente al más antiguo y los eventos nuevos aparecen al
    principio. Se busca en `nueva` el evento más reciente de `anterior`, y el resto del tramo
    común también debe coincidir: lo que queda antes es nuevo. Si no aparece (la central
    reinició y su bitácora empezó de cero, o no hay estado anterior), toda la lista es nueva.
    Así un reinicio que repite "+4s Central iniciada" no se pierde, como pasaría con un hash
    de hora y texto.
    """
    if anterior:
        for inicio in range(len(nueva)):
            comun = len(nueva) - inicio
            if list(nueva[inicio:]) == list(anterior[:comun]):
                return list(nueva[:inicio])
    return list(nueva)


def se_importa(evento: EventoCentral) -> bool:
    return not evento.x.startswith(PREFIJOS_PROPIOS) and not evento.x.endswith(SUFIJOS_PROPIOS)
