"""Detector de transiciones (§6.4, §13.1)."""

import pytest

from app.protocolo import (
    AL_AGUA,
    AL_GAS,
    AL_INTRUSION,
    AL_SIN_MOVIMIENTO,
    AL_TEMPERATURA,
    FL_HORA_VALIDA,
    FL_HORARIO_NOCTURNO,
)
from app.services.detector import Transicion, detectar
from tests.ayudas import estado


@pytest.mark.parametrize(
    ("nodo", "bit", "tipo", "limite", "valor"),
    [
        (0, AL_INTRUSION, "INTRUSION", None, None),
        (1, AL_SIN_MOVIMIENTO, "SIN_MOVIMIENTO", 1800, None),
        (2, AL_SIN_MOVIMIENTO, "SIN_MOVIMIENTO", 600, None),
        (3, AL_AGUA, "AGUA", 480, None),
        (4, AL_GAS, "GAS", 240, None),
        (4, AL_TEMPERATURA, "TEMPERATURA", None, 24.6),
        (4, AL_SIN_MOVIMIENTO, "SIN_MOVIMIENTO", 1200, None),  # presencia: usa l2
    ],
)
def test_abre_y_cierra_cada_tipo(
    nodo: int, bit: int, tipo: str, limite: int | None, valor: float | None
) -> None:
    con_alarma = estado(**{f"n{nodo}": {"al": bit}})
    assert detectar(None, con_alarma, set()) == [
        Transicion("alarma_abre", nodo, tipo, valor=valor, limite_s=limite)  # type: ignore[arg-type]
    ]
    assert detectar(con_alarma, estado(), {(nodo, tipo)}) == [
        Transicion("alarma_cierra", nodo, tipo)  # type: ignore[arg-type]
    ]


def test_una_alarma_ya_abierta_no_se_abre_de_nuevo() -> None:
    assert detectar(None, estado(n2={"al": AL_SIN_MOVIMIENTO}), {(2, "SIN_MOVIMIENTO")}) == []


def test_un_reinicio_de_la_central_no_cierra_nada() -> None:
    abiertas = {(2, "SIN_MOVIMIENTO"), (4, "GAS"), (3, "NODO_SIN_CONEXION")}
    antes = estado(n2={"al": AL_SIN_MOVIMIENTO}, n4={"al": AL_GAS})
    assert detectar(antes, estado("estado_reinicio"), abiertas) == []


def test_nodo_sin_conexion_abre_y_cierra() -> None:
    caido = estado(n3={"enLinea": False, "hace": 25})
    assert detectar(None, caido, set()) == [
        Transicion("nodo_offline", 3, "NODO_SIN_CONEXION", hace_s=25)
    ]
    assert detectar(caido, estado(), {(3, "NODO_SIN_CONEXION")}) == [
        Transicion("nodo_online", 3, "NODO_SIN_CONEXION")
    ]


def test_mientras_el_nodo_esta_caido_se_conservan_sus_alarmas() -> None:
    caido = estado(n2={"enLinea": False, "al": 0, "hace": 40})
    abiertas = {(2, "SIN_MOVIMIENTO"), (2, "NODO_SIN_CONEXION")}
    assert detectar(None, caido, abiertas) == []


def test_varios_bits_a_la_vez_en_el_nodo_4() -> None:
    ambas = estado(n4={"al": AL_GAS | AL_TEMPERATURA, "v1": 61.0})
    transiciones = detectar(None, ambas, set())
    assert [(t.tipo, t.tipo_alarma) for t in transiciones] == [
        ("alarma_abre", "GAS"),
        ("alarma_abre", "TEMPERATURA"),
    ]
    assert transiciones[1].valor == 61.0


def test_cambio_de_hab_de_la_habitacion_por_horario() -> None:
    dia = estado(n1={"hab": 1, "fl": FL_HORA_VALIDA | 0x01})
    noche = estado(n1={"hab": 0, "fl": FL_HORA_VALIDA | FL_HORARIO_NOCTURNO})
    assert detectar(dia, noche, set()) == [
        Transicion("habilitado_cambia", 1, hab_previo=1, hab_nuevo=0, por_horario=True)
    ]
    assert detectar(noche, dia, set())[0].por_horario


def test_cambio_de_hab_por_comando_o_desde_la_app_local() -> None:
    assert detectar(estado(), estado(n2={"hab": 0}), set()) == [
        Transicion("habilitado_cambia", 2, hab_previo=1, hab_nuevo=0, por_horario=False)
    ]


def test_sin_estado_previo_no_hay_cambio_de_hab() -> None:
    assert detectar(None, estado(n2={"hab": 0}), set()) == []


def test_un_nodo_que_reaparece_tras_el_reinicio_no_cuenta_como_cambio_de_hab() -> None:
    assert detectar(estado("estado_reinicio"), estado(), set()) == []
