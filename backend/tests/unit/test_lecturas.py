"""Qué lecturas se guardan de cada estado (§7.2)."""

from app.protocolo import FL_CALENTANDO, FL_ERROR_SENSOR, FL_HORA_VALIDA
from app.services.lecturas import lecturas_de
from tests.ayudas import estado


def test_lecturas_de_un_estado_normal() -> None:
    assert lecturas_de(estado()) == [(3, "caudal", 6.4), (4, "temperatura", 24.6), (4, "gas", 640)]


def test_un_nodo_sin_conexion_no_genera_lecturas() -> None:
    assert lecturas_de(estado(n3={"enLinea": False})) == [(4, "temperatura", 24.6), (4, "gas", 640)]


def test_tras_un_reinicio_los_nodos_aun_no_vistos_no_generan_ceros() -> None:
    assert lecturas_de(estado("estado_reinicio")) == []


def test_sensor_de_temperatura_con_error_o_gas_calentando() -> None:
    assert lecturas_de(estado(n4={"fl": FL_HORA_VALIDA | FL_ERROR_SENSOR})) == [
        (3, "caudal", 6.4),
        (4, "gas", 640),
    ]
    assert lecturas_de(estado(n4={"fl": FL_HORA_VALIDA | FL_CALENTANDO})) == [
        (3, "caudal", 6.4),
        (4, "temperatura", 24.6),
    ]
