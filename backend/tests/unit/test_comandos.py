"""Comandos (§6.5): payload de cmd, validación de sub, predicados de confirmación y textos."""

import pytest
from pydantic import ValidationError

from app.protocolo import sub_valido
from app.schemas.comandos import ComandoNuevo
from app.services.comandos import cumple, payload_cmd, texto_enviado, texto_sin_confirmar
from tests.ayudas import estado


@pytest.mark.parametrize(
    ("nodo_id", "accion", "sub", "payload"),
    [
        (2, "silenciar", 0, "2:silenciar:0"),
        (0, "desactivar", 0, "0:desactivar:0"),
        (4, "activar", 1, "4:activar:1"),
        (4, "desactivar", 1, "4:desactivar:1"),
        (None, "silenciar", 0, "todo:silenciar"),
    ],
)
def test_payload_de_cmd(nodo_id: int | None, accion: str, sub: int, payload: str) -> None:
    assert payload_cmd(nodo_id, accion, sub) == payload  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("nodo_id", "accion", "sub"),
    [
        (2, "activar", 1),  # la presencia solo existe en el nodo 4
        (4, "silenciar", 1),
        (5, "silenciar", 0),
        (2, "apagar", 0),
        (None, "activar", 0),  # a todos los nodos solo se les silencia
    ],
)
def test_payload_invalido(nodo_id: int | None, accion: str, sub: int) -> None:
    with pytest.raises(ValueError):
        payload_cmd(nodo_id, accion, sub)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("nodo_id", "accion", "sub", "valido"),
    [
        (4, "activar", 1, True),
        (4, "desactivar", 1, True),
        (4, "silenciar", 1, False),
        (3, "activar", 1, False),
        (3, "silenciar", 0, True),
        (None, "silenciar", 0, True),
    ],
)
def test_sub_valido(nodo_id: int | None, accion: str, sub: int, valido: bool) -> None:
    assert sub_valido(nodo_id, accion, sub) is valido


def test_el_esquema_rechaza_sub_fuera_de_la_presencia() -> None:
    assert ComandoNuevo(nodo=2, accion="silenciar").sub == 0
    assert ComandoNuevo(nodo=4, accion="activar", sub=1).sub == 1
    for datos in (
        {"nodo": 2, "accion": "activar", "sub": 1},
        {"nodo": 4, "accion": "silenciar", "sub": 1},
        {"nodo": 5, "accion": "silenciar"},
        {"nodo": 2, "accion": "apagar"},
        {"nodo": 2, "accion": "silenciar", "sub": 2},
    ):
        with pytest.raises(ValidationError):
            ComandoNuevo.model_validate(datos)


@pytest.mark.parametrize(
    ("accion", "nodo_id", "sub", "cambios", "confirmado"),
    [
        # En estado_normal: hab = 1 en los nodos 0 a 3 y hab = 3 (gas y presencia) en el 4
        ("activar", 2, 0, {}, True),
        ("activar", 2, 0, {"n2": {"hab": 0}}, False),
        ("desactivar", 2, 0, {"n2": {"hab": 0}}, True),
        ("desactivar", 2, 0, {}, False),
        ("activar", 4, 1, {}, True),
        ("activar", 4, 1, {"n4": {"hab": 1}}, False),
        ("desactivar", 4, 1, {"n4": {"hab": 1}}, True),  # la presencia es el bit 0x02
        ("desactivar", 4, 0, {"n4": {"hab": 2}}, True),  # gas apagado, presencia activa
        ("silenciar", 2, 0, {}, True),
        ("silenciar", 2, 0, {"n2": {"al": 1}}, False),
        ("silenciar", 3, 0, {"n3": {"al": 2}}, False),
    ],
)
def test_predicados_de_confirmacion(
    accion: str, nodo_id: int, sub: int, cambios: dict, confirmado: bool
) -> None:
    assert cumple(accion, nodo_id, sub, estado(**cambios)) is confirmado


def test_un_nodo_sin_conexion_o_sin_ver_no_confirma_nada() -> None:
    """Tras reiniciar, la central manda los nodos con hab y al en 0 hasta que reportan."""
    reinicio = estado("estado_reinicio")
    assert not cumple("silenciar", 2, 0, reinicio)
    assert not cumple("desactivar", 2, 0, reinicio)
    sin_conexion = estado(n2={"enLinea": False, "al": 0})
    assert not cumple("silenciar", 2, 0, sin_conexion)


def test_silenciar_todo_mira_solo_los_nodos_conocidos() -> None:
    assert cumple("silenciar", None, 0, estado())
    assert not cumple("silenciar", None, 0, estado(n2={"al": 1}))
    # Un nodo sin conexión conserva su último "al": no impide confirmar
    assert cumple("silenciar", None, 0, estado(n3={"al": 2, "enLinea": False}))


@pytest.mark.parametrize(
    ("accion", "nodo_id", "sub", "enviado", "sin_confirmar"),
    [
        (
            "silenciar",
            2,
            0,
            "Laura silenció Baño",
            "La central no confirmó el comando de Laura: silenciar Baño",
        ),
        (
            "activar",
            4,
            1,
            "Laura activó Cocina · gas (presencia)",
            "La central no confirmó el comando de Laura: activar Cocina · gas (presencia)",
        ),
        (
            "silenciar",
            None,
            0,
            "Laura silenció todas las alarmas",
            "La central no confirmó el comando de Laura: silenciar todas las alarmas",
        ),
    ],
)
def test_textos_de_los_eventos(
    accion: str, nodo_id: int | None, sub: int, enviado: str, sin_confirmar: str
) -> None:
    assert texto_enviado("Laura", accion, nodo_id, sub) == enviado
    assert texto_sin_confirmar("Laura", accion, nodo_id, sub) == sin_confirmar


def test_texto_sin_confirmar_sin_usuario() -> None:
    assert (
        texto_sin_confirmar(None, "desactivar", 1, 0)
        == "La central no confirmó el comando: desactivar Habitación"
    )
