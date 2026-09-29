"""Textos de las alarmas (§4.4) y lo que se guarda al abrirlas."""

import pytest

from app.protocolo import limite_de, nombre_nodo, texto_alarma, valor_de
from tests.ayudas import estado


@pytest.mark.parametrize(
    ("tipo", "limite", "valor", "texto"),
    [
        ("INTRUSION", None, None, "Movimiento en la entrada durante la madrugada"),
        ("SIN_MOVIMIENTO", 600, None, "Sin movimiento por 10 min"),
        ("SIN_MOVIMIENTO", 1200, None, "Sin movimiento por 20 min"),
        ("AGUA", 480, None, "Agua corriendo más de 8 min"),
        ("GAS", 240, None, "Gas detectado por más de 4 min"),
        ("TEMPERATURA", None, 56.34, "Temperatura alta: 56.3 °C"),
        ("NODO_SIN_CONEXION", None, None, "Sin conexión con la central"),
        ("CENTRAL_DESCONECTADA", None, None, "La central no está conectada"),
    ],
)
def test_texto_de_cada_alarma(
    tipo: str, limite: int | None, valor: float | None, texto: str
) -> None:
    assert texto_alarma(tipo, limite, valor) == texto


def test_tipo_desconocido() -> None:
    with pytest.raises(ValueError):
        texto_alarma("INCENDIO")


def test_el_nodo_4_usa_l2_para_la_presencia() -> None:
    gas = estado().nodos[4]
    assert (limite_de(gas, "SIN_MOVIMIENTO"), limite_de(gas, "GAS")) == (1200, 240)
    assert limite_de(estado().nodos[1], "SIN_MOVIMIENTO") == 1800


def test_la_temperatura_se_guarda_al_abrir() -> None:
    gas = estado(n4={"v1": 58.25}).nodos[4]
    assert (valor_de(gas, "TEMPERATURA"), valor_de(gas, "GAS")) == (58.25, None)


def test_nombre_de_nodo() -> None:
    assert (nombre_nodo(2), nombre_nodo(None)) == ("Baño", "Central")
