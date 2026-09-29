"""Parser del payload de la central (§4.3) y espejo de protocolo.h (§4.4)."""

import re
from collections.abc import Callable
from typing import Any

import pytest

from app import protocolo
from app.protocolo import parsear_estado
from tests.ayudas import FIXTURES, RAIZ_REPO, en_bytes, payload

FIRMWARE = RAIZ_REPO / "firmware" / "gateway_puerta"


def test_parsea_el_ejemplo_de_la_especificacion() -> None:
    estado = parsear_estado((FIXTURES / "estado_alarma.json").read_bytes())
    assert (estado.hora_valida, estado.red) == (True, "wifi")
    bano = estado.nodos[2]
    assert (bano.nombre, bano.al, bano.l1, bano.en_linea) == ("Baño", 1, 600, True)
    assert estado.nodos[3].nombre == "Cocina · agua"
    assert (estado.nodos[4].v1, estado.nodos[4].v2) == (24.6, 640)
    assert estado.eventos[0].x == "ALARMA Baño: sin movimiento por 10 min"
    assert estado.eventos[0].a is True


def test_parsea_un_estado_recien_reiniciada_la_central() -> None:
    estado = parsear_estado((FIXTURES / "estado_reinicio.json").read_bytes())
    assert estado.hora == "+6s" and not estado.hora_valida
    assert [nodo.visto for nodo in estado.nodos] == [True, False, False, False, False]


def test_acepta_utf8() -> None:
    datos = payload(n2={"nombre": "Baño de la niña"})
    assert parsear_estado(en_bytes(datos)).nodos[2].nombre == "Baño de la niña"


@pytest.mark.parametrize(
    "romper",
    [
        lambda d: d["nodos"][2].pop("enLinea"),
        lambda d: d["nodos"][1].update(al="mucho"),
        lambda d: d["nodos"].pop(),  # cuatro nodos
        lambda d: d["nodos"].reverse(),  # fuera de orden
        lambda d: d.update(red="lte"),
        lambda d: d.pop("eventos"),
    ],
)
def test_rechaza_lo_que_no_cumple_el_contrato(romper: Callable[[dict[str, Any]], Any]) -> None:
    datos = payload()
    romper(datos)
    with pytest.raises(ValueError):
        parsear_estado(en_bytes(datos))


def test_rechaza_json_mal_formado() -> None:
    with pytest.raises(ValueError):
        parsear_estado(b'{"hora": "27/09')


def test_los_bits_son_los_de_protocolo_h() -> None:
    texto = (FIRMWARE / "protocolo.h").read_text(encoding="utf-8")
    definidos = dict(re.findall(r"#define\s+((?:AL|HAB|FL)_\w+)\s+(0x[0-9A-Fa-f]+)", texto))
    assert len(definidos) == 14
    for nombre, valor in definidos.items():
        assert getattr(protocolo, nombre) == int(valor, 16), nombre


def test_los_nombres_de_los_nodos_son_los_del_firmware() -> None:
    texto = (FIRMWARE / "gateway_puerta.ino").read_text(encoding="utf-8")
    declaracion = re.search(r"Nodo nodos\[TOTAL_NODOS\] = \{(.*?)\};", texto, re.DOTALL)
    assert declaracion is not None
    assert re.findall(r'\{"([^"]+)"\}', declaracion.group(1)) == list(protocolo.NODOS.values())
